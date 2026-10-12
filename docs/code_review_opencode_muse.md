# Code Review - Muse Spark (OpenCode)

Date: 2026-10-12
Scope: full repo - `backend/`, `frontend/`, `Dockerfile`, `scripts/`, `docs/`, root config
Method: read all source + prior `docs/code_review.md`, ran `uv run pytest` (74 passed) and `npm run test:unit` (19 passed). Did not run Docker build or Playwright e2e in this pass.
Prior review: `docs/code_review.md` (2026-10-11) found 18 issues, all marked fixed. This review verifies current state and finds remaining gaps.

## Verdict

MVP meets spec: sign-in (`user`/`password`), 5 fixed renameable columns, card CRUD + drag-drop, AI sidebar with structured create/edit/move/delete/rename. Code is small, readable, and follows `AGENTS.md` simplicity rule. Prior remediation held up well.

Remaining work is hardening, not rework: no server-side auth, a few race / validation / UX gaps, and minor dependency hygiene. No data-loss bug of the severity of the prior review was found.

## What is good

- Single `Board` Pydantic model (`backend/app/models.py:21`) is the contract for PUT, chat request board, and AI result. Validation errors return 400 with readable `detail` (`backend/app/main.py:24`).
- AI flow is minimal and safe: `{reply, actions}` only, never whole board (`backend/app/ai.py:17`, `backend/app/actions.py:19`). `apply_actions` works on a deep copy, all-or-nothing, then re-validates with `Board` (`backend/app/actions.py:72`). Retry-once with reason (`backend/app/routes.py:32`), 400 without save on second failure. `boardUpdate` null when no actions. Reply suffix "Changes made:" built from applied actions, not model claims (`backend/app/routes.py:66`).
- Strict OpenRouter JSON-schema with `require_parameters` (`backend/app/ai.py:50`), null-padded unused fields documented.
- SQLite lifecycle correct: `init_db()` once in lifespan (`backend/app/main.py:16`), `get_connection()` commits/rollbacks and closes (`backend/app/db.py:74`), plain `def` handlers run in threadpool (`backend/app/routes.py:12`), composite `(board_id, id)` keys, positions sorted in Python (`backend/app/db.py:134`).
- Frontend save path fixed: `boardRef` + `updateBoard` + serialized `saveQueue` (`frontend/src/components/KanbanBoard.tsx:35`), no seed fallback on load failure with Retry (`frontend/src/components/KanbanBoard.tsx:206`), column commit on blur/Enter (`frontend/src/components/KanbanColumn.tsx:19`), `encodeURIComponent` username, `useSyncExternalStore` auth gate, chat waits for pending saves (`frontend/src/components/AIChatSidebar.tsx:38`).
- Docker: multi-stage, `uv sync --frozen --no-dev`, `npm ci`, Node 24, non-root `app` user, healthcheck, `127.0.0.1:8000:8000` bind, `pm-mvp-data` volume (`Dockerfile:1`, `scripts/start.sh:11`, `scripts/start.ps1:11`). `.dockerignore` excludes `.env`, `out`, `data`, `static`.
- Tests: backend temp-DB fixture (`backend/tests/conftest.py:6`), AI mocked, invalid-payload / ordering / retry coverage. Frontend Vitest covers edit/cancel, load-fail/retry, save-fail, save-ordering, AI error. Playwright uses isolated ports 3100/8100, `reuseExistingServer: false`, resets board per test (`frontend/playwright.config.ts:10`, `frontend/tests/kanban.spec.ts:19`).

## Findings

### High

None. No reproducible data-loss, auth bypass beyond intended MVP scope, or crash (500) found. Prior High items 1-6 verified fixed by reading code.

### Medium

1. **No server-side auth; paid AI endpoint is LAN-adjacent.** `GET/PUT /api/users/{username}/board` and `POST /api/ai/chat` trust `username` from the body/path (`backend/app/routes.py:22`). Mitigation today is only `127.0.0.1` publish in start scripts. Any local process / XSS / misconfigured bind can read/write board and spend `OPENROUTER_API_KEY`. Acceptable per MVP ("hardcoded sign-in"), but `CLAUDE.md` should state this as the security boundary and note: do not publish beyond loopback, consider a bearer token post-MVP.
   Files: `backend/app/routes.py:22`, `frontend/src/components/AuthGate.tsx:31`, `scripts/start.sh:11`.

2. **AI chat uses client-supplied board, backend does not check it matches stored board.** `ai_chat` prefers `request.board` if present (`backend/app/routes.py:59`), applies AI actions to it, then overwrites stored board. A stale client board (edits made before load, or two tabs) silently discards server-side changes. Prior review noted "AI update replaces board"; still present. Fix: fetch stored board and use it as base, or pass a version/etag and reject stale writes. At minimum document last-writer-wins in `docs/PLAN.md` known limits.
   Files: `backend/app/routes.py:57`, `frontend/src/components/KanbanBoard.tsx:199`.

3. **Frontend save queue has no retry / conflict handling; local state diverges on PUT failure.** `updateBoard` optimistically sets `boardRef`/`setBoard`, then queues `saveBoard(next)`. On failure it only sets error banner; `boardRef` stays ahead of server (`frontend/src/components/KanbanBoard.tsx:104`). Reload is the only recovery, and next edit sends the diverged board. Queued saves also capture stale `next` snapshots - two rapid edits queue two full-board PUTs, second overwrites first even if first failed. Acceptable for MVP but should surface "reload to resync" in the error banner.
   Files: `frontend/src/components/KanbanBoard.tsx:82`.

4. **Card ordering query is fragile.** `read_board` orders cards by `position` globally, not per column (`backend/app/db.py:139`): `ORDER BY position` without `column_id`. Correct today because positions restart at 0 per column and Python groups in row order, but interleaving (e.g. col A has 3 cards, col B has 1) yields global order that mixes columns. It still groups correctly per column since relative order within each column is preserved, but this relies on implicit behavior. Fix: `ORDER BY column_id, position` or sort per column in Python.
   Files: `backend/app/db.py:134`.

5. **`init_db()` restores missing columns but never restores missing seed cards.** If a column is deleted manually (or legacy DB), `init_db` re-inserts the column but `if created:` guard means cards are only seeded for newly created columns (`backend/app/db.py:105`). `test_legacy_board_is_restored` passes because columns are recreated, but a DB with all 5 columns and zero cards stays empty. Minor; document or seed missing cards unconditionally.

6. **Chat history cap is enforced in two places with different semantics.** Backend slices `history[-MAX_HISTORY_TURNS:]` (`backend/app/ai.py:107`, 20 turns) and frontend slices `messages.slice(-MAX_HISTORY_TURNS)` (`frontend/src/components/AIChatSidebar.tsx:46`). Combined effect is up to 40 messages sent if both caps drift. No bug today (both 20), but magic numbers duplicated. Fix: single constant or rely on backend only.

### Low

7. **Action models lack length limits; board-level check is the only net.** `CreateCard.title`, `UpdateCard.title/details`, `RenameColumn.title` accept any string length (`backend/app/models.py:61`); overlong input fails only after `apply_actions` builds the board and `Board.model_validate` rejects it. Works (all-or-nothing), but error surfaces as "AI changes are invalid" rather than a field error, and wastes a retry. Add `Field(max_length=...)` matching `Card`/`Column` limits.
8. **`parse_ai_content` fence-strip is brittle.** `removeprefix("```").strip()` then `cleaned[4:]` for "json" assumes no language tag variants (`jsonc`, whitespace). Strict `response_format` makes fences rare, and tests cover the common cases (`backend/tests/test_ai_chat.py:88`). Acceptable; consider regex `^```(?:json)?\s*|\s*```$`.
9. **`config.load_env_file` is a minimal parser.** Splits on first `=`, does not strip quotes, does not handle `export KEY=`. Fine for `OPENROUTER_API_KEY=...`, but a quoted key breaks silently (`backend/app/config.py:13`). Document expected format or use `python-dotenv` (adds dep; probably not worth it for MVP).
10. **`DB_PATH` read at import; `STATIC_DIR` resolved at import.** Tests monkeypatch `db.DB_PATH` (`backend/tests/conftest.py:9`) which works because handlers read the global per-request, but any module that captured the path at import would miss it. Current code is correct; keep the pattern (read global inside function, not default arg).
11. **`health` response contains filler `"message": "hello world"`** (`backend/app/routes.py:14`). Harmless, remove post-MVP or keep as version indicator.
12. **Frontend `isBoardData` is a shallow guard.** Checks `columns` array and `cards` object only (`frontend/src/components/KanbanBoard.tsx:21`); malformed column entries render until backend 400 on save. Backend is source of truth, so low risk. Could validate with Zod, overkill for MVP.
13. **Column title input `key={column.title}` remounts on every remote title change** (`frontend/src/components/KanbanColumn.tsx:74`). Intended (resync draft), but remounts mid-typing if AI renames the column being edited. Rare; acceptable.
14. **`createId` uses `crypto.randomUUID()`** (`frontend/src/lib/kanban.ts:164`) - good. Backend AI cards use `card-{uuid4}` (`backend/app/actions.py:44`). Both unguessable, no collision risk. Note IDs are long in DOM testids; fine.
15. **E2E drag test uses mouse coordinates** (`frontend/tests/kanban.spec.ts:93`). Works but flaky under CI load; dnd-kit `PointerSensor` with 6px activation is test-friendly. Keep.
16. **Docs drift (minor).** `docs/PLAN.md:320` quality-gate checkboxes unchecked though work is done; `CLAUDE.md:40` references `tests/test_persistence.py::test_name` which does not exist (actual files are `test_board_api.py` etc.). Fix the example command. `docs/DATABASE.md` and `kanban_schema.json` now match code (prior issue 11 fixed).
17. **Dependencies.** `backend/pyproject.toml` lower-bounds only (`fastapi>=0.115.0`); reproducibility comes from `uv.lock --frozen` in Docker, correct. Frontend `next 16.4.0`, React 19, `eslint-config-next 16.4.0` current. Prior review left 9 dev-only advisories (vitest chain); re-run `npm audit` periodically. `@types/node ^20` while Docker uses Node 24 - types still fine, consider bumping to ^24.

### Suggestions (post-MVP, do not implement now)

- Server-side session or API token; per-user board isolation test with second user.
- Optimistic-concurrency: `updated_at` etag on PUT, 409 on stale write.
- Retry with backoff on PUT failure + "Reload to resync" banner.
- `ORDER BY column_id, position` in `read_board`.
- Shared `MAX_HISTORY_TURNS` constant or backend-only trim.
- Pydantic length limits on action models.
- Fix `CLAUDE.md` test example path.

## Test evidence

- `uv run pytest -q` from `backend/`: 74 passed, 1 warning (Starlette `httpx` deprecation in `tests/helpers.py:1`, pre-existing).
- `npm run test:unit` from `frontend/`: 3 files, 19 tests passed.
- Did not run `npm run test:e2e` (requires Playwright browsers + ports) or Docker build in this pass; prior review verified both.

## Files reviewed

`AGENTS.md`, `CLAUDE.md`, `Dockerfile`, `.dockerignore`, `.gitignore`, `docs/PLAN.md`, `docs/DATABASE.md`, `docs/kanban_schema.json`, `docs/code_review.md`, `scripts/start.sh`, `scripts/start.ps1`, `scripts/stop.sh`, `scripts/stop.ps1`, `scripts/AGENTS.md`, `backend/pyproject.toml`, `backend/app/main.py`, `routes.py`, `models.py`, `actions.py`, `db.py`, `ai.py`, `config.py`, `backend/tests/conftest.py`, `helpers.py`, `test_board_api.py`, `test_ai_chat.py`, `test_actions.py`, `test_db.py`, `test_main.py`, `test_config.py`, `frontend/package.json`, `frontend/next.config.ts`, `frontend/playwright.config.ts`, `frontend/src/lib/kanban.ts`, `frontend/src/components/KanbanBoard.tsx`, `KanbanColumn.tsx`, `KanbanCard.tsx`, `NewCardForm.tsx`, `KanbanCardPreview.tsx`, `AIChatSidebar.tsx`, `AuthGate.tsx`, `frontend/src/app/page.tsx`, `frontend/tests/kanban.spec.ts`.
