import json
import os

import httpx
from fastapi import HTTPException

from app.config import MAX_HISTORY_TURNS, OPENROUTER_MODEL, OPENROUTER_URL
from app.models import ChatTurn


def _nullable(json_type: str) -> dict:
    return {"type": [json_type, "null"]}


# Strict structured output makes the provider enforce this shape, so the model cannot misspell a key.
# Strict mode needs every key present, so fields that do not apply to an action are sent as null.
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "board_actions",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["reply", "actions"],
            "properties": {
                "reply": {"type": "string"},
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["type", "cardId", "columnId", "title", "details", "position"],
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["create_card", "update_card", "move_card", "delete_card", "rename_column"],
                            },
                            "cardId": _nullable("string"),
                            "columnId": _nullable("string"),
                            "title": _nullable("string"),
                            "details": _nullable("string"),
                            "position": _nullable("integer"),
                        },
                    },
                },
            },
        },
    },
}


def parse_ai_content(raw_content: str) -> dict:
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
        cleaned = cleaned.removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="AI response was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="AI response must be a JSON object.")

    return parsed


def query_openrouter(
    board: dict,
    message: str,
    history: list[ChatTurn],
    retry: tuple[dict, str] | None = None,
) -> dict:
    """Ask the model for {reply, actions}. `retry` is a rejected earlier answer and why it was rejected."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "reply": "The AI assistant is not configured in this environment yet.",
            "actions": [],
        }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a project management assistant for a Kanban board with five fixed columns "
                "(ids: col-backlog, col-discovery, col-progress, col-review, col-done). "
                "The user message is JSON with the current board and the user's request. "
                'Return only a JSON object: {"reply": string, "actions": array}. '
                "reply is a short answer or confirmation for the user; do not list the changes, the app lists the ones it applies. "
                "actions lists the board changes to make, in order; use [] when nothing should change. "
                "Never output the whole board. Action shapes: "
                '{"type": "create_card", "columnId": string, "title": string, "details": string}; '
                '{"type": "update_card", "cardId": string, "title": string (optional), "details": string (optional)}; '
                '{"type": "move_card", "cardId": string, "columnId": string, "position": integer (optional, 0-based)}; '
                '{"type": "delete_card", "cardId": string}; '
                '{"type": "rename_column", "columnId": string, "title": string}. '
                "Fields that do not apply to an action must be null. "
                "Use only card ids that exist in the board and the five column ids above."
            ),
        }
    ]
    messages.extend({"role": turn.role, "content": turn.content} for turn in history[-MAX_HISTORY_TURNS:])
    messages.append(
        {"role": "user", "content": json.dumps({"board": board, "prompt": message}, ensure_ascii=False)}
    )
    if retry is not None:
        rejected, problem = retry
        messages.append({"role": "assistant", "content": json.dumps(rejected, ensure_ascii=False)})
        messages.append(
            {
                "role": "user",
                "content": f"That response was rejected: {problem} Reply again with only the corrected JSON object.",
            }
        )

    try:
        response = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Project Management MVP",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": messages,
                "response_format": RESPONSE_FORMAT,
                "provider": {"require_parameters": True},
                "temperature": 0.2,
            },
            timeout=60.0,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"OpenRouter request failed: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"OpenRouter request failed: {response.text[:400]}",
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="OpenRouter returned an invalid JSON response.") from exc
    choices = payload.get("choices") or []
    if not choices:
        raise HTTPException(status_code=502, detail="OpenRouter returned no choices.")

    content = choices[0].get("message", {}).get("content")
    if not content:
        raise HTTPException(status_code=502, detail="OpenRouter returned empty content.")

    return parse_ai_content(content)
