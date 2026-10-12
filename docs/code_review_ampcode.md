# Code Review - Amp

Date: 2026-10-12
Scope: the whole repository at commit `e54f5b6` (backend, frontend, Dockerfile, scripts, tests, docs).
Method: read every tracked source, test, config and doc file; ran the test suites; probed suspected defects with throwaway scripts against the real FastAPI app and the real React components (removed afterwards). Findings marked "verified" were reproduced; the rest come from reading the code.

## Verdict

The MVP meets the business requirements in `AGENTS.md`: sign-in, one board per user, five fixed renamable columns, card add/edit/delete/drag-and-drop, persistence in SQLite, and an AI sidebar that creates, edits, moves and deletes cards through validated structured actions. The code is small, readable and consistent, and the earlier review (`docs/code_review.md`) was remediated well.

The remaining problems are concentrated in two places:

1. Concurrency between the AI chat and manual edits, which can silently undo a user's change in both the UI and the database.
2. Validation gaps between frontend and backend, one of which can leave the board unsaveable for the rest of the session.

Nothing found is a blocker for a local single-user MVP, but items 1 to 3 below are real data-loss or stuck-state bugs and are cheap to fix.

## Checks run

| Check | Result |
|---|---|
| `uv run pytest` (backend) | 74 passed, 1 warning (Starlette deprecation of `httpx` with `TestClient`) |
| `vitest run` (frontend) | 19 passed |
| `npm run lint` | clean |
| `tsc --noEmit` | clean |
| Playwright e2e, Docker build | not run in this pass |

## Summary of findings

| # | Severity | Area | Finding |
|---|---|---|---|
| 1 | High | Frontend + backend | Edits made while an AI request is in flight are lost (verified) |
| 2 | High | Frontend | One over-long field makes every later save fail for the session (verified) |
| 3 | Medium | Backend | Malformed JSON from the model is not retried, contrary to the docs (verified) |
| 4 | Medium | Scripts | `start.ps1` reports success after a failed build or run (verified) |
| 5 | Medium | Backend | No server-side auth; API trusts the username in path/body |
| 6 | Low | Backend | Whitespace-only titles accepted by `PUT` (verified) |
| 7 | Low | Backend | Chat runs the paid model call before checking the user exists (verified) |
| 8 | Low | Backend | Chat history size and content are unbounded at the API (verified) |
| 9 | Low | Backend | Error status codes and layering |
| 10 | Low | Backend | Unneeded complexity in `init_db` and misleading timestamp columns |
| 11 | Low | Frontend | Small UX and accessibility gaps |
| 12 | Low | Docker / scripts | Build and script hygiene |
| 13 | Low | Tests | Gaps and leftovers |
| 14 | Low | Docs | Drift between docs and code |

## High

### 1. Edits made while an AI request is in flight are lost (verified)

`AIChatSidebar` posts the `board` snapshot taken when Send is clicked ([AIChatSidebar.tsx](../frontend/src/components/AIChatSidebar.tsx) lines 36-48). The board stays fully editable during the request, which can take up to two model calls of up to 60 s each. When the reply arrives:

- the backend has applied the AI actions to the old snapshot and saved that whole board ([routes.py](../backend/app/routes.py) lines 59-65), overwriting any `PUT` the user made in the meantime;
- the frontend replaces `boardRef` and state with the returned board ([KanbanBoard.tsx](../frontend/src/components/KanbanBoard.tsx) lines 200-204).

Reproduced with a throwaway Vitest test: send a chat message, delete a card while the request is pending (the `PUT` is sent), then let the AI respond. The deleted card reappears. From the code, the database ends up the same way, because the AI save replaces the whole board (not separately reproduced). If the user's `PUT` instead lands after the AI save, the database and the screen disagree until the next edit.

`docs/code_review.md` lists this as a known limit, but it undoes user changes silently, and the fix is small:

- Simplest and sufficient: make the board read-only while `isSending` is true (lift `isSending` into `KanbanBoard`, disable the DnD context and the edit, add, remove and rename controls). Both writers then never overlap.
- Separately, consider dropping `board` from `ChatRequest` and always reading the stored board in `ai_chat`. The frontend already flushes pending saves before sending, so the stored board is current, and the chat endpoint would no longer let a client overwrite the stored board with an arbitrary one. This alone does not fix the race, because edits made during the model call would still be replaced by the full-board save.

### 2. One over-long field makes every later save fail for the session (verified)

The backend limits card titles to 200 characters, details to 5000 and column titles to 100 ([models.py](../backend/app/models.py) lines 9-18). None of the frontend inputs have matching `maxLength` ([NewCardForm.tsx](../frontend/src/components/NewCardForm.tsx), [KanbanCard.tsx](../frontend/src/components/KanbanCard.tsx), the column title input in [KanbanColumn.tsx](../frontend/src/components/KanbanColumn.tsx)).

Because every save sends the whole board and the optimistic update stays in `boardRef` on failure ([KanbanBoard.tsx](../frontend/src/components/KanbanBoard.tsx) lines 104-120), one 201-character title makes that save fail with 400 and every later save fail too, since each one still carries the invalid card. Verified against the API: the first `PUT` returns `400 cards.card-1.title: String should have at most 200 characters`, and a follow-up `PUT` with an unrelated change also returns 400. The user sees a generic "Unable to save ..." banner, keeps editing, and loses every change made since the failure on reload.

Fix: add `maxLength` to the three inputs, matching the backend limits. Optionally, on a failed save, reload the board from the server instead of keeping the unsaved state.

## Medium

### 3. Malformed JSON from the model is not retried (verified)

`parse_ai_content` raises `HTTPException(400)` for non-JSON or non-object output ([ai.py](../backend/app/ai.py) lines 61-67). That exception escapes `run_ai_request` before its `try` block ([routes.py](../backend/app/routes.py) line 37), so the retry loop never sees it. Verified: with the model returning `not json`, the endpoint returns `400 AI response was not valid JSON.` after one model call.

`backend/AGENTS.md` and `CLAUDE.md` both say a malformed AI response is sent back to the model once. Strict structured output makes this rare, but it is exactly the failure the retry exists for. Fix: have `parse_ai_content` raise `ValueError` (or return the raw string) and handle it inside the loop alongside the `ValidationError` case, then add one test for it.

### 4. `start.ps1` reports success after a failure (verified)

In Windows PowerShell 5.1, `$ErrorActionPreference = "Stop"` does not stop on a failing native command (verified: `cmd /c exit 1` continues with `$LASTEXITCODE = 1`). So if `docker build` fails, [start.ps1](../scripts/start.ps1) still runs the previous image, and if `docker run` fails (for example because the container is already running) it still prints "Project Management MVP is running". Fix: check `$LASTEXITCODE` after each `docker` call and `exit 1` on failure.

Related:

- Both start scripts fail with a name conflict if the app is already running; calling the stop logic first (or `docker rm -f` before `run`) makes start idempotent.
- Both require `.env` to exist (`--env-file`), although the backend handles a missing key gracefully.
- On this machine the default execution policy blocks `.ps1` files; `scripts/README.md` could mention `powershell -ExecutionPolicy Bypass -File scripts\start.ps1`.

### 5. No server-side auth

Sign-in is checked in the browser only ([AuthGate.tsx](../frontend/src/components/AuthGate.tsx) lines 31-36) and the API trusts the `username` in the path and request body ([routes.py](../backend/app/routes.py) lines 22-29, 58). This is within the MVP brief, and the start scripts bind to `127.0.0.1`, which is the right mitigation. Good: JSON bodies require `Content-Type: application/json`, so plain cross-site form posts cannot reach the API, and React escapes all rendered text.

Residual risk worth stating in the docs: any local process, or a DNS-rebinding page, can read and write the board and spend OpenRouter credits. When real users arrive, a session cookie set by a `POST /api/login` and checked in a dependency is the smallest step up.

## Low

### 6. Whitespace-only titles accepted by `PUT` (verified)

`Card.title` and `Column.title` use `min_length=1` without stripping, so `"   "` is stored ([models.py](../backend/app/models.py) lines 11, 17). The UI trims, and AI actions are stripped in `apply_actions`, so only direct API calls are affected. Fix: use `StringConstraints(strip_whitespace=True, min_length=1, ...)` as `ChatRequest.message` already does.

### 7. Chat calls the model before checking the user (verified)

When the request includes a `board`, `ai_chat` skips the database read, calls OpenRouter, and only then gets a 404 from `save_board_for_user` for an unknown user. Verified: one model call, then 404. Resolving the board id first (or the change suggested in item 1) fixes it.

### 8. Chat history is unbounded at the API (verified)

`ChatTurn.content` has no length limit and `history` has no item limit ([models.py](../backend/app/models.py) lines 40-49). The backend trims to the last 20 entries only when forwarding, so a 10 MB history is accepted and parsed (verified: 200). Adding `max_length` to `content` and to `history` is enough. Note also that "20 turns" in the docs is really 20 messages, about 10 exchanges, and that a failed send leaves a user message without a reply in the history.

### 9. Error status codes and layering

- An AI answer that is still unusable after the retry returns 400, which reads as a client error; 502 matches the other upstream failures in `ai.py`.
- `db.py` and `ai.py` raise FastAPI `HTTPException`, which ties the data and AI layers to the web framework. Acceptable at this size; worth changing if these modules grow.
- `query_openrouter` returns OpenRouter's raw error text to the browser. Fine locally.

### 10. Unneeded complexity in `init_db`; misleading timestamps

- `init_db` restores any missing fixed column and rewrites column positions on every start ([db.py](../backend/app/db.py) lines 105-121). The `Board` validator makes a missing column impossible through the API, so this only serves pre-existing development databases. Given the "never over-engineer" rule, a plain "seed if the board does not exist" would do, along with its `test_db.py` legacy test.
- `save_board_for_user` deletes and re-inserts every column and card on each save, so `cards.created_at`, `cards.updated_at` and `columns.created_at` are reset on every drag. The columns exist in the schema docs but carry no meaning. Either drop them or stop claiming them.
- Seed data is duplicated in `db.get_default_board()` and `frontend/src/lib/kanban.ts` (`initialData`, used only by tests). They can drift.

### 11. Frontend UX and accessibility

- New cards without details are saved with the literal text "No details yet." ([KanbanBoard.tsx](../frontend/src/components/KanbanBoard.tsx) line 158), so the placeholder becomes data that the AI sees and the edit form shows. Store an empty string and show a placeholder when rendering.
- Only `PointerSensor` is configured, so cards cannot be moved with the keyboard even though dnd-kit gives them `role="button"` and focus. Adding `KeyboardSensor` with `sortableKeyboardCoordinates` is a few lines.
- No `onDragOver`, so a card does not preview in the target column while dragging between columns. Acceptable for an MVP.
- Remove deletes immediately with no undo or confirmation.
- The chat `fetch` has no timeout or cancel; with two 60 s model calls the UI can show "Thinking..." for two minutes.

### 12. Docker and script hygiene

- `pip install uv` is unpinned; `COPY --from=ghcr.io/astral-sh/uv:<version> /uv /bin/uv` is the documented, reproducible way.
- `backend/app` is copied before `uv sync`, so any code change reinstalls all dependencies. Run `uv sync --frozen --no-dev --no-install-project` before copying the app, then sync again.
- `layout.tsx` uses `next/font/google`, so the image build needs network access to Google Fonts.

### 13. Tests

The suites are good overall: isolated temp database per backend test, the AI mocked at two levels, invalid-payload tables, ordered-save and failure tests in Vitest, and e2e on dedicated ports with a throwaway database. Gaps:

- No test for invalid JSON from the model, which is how item 3 went unnoticed.
- No test for the AI-in-flight race (item 1) or for oversized input in the UI (item 2).
- `test_ai_chat_uses_stored_board_and_trims_history` sends 3 history entries, so it does not test trimming.
- [test_ai_chat.py](../backend/tests/test_ai_chat.py) has seven blank lines (30-36) left from removed tests.
- `moveCard` tests do not cover a same-column drop on the column (move to end) or the no-op cases.
- The Starlette warning says `TestClient` with `httpx` is deprecated; it will need attention on the next Starlette upgrade.

### 14. Docs drift

- `CLAUDE.md` gives `uv run pytest tests/test_persistence.py::test_name` as the example; that file does not exist.
- `backend/AGENTS.md` and `CLAUDE.md` say malformed AI responses are retried (see item 3).
- `CLAUDE.md` and `PLAN.md` say all review items are fixed, while `code_review.md` lists the AI race as a known limit; this review treats it as a bug.
- The quality-gate checkboxes at the end of `docs/PLAN.md` are unchecked although every part is marked done.

## Notes on `docs/code_review_opencode_muse.md`

Most of that review agrees with this one (auth, the client-supplied chat board, history limits, docs drift). Three points are not correct as written:

- Its item 4 calls the card query fragile. `ORDER BY position` across columns is fine: `read_board` groups rows by `column_id` in Python, and rows from one column keep their relative position order. No change needed.
- Its item 5 suggests reseeding cards when a board has columns but no cards. An empty board is a valid user state; reseeding would resurrect cards the user deleted.
- Its item 3 says a second queued save overwrites a first one that failed. Every save sends the whole board, so the later save includes the earlier change; the real stuck-save problem is item 2 above.

## What is good

- One Pydantic `Board` model is the single contract for `PUT`, chat boards and AI results, with readable 400 errors.
- The AI never returns a whole board: small typed actions, applied in order to a deep copy, all or nothing, then validated with `Board`. Strict JSON-schema output with `require_parameters`, one informed retry, and a "Changes made" list built from what was actually applied rather than what the model claims.
- SQLite access is simple and correct: one transaction per request, rollback on error, connections closed, plain `def` handlers so blocking calls run in the threadpool, composite `(board_id, id)` keys.
- The frontend funnels all edits through one `updateBoard` with a serialized save queue, never falls back to seed data on load failure, and commits column renames on blur or Enter.
- The Docker image is multi-stage, uses `uv.lock` and `npm ci`, runs as a non-root user, has a healthcheck, and persists data in a named volume bound to localhost only.

## Recommended order of work

1. Item 2 (add `maxLength`): minutes, removes a stuck state.
2. Item 1 (lock the board during chat, or base AI actions on the stored board).
3. Item 3 (retry invalid JSON) with one test.
4. Item 4 (exit-code checks in `start.ps1`).
5. Items 6 to 8 together in `models.py` and `routes.py`.
6. Docs fixes (item 14).
