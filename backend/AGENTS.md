# Backend agent guide

## Overview

FastAPI service for the Project Management MVP. It stores the Kanban board in SQLite, proxies board-aware chat to OpenRouter, and serves the static Next.js build at `/`.

## Runtime

- Python 3.12+, FastAPI, Uvicorn, httpx; dependencies managed with uv (`uv.lock` is committed).
- Layout (all in [app/](app)):
  - `main.py`: creates the app, lifespan (runs `db.init_db()`), the 400 validation handler, includes the router, and mounts the static site last.
  - `routes.py`: the `/api` router (health, board GET and PUT, AI chat).
  - `models.py`: Pydantic models (`Board`, `Card`, `Column`, `ChatRequest`, the AI action types, `AIResponse`) and `format_errors`.
  - `actions.py`: `apply_actions` applies the AI's actions to a copy of the board, all or nothing.
  - `db.py`: schema, seed data, `get_connection`, `init_db`, `fetch_board_for_user`, `save_board_for_user`, `DB_PATH`.
  - `ai.py`: `query_openrouter` and `parse_ai_content`.
  - `config.py`: paths, OpenRouter constants, and the root `.env` loader (imported first so the environment is ready).
- Environment: `OPENROUTER_API_KEY` (read from the root `.env` at import), `DB_PATH` (default `backend/data/kanban.db`), `STATIC_DIR` (default `backend/static`).

## Endpoints

- `GET /api/health` returns service status.
- `GET /api/users/{username}/board` returns the board; unknown user returns 404.
- `PUT /api/users/{username}/board` replaces the whole board after validation.
- `POST /api/ai/chat` takes `{username, message, board?, history}`, asks OpenRouter (`openai/gpt-oss-120b`) for `{reply, actions}` (small actions such as `create_card`, `update_card`, `move_card`, `delete_card`, `rename_column`, never the whole board), applies them to the board, saves the result, and returns `{reply, boardUpdate}` (`boardUpdate` is the saved board, or null when there were no actions). The reply ends with a "Changes made:" list built from the applied actions. Without an API key it replies that the assistant is not configured.
- `/` serves `STATIC_DIR` (or a placeholder page if it is missing).

## Validation

The `Board` Pydantic model is the single contract for PUT bodies, chat request boards, and AI updates: five fixed column ids in order, every card in exactly one column, card ids matching their map keys, and length limits on titles and details. Request validation errors are returned as HTTP 400 with a readable `detail`. The model call uses strict JSON-schema output (`ai.RESPONSE_FORMAT`); unused action fields are null. A malformed AI response, an action naming an unknown card or column, or a result that breaks the board rules is sent back to the model once with the reason; if the second answer is also unusable the endpoint returns 400 and nothing is saved. Chat history is limited to 20 turns and only `user` and `assistant` roles are accepted.

Card text is passed to the model as data; the output is schema-validated and can only change the signed-in user's own board.

## Database

Tables `users`, `boards`, `columns`, `cards` (see [../docs/kanban_schema.json](../docs/kanban_schema.json)). `init_db()` runs once at startup (FastAPI lifespan): it creates tables, seeds the MVP user and board, and restores any missing fixed column. Handlers are plain `def` so blocking SQLite and HTTP calls run in the threadpool. `get_connection()` commits on success, rolls back on error, and always closes.

## Tests

`uv run pytest` from `backend/`. `tests/conftest.py` points `db.DB_PATH` at a temp file and calls `db.init_db()` for every test, because the TestClient does not run the lifespan. Patch `ai.query_openrouter` or `ai.httpx.post` to fake the AI. Files: `test_board_api.py`, `test_ai_chat.py`, `test_actions.py`, `test_db.py`, `test_config.py`, `test_main.py`; `helpers.py` has the shared client.
