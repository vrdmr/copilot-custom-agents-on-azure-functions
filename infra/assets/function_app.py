"""
Azure Functions + GitHub Copilot SDK
"""

import json
import logging
from pathlib import Path

import azure.functions as func
from copilot_shim import run_copilot_agent

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


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
