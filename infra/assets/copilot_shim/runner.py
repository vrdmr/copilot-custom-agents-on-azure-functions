import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from copilot import ResumeSessionConfig, SessionConfig
import frontmatter

from .client_manager import CopilotClientManager, _is_byok_mode
from .config import resolve_config_dir, session_exists
from .mcp import get_cached_mcp_servers
from .skills import resolve_session_directory_for_skills
from .tools import _REGISTERED_TOOLS_CACHE

DEFAULT_TIMEOUT = 120.0


@dataclass
class AgentResult:
    session_id: str
    content: str
    content_intermediate: List[str]
    tool_calls: List[Dict[str, Any]]
    reasoning: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)


def _load_agents_md_content() -> str:
    """Load AGENTS.md content from disk (called once at module load)."""
    agents_md_path = os.path.join(os.getcwd(), "AGENTS.md")
    logging.info(f"Checking for AGENTS.md at: {agents_md_path}")
    if not os.path.exists(agents_md_path):
        logging.info("No AGENTS.md found")
        return ""

    try:
        with open(agents_md_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        parsed = frontmatter.loads(raw_content)
        content = (parsed.content or "").strip()
        metadata_count = len(parsed.metadata) if parsed.metadata else 0

        logging.info(
            f"Loaded AGENTS.md from {agents_md_path} ({len(raw_content)} chars, frontmatter keys={metadata_count}, body chars={len(content)})"
        )
        return content
    except Exception as e:
        logging.warning(f"Failed to read AGENTS.md: {e}")
        return ""


# Cache AGENTS.md content at module load time (won't change during runtime)
_AGENTS_MD_CONTENT_CACHE = _load_agents_md_content()


DEFAULT_MODEL = os.environ.get("COPILOT_MODEL", "claude-sonnet-4")


def _build_session_config(
    model: str = DEFAULT_MODEL,
    config_dir: Optional[str] = None,
    session_id: Optional[str] = None,
    streaming: bool = False,
) -> SessionConfig:
    session_config: SessionConfig = {
        "model": model,
        "streaming": streaming,
        "tools": _REGISTERED_TOOLS_CACHE,  # type: ignore
        "system_message": {"mode": "replace", "content": _AGENTS_MD_CONTENT_CACHE},
    }

    # If Microsoft Foundry BYOK is configured, add provider config
    if _is_byok_mode():
        foundry_endpoint = os.environ["AZURE_AI_FOUNDRY_ENDPOINT"]
        foundry_key = os.environ["AZURE_AI_FOUNDRY_API_KEY"]
        foundry_model = os.environ.get("AZURE_AI_FOUNDRY_MODEL", model)
        # GPT-5 series models use the responses API format
        wire_api = "responses" if foundry_model.startswith("gpt-5") else "completions"
        session_config["model"] = foundry_model  # type: ignore
        session_config["provider"] = {  # type: ignore
            "type": "openai",
            "base_url": foundry_endpoint,
            "api_key": foundry_key,
            "wire_api": wire_api,
        }
        logging.info(f"BYOK mode: using Microsoft Foundry endpoint={foundry_endpoint}, model={foundry_model}, wire_api={wire_api}")

    if session_id:
        session_config["session_id"] = session_id

    if config_dir:
        session_config["config_dir"] = config_dir

    session_directory = resolve_session_directory_for_skills()
    if session_directory:
        session_config["config"] = {"sessionDirectory": session_directory}  # type: ignore
        logging.info(f"Using sessionDirectory for skills discovery: {session_directory}")

    mcp_servers = get_cached_mcp_servers()
    if mcp_servers:
        session_config["mcp_servers"] = mcp_servers

    return session_config


def _build_resume_config(
    model: str = DEFAULT_MODEL,
    config_dir: Optional[str] = None,
    streaming: bool = False,
) -> ResumeSessionConfig:
    resume_config: ResumeSessionConfig = {
        "model": model,
        "streaming": streaming,
        "tools": _REGISTERED_TOOLS_CACHE,  # type: ignore
        "system_message": {"mode": "replace", "content": _AGENTS_MD_CONTENT_CACHE},
    }

    if config_dir:
        resume_config["config_dir"] = config_dir

    mcp_servers = get_cached_mcp_servers()
    if mcp_servers:
        resume_config["mcp_servers"] = mcp_servers

    return resume_config


async def run_copilot_agent(
    prompt: str,
    timeout: float = DEFAULT_TIMEOUT,
    model: str = DEFAULT_MODEL,
    session_id: Optional[str] = None,
    streaming: bool = False,
) -> AgentResult:
    config_dir = resolve_config_dir()
    client = await CopilotClientManager.get_client()

    # Resume existing session or create a new one
    if session_id and session_exists(config_dir, session_id):
        logging.info(f"Resuming existing session: {session_id}")
        resume_config = _build_resume_config(model=model, config_dir=config_dir)
        session = await client.resume_session(session_id, resume_config)
    else:
        if session_id:
            logging.info(f"Creating new session with provided ID: {session_id}")
        session_config = _build_session_config(
            model=model, config_dir=config_dir, session_id=session_id, streaming=streaming
        )
        session = await client.create_session(session_config)

    response_content: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    reasoning_content: List[str] = []
    events_log: List[Dict[str, Any]] = []

    done = asyncio.Event()

    def on_event(event):
        event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
        events_log.append({"type": event_type, "data": str(event.data) if event.data else None})

        if event_type == "assistant.message":
            response_content.append(event.data.content)
        elif event_type == "assistant.message_delta" and streaming:
            if event.data.delta_content:
                response_content.append(event.data.delta_content)
        elif event_type == "assistant.reasoning_delta" and streaming:
            if hasattr(event.data, "delta_content") and event.data.delta_content:
                reasoning_content.append(event.data.delta_content)
        elif event_type == "tool.execution_start":
            tool_calls.append(
                {
                    "event_id": str(event.id) if hasattr(event, "id") and event.id else None,
                    "timestamp": event.timestamp.isoformat() if hasattr(event, "timestamp") and event.timestamp else None,
                    "tool_call_id": getattr(event.data, "tool_call_id", None),
                    "tool_name": getattr(event.data, "tool_name", None),
                    "arguments": getattr(event.data, "arguments", None),
                    "parent_tool_call_id": getattr(event.data, "parent_tool_call_id", None),
                }
            )
        elif event_type == "session.idle":
            done.set()

    session.on(on_event)

    if streaming:
        logging.info(f"Starting streaming session with ID: {session.session_id}")
        return AgentResult(
            session_id=session.session_id,
            content=response_content[-1] if response_content else "",
            content_intermediate=response_content[-6:-1] if len(response_content) > 1 else [],
            tool_calls=tool_calls,
            reasoning="".join(reasoning_content) if reasoning_content else None,
            events=events_log,
        )

    else:
        await session.send_and_wait({"prompt": prompt}, timeout=timeout)

        return AgentResult(
            session_id=session.session_id,
            content=response_content[-1] if response_content else "",
            content_intermediate=response_content[-6:-1] if len(response_content) > 1 else [],
            tool_calls=tool_calls,
            reasoning="".join(reasoning_content) if reasoning_content else None,
            events=events_log,
        )


_STREAM_SENTINEL = object()


async def run_copilot_agent_stream(
    prompt: str,
    timeout: float = DEFAULT_TIMEOUT,
    model: str = DEFAULT_MODEL,
    session_id: Optional[str] = None,
):
    """Async generator that yields SSE-formatted events as the agent streams a response.

    Yields strings like 'data: {"type": "delta", ...}\\n\\n' suitable for StreamingResponse.
    """
    config_dir = resolve_config_dir()
    client = await CopilotClientManager.get_client()

    if session_id and session_exists(config_dir, session_id):
        logging.info(f"[stream] Resuming existing session: {session_id}")
        resume_config = _build_resume_config(model=model, config_dir=config_dir, streaming=True)
        session = await client.resume_session(session_id, resume_config)
    else:
        if session_id:
            logging.info(f"[stream] Creating new session with provided ID: {session_id}")
        session_config = _build_session_config(
            model=model, config_dir=config_dir, session_id=session_id, streaming=True
        )
        session = await client.create_session(session_config)

    queue: asyncio.Queue = asyncio.Queue()
    accept_events = False
    seen_event_ids: set[str] = set()

    def on_event(event):
        nonlocal accept_events
        event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
        event_id = str(event.id) if hasattr(event, "id") and event.id else None

        if not accept_events:
            return

        if event_id:
            if event_id in seen_event_ids:
                return
            seen_event_ids.add(event_id)

        if event_type == "assistant.message_delta":
            delta = getattr(event.data, "delta_content", None)
            if delta:
                queue.put_nowait({"type": "delta", "content": delta})
        elif event_type == "assistant.reasoning_delta":
            reasoning_delta = getattr(event.data, "delta_content", None)
            if reasoning_delta:
                queue.put_nowait({"type": "intermediate", "content": reasoning_delta})
        elif event_type == "assistant.message":
            message_content = getattr(event.data, "content", "")
            queue.put_nowait({"type": "message", "content": message_content})
        elif event_type == "tool.execution_start":
            queue.put_nowait({
                "type": "tool_start",
                "event_id": str(event.id) if hasattr(event, "id") and event.id else None,
                "timestamp": event.timestamp.isoformat() if hasattr(event, "timestamp") and event.timestamp else None,
                "tool_name": getattr(event.data, "tool_name", None),
                "tool_call_id": getattr(event.data, "tool_call_id", None),
                "parent_tool_call_id": getattr(event.data, "parent_tool_call_id", None),
                "arguments": getattr(event.data, "arguments", None),
            })
        elif event_type == "tool.execution_end":
            queue.put_nowait({
                "type": "tool_end",
                "event_id": str(event.id) if hasattr(event, "id") and event.id else None,
                "timestamp": event.timestamp.isoformat() if hasattr(event, "timestamp") and event.timestamp else None,
                "tool_name": getattr(event.data, "tool_name", None),
                "tool_call_id": getattr(event.data, "tool_call_id", None),
                "parent_tool_call_id": getattr(event.data, "parent_tool_call_id", None),
                "result": getattr(event.data, "result", None),
            })
        elif event_type == "session.idle":
            queue.put_nowait(_STREAM_SENTINEL)

    session.on(on_event)

    # Yield the session ID first so the client knows it immediately
    yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id})}\n\n"

    # Fire-and-forget: send the prompt, events arrive via on_event callback
    accept_events = True
    await session.send({"prompt": prompt})

    # Drain the queue until session.idle sentinel arrives or timeout
    try:
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Timeout waiting for response'})}\n\n"
                break

            item = await asyncio.wait_for(queue.get(), timeout=remaining)
            if item is _STREAM_SENTINEL:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

            yield f"data: {json.dumps(item)}\n\n"
    except asyncio.TimeoutError:
        yield f"data: {json.dumps({'type': 'error', 'content': 'Timeout waiting for response'})}\n\n"
