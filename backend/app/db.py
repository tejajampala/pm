import hashlib
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from app.config import BASE_DIR
from app.models import Board

DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "data" / "kanban.db"))


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


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS boards (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS columns (
    board_id TEXT NOT NULL REFERENCES boards(id),
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (board_id, id)
);
CREATE TABLE IF NOT EXISTS cards (
    board_id TEXT NOT NULL,
    id TEXT NOT NULL,
    column_id TEXT NOT NULL,
    title TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (board_id, id),
    FOREIGN KEY (board_id, column_id) REFERENCES columns(board_id, id)
);
"""


@contextmanager
def get_connection():
    """Open a connection that commits on success, rolls back on error, and always closes."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    """Create tables and seed the MVP user and board; restores any missing fixed column."""
    # Sign-in is checked in the browser for the MVP; the stored hash only shapes the schema.
    password_hash = hashlib.sha256(b"password").hexdigest()
    seed = get_default_board()
    board_id = "board-user"

    with get_connection() as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES ('user', 'user', ?)",
            (password_hash,),
        )
        connection.execute(
            "INSERT OR IGNORE INTO boards (id, user_id, name) VALUES (?, 'user', 'Main Board')",
            (board_id,),
        )
        for position, column in enumerate(seed["columns"]):
            created = connection.execute(
                "INSERT OR IGNORE INTO columns (board_id, id, title, position) VALUES (?, ?, ?, ?)",
                (board_id, column["id"], column["title"], position),
            ).rowcount
            if created:
                for card_position, card_id in enumerate(column["cardIds"]):
                    card = seed["cards"][card_id]
                    connection.execute(
                        "INSERT OR IGNORE INTO cards (board_id, id, column_id, title, details, position) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (board_id, card["id"], column["id"], card["title"], card["details"], card_position),
                    )
            connection.execute(
                "UPDATE columns SET position = ? WHERE board_id = ? AND id = ?",
                (position, board_id, column["id"]),
            )


def find_board_id(connection: sqlite3.Connection, username: str) -> str:
    row = connection.execute(
        "SELECT boards.id FROM boards JOIN users ON users.id = boards.user_id WHERE users.username = ?",
        (username,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User or board not found")
    return row["id"]


def read_board(connection: sqlite3.Connection, board_id: str) -> dict:
    columns = connection.execute(
        "SELECT id, title FROM columns WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()
    cards = connection.execute(
        "SELECT id, column_id, title, details FROM cards WHERE board_id = ? ORDER BY position",
        (board_id,),
    ).fetchall()

    card_ids_by_column: dict[str, list[str]] = {column["id"]: [] for column in columns}
    card_map = {}
    for card in cards:
        card_ids_by_column[card["column_id"]].append(card["id"])
        card_map[card["id"]] = {"id": card["id"], "title": card["title"], "details": card["details"]}

    return {
        "columns": [
            {"id": column["id"], "title": column["title"], "cardIds": card_ids_by_column[column["id"]]}
            for column in columns
        ],
        "cards": card_map,
    }


def fetch_board_for_user(username: str) -> dict:
    with get_connection() as connection:
        return read_board(connection, find_board_id(connection, username))


def save_board_for_user(username: str, board: Board) -> dict:
    with get_connection() as connection:
        board_id = find_board_id(connection, username)
        connection.execute("DELETE FROM cards WHERE board_id = ?", (board_id,))
        connection.execute("DELETE FROM columns WHERE board_id = ?", (board_id,))

        for column_index, column in enumerate(board.columns):
            connection.execute(
                "INSERT INTO columns (board_id, id, title, position) VALUES (?, ?, ?, ?)",
                (board_id, column.id, column.title, column_index),
            )
            for card_index, card_id in enumerate(column.cardIds):
                card = board.cards[card_id]
                connection.execute(
                    "INSERT INTO cards (board_id, id, column_id, title, details, position) VALUES (?, ?, ?, ?, ?, ?)",
                    (board_id, card.id, column.id, card.title, card.details, card_index),
                )

        connection.execute("UPDATE boards SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (board_id,))
        return read_board(connection, board_id)
