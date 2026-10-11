# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Project Management MVP: sign in, a single Kanban board per user, five fixed columns with renamable titles, cards that can be edited, removed and moved by drag and drop, and an AI chat sidebar that can create, edit and move cards. It runs locally in one Docker container. All planned work (10 parts) is implemented, and a code review plus its remediation is recorded in `docs/code_review.md`.

Constraints:
- Sign-in is hardcoded to `user` / `password` and checked in the browser (`AuthGate.tsx`). The database supports multiple users, but the MVP uses one board for one user. The API has no server-side auth, so it is published on 127.0.0.1 only.
- AI calls go through OpenRouter with model `openai/gpt-oss-120b`. `OPENROUTER_API_KEY` comes from the root `.env`.
- Python packages are managed with `uv`. The database is SQLite and is created if missing.

Coding standards: keep it simple and do not over-engineer; no unnecessary defensive code or extra features; keep the README minimal; no emojis anywhere. When something breaks, find the root cause with evidence before fixing.

Color scheme: accent yellow `#ecad0a`, blue primary `#209dd7`, purple secondary `#753991` (submit buttons, important actions), dark navy `#032147` (headings), gray text `#888888`.

## Architecture

One Docker image serves everything on port 8000.

- **Dockerfile (multi-stage):** a Node 24 stage runs `npm ci` and builds the Next.js app (`output: "export"`) into `frontend/out`. The Python 3.12 stage runs `uv sync --frozen --no-dev`, copies that output to `backend/static`, runs as a non-root user, and starts `uvicorn` from the venv. It has a healthcheck on `/api/health`. `STATIC_DIR` overrides the static path.
- **Persistence:** the start scripts mount the Docker volume `pm-mvp-data` at `/app/backend/data` and publish `127.0.0.1:8000`. To reset data: stop, then `docker volume rm pm-mvp-data`.
- **Backend (`backend/app`):** `main.py` builds the app (lifespan, 400 validation handler, router, static mount last); `routes.py` has the `/api` endpoints; `models.py` the Pydantic models (board, chat request, AI actions); `actions.py` applies AI actions to a board; `db.py` the schema, seed and SQLite access; `ai.py` the OpenRouter call; `config.py` the paths, constants and root `.env` loader (imported first so the environment is ready). `db.DB_PATH` (default `backend/data/kanban.db`, overridable with the `DB_PATH` env var) is read at import; tests monkeypatch it. `db.init_db()` runs once in the FastAPI lifespan, so tests that use `TestClient` without a context manager must call it themselves (`tests/conftest.py` does). To fake the AI in tests patch `ai.query_openrouter` or `ai.httpx.post`. Handlers are plain `def` (threadpool) because SQLite and httpx calls are blocking.
- **Validation:** the `Board` Pydantic model is the single contract for PUT bodies, chat request boards and AI updates (five fixed column ids in order, each card in exactly one column, card ids match map keys, length limits). Request validation errors are mapped to HTTP 400 with a readable `detail`.
- **API:** `GET /api/health`; `GET` and `PUT /api/users/{username}/board` (whole-board read and replace); `POST /api/ai/chat`.
- **AI flow:** `AIChatSidebar.tsx` waits for pending saves, then posts board, last 20 messages and the prompt. The model is asked for a small JSON object `{reply, actions}`, never the whole board (an earlier design had the model re-emit the full board and it returned malformed columns). Actions are `create_card`, `update_card`, `move_card`, `delete_card`, `rename_column` (models in `models.py`, applied by `actions.apply_actions`). The request uses OpenRouter strict structured output (`ai.RESPONSE_FORMAT`, with `provider.require_parameters` so only providers that enforce it are used); an earlier `json_object` request let the model misspell keys such as `"type "` and drop required fields, and OpenRouter routes the model to different providers. Strict mode needs every key present, so unused action fields arrive as null. The backend parses the output (`parse_ai_content` strips code fences), validates it as `AIResponse`, applies the actions in order to a copy of the board, validates the result with `Board`, saves it, and returns `{reply, boardUpdate}` where `boardUpdate` is the saved board or null. If the response is invalid or an action cannot be applied, the model gets one retry (`routes.run_ai_request`, `MAX_AI_ATTEMPTS`) with its rejected answer and the reason; if that also fails the endpoint returns 400 and changes nothing. Without an API key it returns a "not configured" reply.
- **SQLite schema:** `users`, `boards`, `columns`, `cards`; columns and cards are keyed `(board_id, id)`; order is an integer `position` that is read back by sorting (see `docs/kanban_schema.json`).
- **Frontend (`frontend/src`):** `AuthGate` renders `KanbanBoard`, which owns state in a `boardRef` and funnels every change through `updateBoard`, which saves via a serialized promise queue (one PUT at a time, in order). Load failure shows an error with Retry and never falls back to seed data. Column titles save on blur or Enter; cards have inline edit. `lib/kanban.ts` has the types, `initialData` (tests only) and `moveCard`. Styling is Tailwind 4; Next 16, React 19. The chat sidebar is beside the board only at `2xl`. Under `next dev`, `/api/*` is proxied to `BACKEND_API_URL` (default `http://127.0.0.1:8000`).

## Commands

Run the whole app (builds the image, passes the root `.env`, serves http://localhost:8000):
- Windows: `scripts\start.ps1`, `scripts\stop.ps1` (do not redirect stderr; the script stops on Docker's progress output)
- Mac/Linux: `scripts/start.sh`, `scripts/stop.sh`

Backend (from `backend/`):
- `uv sync`
- `uv run uvicorn app.main:app --reload --port 8000`
- `uv run pytest`; one test: `uv run pytest tests/test_persistence.py::test_name`

Frontend (from `frontend/`):
- `npm run dev`, `npm run build` (also type-checks tests), `npm run lint`
- `npm run test:unit` (Vitest); one file: `npx vitest run src/lib/kanban.test.ts`; one test: `npx vitest run -t "name"`
- `npm run test:e2e` (Playwright): starts its own backend on port 8100 with a temporary database and AI disabled, and its own dev server on port 3100; it never reuses running servers, and each test resets the board through the API. `npm run test:all` runs unit then e2e.
