"""
Azure Functions + GitHub Copilot SDK
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import azure.functions as func
import frontmatter
from copilot_shim import run_copilot_agent

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _load_agents_functions_from_frontmatter() -> List[Dict[str, Any]]:
    """Load optional function definitions from AGENTS.md frontmatter."""
    agents_md_path = Path(os.getcwd()) / "AGENTS.md"
    if not agents_md_path.exists():
        logging.info("AGENTS.md not found. No dynamic functions registered.")
        return []

    try:
        raw_content = agents_md_path.read_text(encoding="utf-8")
        parsed = frontmatter.loads(raw_content)
        metadata = parsed.metadata if isinstance(parsed.metadata, dict) else {}
        functions = metadata.get("functions")

        if functions is None:
            logging.info("AGENTS.md frontmatter has no 'functions' section. No dynamic functions registered.")
            return []

        if not isinstance(functions, list):
            logging.warning("AGENTS.md frontmatter 'functions' must be an array. Ignoring dynamic functions.")
            return []

        return [item for item in functions if isinstance(item, dict)]
    except Exception as exc:
        logging.warning(f"Failed to parse AGENTS.md frontmatter: {exc}")
        return []


def _normalize_timer_schedule(schedule: str) -> str:
    """Accept 5-part cron by prepending seconds; keep 6-part schedules unchanged."""
    schedule_parts = schedule.strip().split()
    if len(schedule_parts) == 5:
        return f"0 {schedule.strip()}"
    return schedule.strip()


def _is_valid_timer_schedule(schedule: str) -> bool:
    return len(schedule.strip().split()) == 6


def _to_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return default


def _safe_timer_name(raw_name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "_", raw_name).strip("_")
    if not name:
        return "timer_agent"
    if name[0].isdigit():
        return f"timer_{name}"
    return name


def _register_dynamic_timer_functions() -> None:
    function_specs = _load_agents_functions_from_frontmatter()
    if not function_specs:
        return

    registered_names = set()

    for index, spec in enumerate(function_specs, start=1):
        trigger_value = spec.get("trigger", "timer")
        trigger = str(trigger_value).strip().lower()
        if trigger != "timer":
            logging.warning(
                f"Rejected AGENTS function #{index}: unsupported trigger '{trigger}' (raw={trigger_value!r}). Only 'timer' is supported."
            )
            continue

        schedule_raw = spec.get("schedule")
        prompt_raw = spec.get("prompt")

        if not isinstance(schedule_raw, str) or not schedule_raw.strip():
            logging.warning(f"Skipping AGENTS function #{index}: missing required 'schedule'")
            continue

        if not isinstance(prompt_raw, str) or not prompt_raw.strip():
            logging.warning(f"Skipping AGENTS function #{index}: missing required 'prompt'")
            continue

        schedule = _normalize_timer_schedule(schedule_raw)
        if not _is_valid_timer_schedule(schedule):
            logging.warning(
                f"Skipping AGENTS function #{index}: invalid schedule '{schedule_raw}' after normalization '{schedule}'"
            )
            continue

        base_name = _safe_timer_name(str(spec.get("name") or f"timer_agent_{index}"))
        function_name = base_name
        suffix = 2
        while function_name in registered_names:
            function_name = f"{base_name}_{suffix}"
            suffix += 1
        registered_names.add(function_name)

        prompt = prompt_raw.strip()
        should_log_response = _to_bool(spec.get("logger", True), default=True)

        def _make_timer_handler(
            timer_function_name: str,
            timer_schedule: str,
            timer_prompt: str,
            log_response: bool,
        ):
            async def _timer_handler(timer_request: func.TimerRequest) -> None:
                if timer_request.past_due:
                    logging.info(f"Timer '{timer_function_name}' is past due.")

                logging.info(f"Timer '{timer_function_name}' running with schedule '{timer_schedule}'")

                try:
                    result = await run_copilot_agent(timer_prompt)
                    if log_response:
                        logging.info(
                            "Timer '%s' agent response: %s",
                            timer_function_name,
                            json.dumps(
                                {
                                    "session_id": result.session_id,
                                    "response": result.content,
                                    "response_intermediate": result.content_intermediate,
                                    "tool_calls": result.tool_calls,
                                },
                                ensure_ascii=False,
                                default=str,
                            ),
                        )
                except Exception as exc:
                    logging.exception(f"Timer '{timer_function_name}' failed: {exc}")

            _timer_handler.__name__ = f"timer_handler_{timer_function_name}"
            return _timer_handler

        handler = _make_timer_handler(function_name, schedule, prompt, should_log_response)
        decorated = app.timer_trigger(
            schedule=schedule,
            arg_name="timer_request",
            run_on_startup=False,
        )(handler)
        app.function_name(name=function_name)(decorated)

        logging.info(
            f"Registered dynamic timer function '{function_name}' from AGENTS.md (schedule='{schedule}', logger={should_log_response})"
        )


_register_dynamic_timer_functions()


@app.route(
    route="{*ignored}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def root_chat_page(req: func.HttpRequest) -> func.HttpResponse:
    """Serve the chat UI at the root route."""
    ignored = (req.route_params or {}).get("ignored", "")
    if ignored:
        return func.HttpResponse("Not found", status_code=404)

    index_path = Path(__file__).resolve().parent / "public" / "index.html"
    if not index_path.exists():
        return func.HttpResponse("index.html not found", status_code=404)

    return func.HttpResponse(
        index_path.read_text(encoding="utf-8"),
        status_code=200,
        mimetype="text/html",
    )

@app.route(route="agent/chat", methods=["POST"])
async def chat(req: func.HttpRequest) -> func.HttpResponse:
    """
    Chat endpoint - send a prompt, get a response.

    POST /agent/chat
    Headers:
        x-ms-session-id (optional): Session ID for resuming a previous session
    Body:
    {
        "prompt": "What is 2+2?"
    }
    """
    try:
        body = req.get_json()
        prompt = body.get("prompt")

        if not prompt:
            return func.HttpResponse(
                json.dumps({"error": "Missing 'prompt'"}),
                status_code=400,
                mimetype="application/json",
            )

        session_id = req.headers.get("x-ms-session-id")
        result = await run_copilot_agent(prompt, session_id=session_id)

        response = func.HttpResponse(
            json.dumps(
                {
                    "session_id": result.session_id,
                    "response": result.content,
                    "response_intermediate": result.content_intermediate,
                    "tool_calls": result.tool_calls,
                }
            ),
            mimetype="application/json",
            headers={"x-ms-session-id": result.session_id},
        )
        return response

    except Exception as e:
        error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
        logging.error(f"Chat error: {error_msg}")
        return func.HttpResponse(
            json.dumps({"error": error_msg}), status_code=500, mimetype="application/json"
        )
