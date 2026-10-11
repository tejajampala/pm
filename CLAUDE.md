# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Project Management MVP: sign in, a single Kanban board per user, five fixed columns with renamable titles, cards that can be edited and moved by drag and drop, and an AI chat sidebar that can create, edit and move cards. It runs locally in one Docker container. The planned work (10 parts, from scaffolding through AI sidebar) is implemented; the MVP is feature-complete.

Constraints:
- Sign-in is hardcoded to `user` / `password` and checked in the browser (`AuthGate.tsx`). The database supports multiple users, but the MVP uses one board for one user.
- AI calls go through OpenRouter with model `openai/gpt-oss-120b`. `OPENROUTER_API_KEY` comes from the root `.env`.
- Python packages are managed with `uv`. The database is SQLite and is created if missing.

Coding standards: keep it simple and do not over-engineer; no unnecessary defensive code or extra features; keep the README minimal; no emojis anywhere. When something breaks, find the root cause with evidence before fixing.

Color scheme: accent yellow `#ecad0a`, blue primary `#209dd7`, purple secondary `#753991` (submit buttons, important actions), dark navy `#032147` (headings), gray text `#888888`.

## Architecture

One Docker image serves everything on port 8000.

- **Dockerfile (multi-stage):** a Node stage builds the Next.js app (`output: "export"`, `trailingSlash: true`) into `frontend/out`. The Python 3.12 stage installs `uv`, copies that output to `backend/static`, runs `uv sync`, and starts `uvicorn app.main:app`. `STATIC_DIR` overrides the static path.
- **Backend:** all of it is in `backend/app/main.py` (FastAPI, SQLite, OpenRouter client, static serving). It loads the root `.env` itself at import (`load_env_file`). The DB file is `backend/data/kanban.db`, created by `init_db()` on startup.
- **API:**
  - `GET /api/health`
  - `GET /api/users/{username}/board` returns the board.
  - `PUT /api/users/{username}/board` replaces the whole board (the frontend saves the full board after each change).
  - `POST /api/ai/chat` takes the board, history and message.
- **Board shape (shared by frontend and backend):** `columns` is an ordered list of `{id, title, cardIds}`, and `cards` is a map of `id -> {id, title, details}`. The five fixed column ids must stay in order (`validate_fixed_columns`); a legacy board is restored to five columns without losing data.
- **SQLite schema:** `users` (username unique, `password_hash`), `boards` (`user_id`), `columns` (`board_id`, `title`, integer `position`), `cards` (`board_id`, `column_id`, `title`, `details`, integer `position`), with `created_at`/`updated_at` timestamps. Order is stored as integer positions. The schema is meant to allow multiple users and boards later.
- **AI flow:** `AIChatSidebar.tsx` posts the current board, conversation history and message to `/api/ai/chat`. The backend asks OpenRouter for a JSON object `{reply, boardUpdate}`; `boardUpdate` is null or a complete board. `parse_ai_content` strips code fences and parses it, and `validate_ai_board_update` requires the same column ids and order, and every card in exactly one column with string `id`/`title`/`details`. A valid update is persisted and returned, and the frontend applies it with no reload. Invalid output is rejected with a 400 and the board is not changed. Without an API key, the endpoint returns a "not configured" reply and no update.
- **Known bug:** in `validate_ai_board_update`, the check that `cardIds` is a list of strings is indented under the `raise` of the previous `if`, so it never runs.
- **Frontend (`frontend/src`):**
  - `app/page.tsx` renders `AuthGate`, which renders `KanbanBoard`.
  - `KanbanBoard.tsx` owns board state, loads and saves through the API, handles drag and drop (dnd-kit), column rename, card add and delete, and applies AI updates.
  - `KanbanColumn`, `KanbanCard`, `KanbanCardPreview` (drag overlay) and `NewCardForm` are the presentational pieces.
  - `lib/kanban.ts` holds the board model, seed data and move logic.
  - Styling is Tailwind 4. Next 16, React 19.
  - Under `next dev`, `/api/*` is proxied to `BACKEND_API_URL` (default `http://127.0.0.1:8000`) by rewrites in `next.config.ts`.

## Commands

Run the whole app (builds the image, passes the root `.env`, serves http://localhost:8000):
- Windows: `scripts\start.ps1`, `scripts\stop.ps1`
- Mac/Linux: `scripts/start.sh`, `scripts/stop.sh`

Backend (from `backend/`):
- `uv sync`
- `uv run uvicorn app.main:app --reload --port 8000`
- `uv run pytest`; one test: `uv run pytest tests/test_persistence.py::test_name`
- Tests monkeypatch `main.DB_PATH` to a temp file, so they never touch `data/kanban.db`.

Frontend (from `frontend/`):
- `npm run dev`, `npm run build`, `npm run lint`
- `npm run test:unit` (Vitest); one file: `npx vitest run src/lib/kanban.test.ts`; one test: `npx vitest run -t "name"`
- `npm run test:e2e` (Playwright, specs in `frontend/tests/`; see `playwright.config.ts` for the server it expects)
- `npm run test:all` runs unit then e2e.
