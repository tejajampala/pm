import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "kanban.db"
STATIC_DIR = Path(os.environ.get("STATIC_DIR", BASE_DIR / "static")).resolve()
ENV_PATH = BASE_DIR.parent / ".env"


def load_env_file() -> None:
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file()


def ensure_board_payload(board: Any) -> dict:
    if not isinstance(board, dict):
        raise HTTPException(status_code=400, detail="Board payload must be an object.")

    if not isinstance(board.get("columns"), list) or not isinstance(board.get("cards"), dict):
        raise HTTPException(status_code=400, detail="Board payload must include columns and cards.")

    return board


def validate_fixed_columns(board: dict) -> None:
    expected_ids = [column["id"] for column in get_default_board()["columns"]]
    actual_ids = [column.get("id") if isinstance(column, dict) else None for column in board["columns"]]
    if actual_ids != expected_ids:
        raise HTTPException(status_code=400, detail="Board must include all five fixed columns in order.")


def validate_ai_board_update(board_update: Any, current_board: dict) -> dict:
    board = ensure_board_payload(board_update)
    current_column_ids = [column["id"] for column in current_board["columns"]]
    updated_column_ids = [column.get("id") for column in board["columns"] if isinstance(column, dict)]
    if updated_column_ids != current_column_ids:
        raise HTTPException(status_code=400, detail="AI boardUpdate must preserve the existing columns and their order.")

    for column in board["columns"]:
        if not isinstance(column, dict):
            raise HTTPException(status_code=400, detail="AI boardUpdate contains an invalid column entry.")
        required_keys = {"id", "title", "cardIds"}
        if not required_keys.issubset(column):
            raise HTTPException(status_code=400, detail="AI boardUpdate columns must include id, title, and cardIds.")
            if not isinstance(column["cardIds"], list) or any(not isinstance(card_id, str) for card_id in column["cardIds"]):
                raise HTTPException(status_code=400, detail="AI boardUpdate column cardIds must be a list of strings.")

    referenced_card_ids = [card_id for column in board["columns"] for card_id in column["cardIds"]]
    if len(referenced_card_ids) != len(set(referenced_card_ids)) or set(referenced_card_ids) != set(board["cards"]):
        raise HTTPException(status_code=400, detail="AI boardUpdate must place every card in exactly one column.")

    for card_id, card in board["cards"].items():
        if not isinstance(card, dict):
            raise HTTPException(status_code=400, detail="AI boardUpdate cards must be map entries.")
        if not {"id", "title", "details"}.issubset(card):
            raise HTTPException(status_code=400, detail="AI boardUpdate cards must include id, title, and details.")
        if not all(isinstance(card[field], str) for field in ("id", "title", "details")):
            raise HTTPException(status_code=400, detail="AI boardUpdate card fields must be strings.")
        if card_id != card["id"]:
            raise HTTPException(status_code=400, detail="AI boardUpdate card ids must match the map keys.")

    return board


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


def query_openrouter(board: dict, message: str, history: list[dict[str, str]]) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "reply": "The AI assistant is not configured in this environment yet.",
            "boardUpdate": None,
        }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful project management assistant. "
                "Keep replies brief and clear. Return only a JSON object with exactly these fields: "
                "'reply' (a string) and 'boardUpdate' (null or a complete board object). "
                "If no board change is requested, set boardUpdate to null. "
                "For a board change, boardUpdate must contain 'columns' and 'cards'. "
                "Keep the existing column ids and order. Each column must contain id, title, and cardIds. "
                "Each card map entry must contain id, title, and details, and every card must appear in exactly one column. "
                "Preserve all unchanged cards and their fields. Use existing card ids when editing or moving cards."
            ),
        }
    ]

    for entry in history:
        if (
            isinstance(entry, dict)
            and entry.get("role") in {"user", "assistant"}
            and isinstance(entry.get("content"), str)
        ):
            messages.append({"role": entry["role"], "content": entry["content"]})

    messages.append(
        {
            "role": "user",
            "content": json.dumps(
                {
                    "board": board,
                    "prompt": message,
                },
                ensure_ascii=False,
            ),
        }
    )

    try:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "Project Management MVP",
            },
            json={
                "model": "openai/gpt-oss-120b",
                "messages": messages,
                "response_format": {"type": "json_object"},
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

app = FastAPI(title="Project Management MVP", version="0.1.0")


def get_default_board() -> dict:
    return {
        "columns": [
            {"id": "col-backlog", "title": "Backlog", "cardIds": ["card-1", "card-2"]},
            {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
            {"id": "col-progress", "title": "In Progress", "cardIds": ["card-4", "card-5"]},
            {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
            {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
        ],
        "cards": {
            "card-1": {"id": "card-1", "title": "Align roadmap themes", "details": "Draft quarterly themes with impact statements and metrics."},
            "card-2": {"id": "card-2", "title": "Gather customer signals", "details": "Review support tags, sales notes, and churn feedback."},
            "card-3": {"id": "card-3", "title": "Prototype analytics view", "details": "Sketch initial dashboard layout and key drill-downs."},
            "card-4": {"id": "card-4", "title": "Refine status language", "details": "Standardize column labels and tone across the board."},
            "card-5": {"id": "card-5", "title": "Design card layout", "details": "Add hierarchy and spacing for scanning dense lists."},
            "card-6": {"id": "card-6", "title": "QA micro-interactions", "details": "Verify hover, focus, and loading states."},
            "card-7": {"id": "card-7", "title": "Ship marketing page", "details": "Final copy approved and asset pack delivered."},
            "card-8": {"id": "card-8", "title": "Close onboarding sprint", "details": "Document release notes and share internally."},
        },
    }


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS boards (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS columns (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL,
                title TEXT NOT NULL,
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (board_id) REFERENCES boards(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL,
                column_id TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (board_id) REFERENCES boards(id),
                FOREIGN KEY (column_id) REFERENCES columns(id)
            )
            """
        )

        user_record = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            ("user",),
        ).fetchone()
        if user_record is None:
            connection.execute(
                "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
                ("user", "user", "password"),
            )

        board_record = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            ("user",),
        ).fetchone()
        if board_record is None:
            connection.execute(
                "INSERT INTO boards (id, user_id, name, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                ("board-user", "user", "Main Board"),
            )

        board_id = "board-user"
        default_board = get_default_board()
        for position, column in enumerate(default_board["columns"]):
            existing_column = connection.execute(
                "SELECT id FROM columns WHERE id = ? AND board_id = ?",
                (column["id"], board_id),
            ).fetchone()
            if existing_column is None:
                connection.execute(
                    "INSERT INTO columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
                    (column["id"], board_id, column["title"], position),
                )
                for card_position, card_id in enumerate(column["cardIds"]):
                    card = default_board["cards"][card_id]
                    existing_card = connection.execute(
                        "SELECT id FROM cards WHERE id = ? AND board_id = ?",
                        (card_id, board_id),
                    ).fetchone()
                    if existing_card is None:
                        connection.execute(
                            "INSERT INTO cards (id, board_id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                card["id"],
                                board_id,
                                column["id"],
                                card["title"],
                                card["details"],
                                card_position,
                            ),
                        )

            connection.execute(
                "UPDATE columns SET position = ? WHERE id = ? AND board_id = ?",
                (position, column["id"], board_id),
            )


def board_from_rows(rows: list[sqlite3.Row]) -> dict:
    columns = []
    cards = {}
    for row in rows:
        if row["table_name"] == "columns":
            columns.append({
                "id": row["id"],
                "title": row["title"],
                "cardIds": json.loads(row["card_ids"] or "[]"),
            })
        else:
            cards[row["id"]] = {
                "id": row["id"],
                "title": row["title"],
                "details": row["details"],
            }
    return {"columns": columns, "cards": cards}


def fetch_board_for_user(username: str) -> dict:
    init_db()
    with get_connection() as connection:
        user = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        board = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        if board is None:
            raise HTTPException(status_code=404, detail="Board not found")

        board_id = board["id"]

        columns = connection.execute(
            """
            SELECT c.id, c.title,
                   COALESCE(
                       (
                           SELECT json_group_array(card.id)
                           FROM cards AS card
                           WHERE card.board_id = c.board_id AND card.column_id = c.id
                           ORDER BY card.position
                       ),
                       '[]'
                   ) AS card_ids
            FROM columns AS c
            WHERE c.board_id = ?
            ORDER BY c.position
            """,
            (board_id,),
        ).fetchall()

        cards = connection.execute(
            "SELECT id, title, details FROM cards WHERE board_id = ? ORDER BY position",
            (board_id,),
        ).fetchall()

        card_map = {
            str(card["id"]): {
                "id": str(card["id"]),
                "title": card["title"],
                "details": card["details"],
            }
            for card in cards
        }

        board_data = {
            "columns": [
                {
                    "id": str(column["id"]),
                    "title": column["title"],
                    "cardIds": json.loads(column["card_ids"] or "[]"),
                }
                for column in columns
            ],
            "cards": card_map,
        }
        return board_data


def save_board_for_user(username: str, board: dict) -> dict:
    board = ensure_board_payload(board)
    validate_fixed_columns(board)
    init_db()
    with get_connection() as connection:
        user = connection.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        board_record = connection.execute(
            "SELECT id FROM boards WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        if board_record is None:
            board_record = connection.execute(
                "INSERT INTO boards (id, user_id, name, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (f"board-{username}", user["id"], "Main Board"),
            )
        board_id = board_record["id"] if hasattr(board_record, "__getitem__") else f"board-{username}"

        current_columns = connection.execute("SELECT id FROM columns WHERE board_id = ?", (board_id,)).fetchall()
        for existing in current_columns:
            connection.execute("DELETE FROM cards WHERE board_id = ? AND column_id = ?", (board_id, existing["id"]))
        connection.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))

        for column_index, column in enumerate(board.get("columns", [])):
            column_id = str(column["id"])
            connection.execute(
                "INSERT INTO columns (id, board_id, title, position) VALUES (?, ?, ?, ?)",
                (column_id, board_id, column["title"], column_index),
            )
            for card_index, card_id in enumerate(column.get("cardIds", [])):
                card = board["cards"][card_id]
                connection.execute(
                    "INSERT INTO cards (id, board_id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(card["id"]), board_id, column_id, card["title"], card.get("details", ""), card_index),
                )

        connection.execute(
            "UPDATE boards SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (board_id,),
        )

    return fetch_board_for_user(username)


@app.post("/api/ai/chat")
async def ai_chat(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="AI request body must be an object.")

    username = payload.get("username") or "user"
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required.")

    board = payload.get("board")
    if board is None:
        board = fetch_board_for_user(username)
    else:
        board = ensure_board_payload(board)

    history = payload.get("history") or []
    if not isinstance(history, list):
        raise HTTPException(status_code=400, detail="History must be a list.")

    response = query_openrouter(board, message, history)

    if "reply" not in response or not isinstance(response["reply"], str):
        raise HTTPException(status_code=400, detail="AI response must include a reply string.")

    board_update = response.get("boardUpdate")
    if board_update is not None:
        board_update = validate_ai_board_update(board_update, board)
        save_board_for_user(username, board_update)
        response["boardUpdate"] = board_update

    return response


def configure_static(app_instance: FastAPI, static_directory: Path) -> None:
    if static_directory.exists():
        app_instance.mount("/", StaticFiles(directory=str(static_directory), html=True), name="static")
        return

    @app_instance.get("/", response_class=HTMLResponse)
    async def root_placeholder() -> str:
        return """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Project Management MVP</title>
            <style>
              body {
                font-family: Arial, sans-serif;
                margin: 0;
                background: linear-gradient(135deg, #f4f8fb, #eef2ff);
                color: #0f172a;
                display: grid;
                place-items: center;
                min-height: 100vh;
              }
              .card {
                background: white;
                border-radius: 18px;
                box-shadow: 0 18px 50px rgba(15, 23, 42, 0.12);
                padding: 2rem 2.5rem;
                max-width: 620px;
                text-align: center;
              }
              h1 {
                margin-top: 0;
                font-size: 2.5rem;
              }
              p {
                font-size: 1.05rem;
                line-height: 1.6;
              }
            </style>
          </head>
          <body>
            <main class="card">
              <h1>Project Management MVP</h1>
              <p>Hello world from the FastAPI backend.</p>
              <p>The app is running locally and ready for the next phase of integration.</p>
            </main>
          </body>
        </html>
        """


init_db()


@app.on_event("startup")
async def startup_event() -> None:
    init_db()


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "project-management-backend",
        "message": "hello world",
    }


@app.get("/api/users/{username}/board")
async def get_user_board(username: str) -> dict:
    return fetch_board_for_user(username)


@app.put("/api/users/{username}/board")
async def put_user_board(username: str, payload: dict) -> dict:
    return save_board_for_user(username, payload)


configure_static(app, STATIC_DIR)
