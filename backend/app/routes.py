from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app import ai, db
from app.actions import ActionError, apply_actions
from app.config import MAX_AI_ATTEMPTS
from app.models import AIResponse, Board, ChatRequest, format_errors

router = APIRouter(prefix="/api")


# Handlers are plain `def` so FastAPI runs the blocking SQLite and HTTP calls in its threadpool.
@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "project-management-backend",
        "message": "hello world",
    }


@router.get("/users/{username}/board")
def get_user_board(username: str) -> dict:
    return db.fetch_board_for_user(username)


@router.put("/users/{username}/board")
def put_user_board(username: str, board: Board) -> dict:
    return db.save_board_for_user(username, board)


def run_ai_request(board: dict, request: ChatRequest) -> tuple[AIResponse, Board | None, list[str]]:
    """Ask the model and apply its actions; if its answer is unusable, tell it why and let it try once more."""
    retry = None
    for _ in range(MAX_AI_ATTEMPTS):
        result = ai.query_openrouter(board, request.message, request.history, retry)
        try:
            response = AIResponse.model_validate(result)
        except ValidationError as exc:
            problem = f"AI response is invalid: {format_errors(exc.errors())}"
        else:
            try:
                if not response.actions:
                    return response, None, []
                update, changes = apply_actions(board, response.actions)
                return response, update, changes
            except ActionError as exc:
                problem = f"AI action could not be applied: {exc}"
            except ValidationError as exc:
                problem = f"AI changes are invalid: {format_errors(exc.errors())}"
        retry = (result, problem)

    raise HTTPException(status_code=400, detail=problem)


@router.post("/ai/chat")
def ai_chat(request: ChatRequest) -> dict:
    board = request.board.model_dump() if request.board else db.fetch_board_for_user(request.username)

    response, update, changes = run_ai_request(board, request)
    if update is None:
        return {"reply": response.reply, "boardUpdate": None}

    saved_board = db.save_board_for_user(request.username, update)
    # The model's reply is only its claim; the list below is what was actually applied.
    bullets = "\n".join(f"- {change}" for change in changes)
    reply = f"{response.reply}\n\nChanges made:\n{bullets}"
    return {"reply": reply, "boardUpdate": saved_board}
