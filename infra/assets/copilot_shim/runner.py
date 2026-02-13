import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from copilot import ResumeSessionConfig, SessionConfig

from .client_manager import CopilotClientManager
from .config import resolve_config_dir, session_exists
from .mcp import get_cached_mcp_servers
from .skills import resolve_skill_directories
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


def _build_session_config(
    model: str = DEFAULT_MODEL,
    config_dir: Optional[str] = None,
    session_id: Optional[str] = None,
) -> SessionConfig:
    session_config: SessionConfig = {
        "model": model,
        "streaming": False,
        "tools": _REGISTERED_TOOLS_CACHE,  # type: ignore
        "system_message": {"mode": "replace", "content": _AGENTS_MD_CONTENT_CACHE},
    }

    if session_id:
        session_config["session_id"] = session_id

    if config_dir:
        session_config["config_dir"] = config_dir
        logging.info(f"SessionConfig: config_dir={config_dir}")

    skill_directory = resolve_skill_directories()
    if skill_directory:
        session_config["skill_directories"] = [skill_directory]
        logging.info(f"Using skill_directories: {skill_directory}")

    mcp_servers = get_cached_mcp_servers()
    if mcp_servers:
        session_config["mcp_servers"] = mcp_servers

    return session_config


def _build_resume_config(
    model: str = DEFAULT_MODEL,
    config_dir: Optional[str] = None,
) -> ResumeSessionConfig:
    resume_config: ResumeSessionConfig = {
        "model": model,
        "streaming": False,
        "tools": _REGISTERED_TOOLS_CACHE,  # type: ignore
        "system_message": {"mode": "replace", "content": _AGENTS_MD_CONTENT_CACHE},
    }

    if config_dir:
        resume_config["config_dir"] = config_dir
        logging.info(f"ResumeSessionConfig: config_dir={config_dir}")

    mcp_servers = get_cached_mcp_servers()
    if mcp_servers:
        resume_config["mcp_servers"] = mcp_servers

    logging.info(f"ResumeSessionConfig built with keys: {list(resume_config.keys())}")
    return resume_config


async def run_copilot_agent(
    prompt: str,
    timeout: float = DEFAULT_TIMEOUT,
    model: str = DEFAULT_MODEL,
    session_id: Optional[str] = None,
) -> AgentResult:
    config_dir = resolve_config_dir()
    print(f"[Session] config_dir={config_dir}, session_id={session_id}")

    # Debug: check what exists at ~/.copilot and at config_dir
    import pathlib
    default_copilot = pathlib.Path.home() / ".copilot"
    default_session_state = default_copilot / "session-state"
    print(f"[Session] ~/.copilot exists: {default_copilot.exists()}")
    print(f"[Session] ~/.copilot/session-state exists: {default_session_state.exists()}")
    if default_session_state.exists():
        sessions_in_default = list(default_session_state.iterdir())
        print(f"[Session] Sessions in ~/.copilot/session-state/: {[s.name for s in sessions_in_default[:10]]}")
    if config_dir:
        custom_session_state = pathlib.Path(config_dir) / "session-state"
        print(f"[Session] {config_dir}/session-state exists: {custom_session_state.exists()}")
        if custom_session_state.exists():
            sessions_in_custom = list(custom_session_state.iterdir())
            print(f"[Session] Sessions in {config_dir}/session-state/: {[s.name for s in sessions_in_custom[:10]]}")

    client = await CopilotClientManager.get_client()

    # Resume existing session or create a new one
    if session_id and session_exists(config_dir, session_id):
        print(f"[Session] RESUMING session '{session_id}' | config_dir={config_dir} | path={config_dir}/session-state/{session_id}")
        resume_config = _build_resume_config(model=model, config_dir=config_dir)
        print(f"[Session] resume_config keys: {list(resume_config.keys())}, config_dir in config: {'config_dir' in resume_config}")
        try:
            session = await client.resume_session(session_id, resume_config)
            print(f"[Session] Resumed OK: {session.session_id}")
        except Exception as e:
            print(f"[Session] Resume FAILED for '{session_id}' config_dir={config_dir}: {e}")
            raise
    else:
        print(f"[Session] CREATING new session | session_id={session_id} | config_dir={config_dir}")
        if session_id:
            exists = session_exists(config_dir, session_id)
            print(f"[Session] session_exists check returned: {exists}")
        session_config = _build_session_config(
            model=model, config_dir=config_dir, session_id=session_id
        )
        session = await client.create_session(session_config)
        print(f"[Session] Created OK: {session.session_id}")

    is_streaming = False  # streaming is always False in current config

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

    return AgentResult(
        session_id=session.session_id,
        content=response_content[-1] if response_content else "",
        content_intermediate=response_content[-6:-1] if len(response_content) > 1 else [],
        tool_calls=tool_calls,
        reasoning="".join(reasoning_content) if reasoning_content else None,
        events=events_log,
    )
