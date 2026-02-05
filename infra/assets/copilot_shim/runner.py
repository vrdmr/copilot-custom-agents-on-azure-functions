import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from copilot import SessionConfig

from .client_manager import CopilotClientManager
from .mcp import get_cached_mcp_servers
from .skills import resolve_session_directory_for_skills
from .tools import _REGISTERED_TOOLS_CACHE

DEFAULT_TIMEOUT = 60.0


@dataclass
class AgentResult:
    content: str
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
            content = f.read()
        logging.info(f"Loaded AGENTS.md from {agents_md_path} ({len(content)} chars)")
        logging.info(f"AGENTS.md content:\n{content}")
        return content
    except Exception as e:
        logging.warning(f"Failed to read AGENTS.md: {e}")
        return ""


# Cache AGENTS.md content at module load time (won't change during runtime)
_AGENTS_MD_CONTENT_CACHE = _load_agents_md_content()


DEFAULT_MODEL = os.environ.get("COPILOT_MODEL", "claude-sonnet-4")


def _build_session_config(model: str = DEFAULT_MODEL) -> SessionConfig:
    session_config: SessionConfig = {
        "model": model,
        "streaming": False,
        "tools": _REGISTERED_TOOLS_CACHE,  # type: ignore
        "system_message": {"mode": "replace", "content": _AGENTS_MD_CONTENT_CACHE},
    }

    session_directory = resolve_session_directory_for_skills()
    if session_directory:
        session_config["config"] = {"sessionDirectory": session_directory}  # type: ignore
        logging.info(f"Using sessionDirectory for skills discovery: {session_directory}")

    mcp_servers = get_cached_mcp_servers()
    if mcp_servers:
        session_config["mcp_servers"] = mcp_servers

    return session_config


async def run_copilot_agent(
    prompt: str,
    timeout: float = DEFAULT_TIMEOUT,
    model: str = DEFAULT_MODEL,
) -> AgentResult:
    session_config = _build_session_config(model=model)
    client = await CopilotClientManager.get_client()

    response_content: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    reasoning_content: List[str] = []
    events_log: List[Dict[str, Any]] = []
    is_streaming = session_config.get("streaming", False)
    session = await client.create_session(session_config)

    try:
        done = asyncio.Event()

        def on_event(event):
            event_type = event.type.value if hasattr(event.type, "value") else str(event.type)
            events_log.append({"type": event_type, "data": str(event.data) if event.data else None})

            if event_type == "assistant.message":
                response_content.append(event.data.content)
            elif event_type == "assistant.message_delta" and is_streaming:
                if event.data.delta_content:
                    response_content.append(event.data.delta_content)
            elif event_type == "assistant.reasoning_delta" and is_streaming:
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
        await session.send_and_wait({"prompt": prompt}, timeout=timeout)
    finally:
        await session.destroy()

    return AgentResult(
        content="".join(response_content),
        tool_calls=tool_calls,
        reasoning="".join(reasoning_content) if reasoning_content else None,
        events=events_log,
    )
