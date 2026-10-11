# Code Review

Date: 2026-10-11
Scope: whole repo (backend, frontend, Docker, scripts, tests, docs).
Method: read all source, ran all test suites (backend 9, Vitest 11, Playwright 3 all pass), ran the Docker image end to end, and probed suspected defects against the backend directly. Items marked "verified" were reproduced; the rest are from reading the code.

Overall: the MVP works end to end and the code is small and readable. The main gaps are (1) data does not survive a container restart, (2) a required feature (card editing) is missing, (3) the board save path has several data-loss and race risks, and (4) nothing server-side protects the API or the paid AI endpoint.

## Remediation status (2026-10-11)

All 18 items were addressed and re-verified. Final results: backend pytest 25 passed; Vitest 19 passed; Playwright 10 passed; `npm run lint`, `tsc --noEmit` and `npm run build` clean; Docker image built, healthy, non-root, bound to 127.0.0.1, data survived a stop and start, and a live AI request created and moved cards.

| # | Status | What changed |
|---|--------|--------------|
| 1 | Fixed | Start scripts mount the `pm-mvp-data` volume at `/app/backend/data`; verified data survives stop and start. `DB_PATH` env var added. |
| 2 | Fixed | Cards have inline Edit (title and details) with unit and e2e tests. |
| 3 | Fixed | Load failure shows an error with Retry; seed data is never substituted. |
| 4 | Fixed | One `updateBoard` helper computes changes outside React updaters from a ref; saves go through a serialized queue and no longer overwrite state from the response. Chat waits for pending saves before sending. |
| 5 | Fixed | Column titles commit on blur or Enter; clearing the title restores the old one. |
| 6 | Fixed | Both start scripts publish `127.0.0.1:8000:8000`. |
| 7 | Fixed | One `Board` Pydantic model validates PUT, chat boards and AI updates (structure, ids, length limits) and returns 400 with a readable message. |
| 8 | Fixed | Cards are read sorted by position and grouped in Python; the `json_group_array` subquery is gone. |
| 9 | Fixed | The hand-written validator (with the dead check) was replaced by the `Board` model; tests cover non-list `cardIds`. |
| 10 | Fixed | Handlers are plain `def`, so blocking calls run in the threadpool. |
| 11 | Fixed | `init_db()` runs once in a lifespan handler; connections close; explicit board id; composite `(board_id, id)` keys; stored hash is SHA-256; `kanban_schema.json` and `DATABASE.md` match the code. |
| 12 | Fixed | Dockerfile uses `uv.lock` with `--frozen --no-dev`, `npm ci`, Node 24, a non-root user, a healthcheck, and a fuller `.dockerignore`. |
| 13 | Fixed | `backend/data/`, `*.db` and `frontend/test-results/` are ignored and the two tracked files are removed from the index (not committed). E2E uses a temporary database. |
| 14 | Fixed | E2E starts its own backend (8100) and frontend (3100) with `reuseExistingServer: false`, resets data before each test, and now covers logout, bad login, reload persistence for add, edit, delete, rename and move, and chat. Backend gained tests for invalid payloads, ordering, moves and deletes, unknown users, history handling and the OpenRouter request. Frontend gained tests for edit, cancel, load failure and retry, save failure, save ordering, and AI error handling. |
| 15 | Fixed | Dead code and the long placeholder page removed, referer corrected, model and URL are constants, Pydantic models replace manual checks. The prompt-injection note is documented in `backend/AGENTS.md`. |
| 16 | Fixed | Username is URL-encoded, no-op memo and unused env var removed, `AuthGate` reads the session with `useSyncExternalStore` (no form flash, and the lint error is gone), chat checks `ok` before parsing and limits history, `next.config.ts` explained, `crypto.randomUUID` ids, "1 card" grammar. Layout: the chat sidebar now sits beside the board only at `2xl`, and card buttons moved below the text so they no longer clip (checked with screenshots at 1280px). |
| 17 | Fixed | `backend/AGENTS.md`, `frontend/AGENTS.md`, `PLAN.md`, `kanban_schema.json`, `DATABASE.md`, `scripts/README.md` and `CLAUDE.md` updated. |
| 18 | Partly | `next` upgraded to 16.4.0 (with `eslint-config-next`): `npm audit --omit=dev` reports 0 vulnerabilities. Node 20 replaced by Node 24. 9 advisories remain in dev-only tooling (the vitest chain and `braces` via `eslint-config-next`); the vitest fix needs vitest 5, which does not install alongside the current Vite React plugin, so it was left. |

Known limits after remediation:
- An existing local `backend/data/kanban.db` created before this change keeps its old table definitions (it still works). Delete it to get the new schema.
- If the user edits the board while an AI reply is in flight, the AI update replaces the board when it arrives; saves made before sending are flushed first.
- Sign-in remains client-side only, per the MVP spec.

## Summary of actions

| # | Severity | Area | Action |
|---|----------|------|--------|
| 1 | High | Docker/scripts | Persist the SQLite DB outside the container |
| 2 | High | Frontend | Implement card editing (required by the spec, not present) |
| 3 | High | Frontend | Do not fall back to seed data on load failure |
| 4 | High | Frontend | Stop saving inside the `setBoard` updater; serialize saves |
| 5 | High | Frontend | Debounce column rename (one PUT per keystroke today) |
| 6 | High | Docker/scripts | Bind the published port to 127.0.0.1 |
| 7 | Medium | Backend | Validate the PUT payload fully (500s today) |
| 8 | Medium | Backend | Make card order explicit in the SQL |
| 9 | Medium | Backend | Fix `validate_ai_board_update` dead check |
| 10 | Medium | Backend | Do not block the event loop in async handlers |
| 11 | Medium | Backend | Pin DB lifecycle: init once, close connections |
| 12 | Medium | Docker | Reproducible, smaller, non-root image |
| 13 | Medium | Repo | Untrack `kanban.db` and `test-results`; isolate e2e data |
| 14 | Medium | Tests | Fill coverage gaps; make e2e independent of port 3000 and DB state |
| 15 | Low | Backend | Remove dead code and duplication |
| 16 | Low | Frontend | Small cleanups |
| 17 | Low | Docs | Update stale AGENTS.md files and PLAN.md checkboxes |
| 18 | Low | Dependencies | Address `npm audit` findings, Node 20 EOL |

## High severity

### 1. Board data is lost when the container is stopped
`scripts/start.*` runs `docker run --rm ... -p 8000:8000` with no volume. The DB lives at `/app/backend/data/kanban.db` inside the container, so `stop` followed by `start` resets the board to the seed data. This defeats the persistence requirement ("Kanban actions persist across refreshes and user sessions").
Action: mount a volume or host directory (for example `-v pm-data:/app/backend/data`) in `start.sh` and `start.ps1`; consider a `DB_PATH` env var so the path is explicit.

### 2. Cards cannot be edited
The spec says cards "can be moved with drag and drop, and edited". `KanbanCard.tsx` renders title, details and a Remove button only; there is no edit UI anywhere in `frontend/src/components`. Only the AI can change an existing card.
Action: add inline edit of title and details on the card (save through the existing board save path), with a unit test. Keep it minimal (click to edit, blur or Enter to save).

### 3. Load failure shows seed data, which the next edit then saves over real data
`KanbanBoard.tsx` (load effect): on any fetch error it calls `setBoard(initialData)`. The error banner appears, but the board is fully interactive; the first edit sends the seed board with edits to `PUT`, overwriting the user's real board once the backend recovers. `normalizeBoard` also returns `initialData` for a malformed payload.
Action: on load failure keep the board empty or disabled and show the error with a retry; never substitute `initialData` for server data. Keep `initialData` for tests only (or remove it from the production bundle).

### 4. Saves run inside the state updater and can race
In `handleDragEnd`, `handleRenameColumn`, `handleAddCard` and `handleDeleteCard`, `void saveBoard(nextBoard)` is called inside the `setBoard(prev => ...)` updater. Updaters must be pure: React StrictMode (and concurrent rendering) may run them twice, which sends duplicate PUTs. Separately, each `saveBoard` ends with `setBoard(normalizeBoard(payload))`, so responses arriving out of order, or after a newer local edit, overwrite newer state with older state. The same applies to `handleAIUpdate` landing while an edit is in flight.
Action: compute `nextBoard` from current state outside the updater, call `setBoard` and then save once; serialize saves (a single in-flight request with a "latest wins" queue) and do not overwrite local state from the PUT response unless it differs in a way that matters. A `useRef` holding the latest board is enough; no library needed.

### 5. Column rename saves on every keystroke
`KanbanColumn.tsx:44` calls `onRename` from `onChange`, so typing "Review" sends six PUTs of the whole board, compounding item 4 (out-of-order responses can revert text mid-typing).
Action: keep local input state and commit on blur or Enter, or debounce.

### 6. The container API is reachable from the network and spends the OpenRouter key
`-p 8000:8000` publishes on all interfaces. `/api/ai/chat` and the board endpoints have no server-side auth, so anyone on the LAN can read or overwrite the board and call the AI on the user's key.
Action: publish as `-p 127.0.0.1:8000:8000` in both start scripts (the app is local-only by design).

## Medium severity

### 7. PUT board validation is incomplete (verified: HTTP 500)
`validate_fixed_columns` only checks the column ids. Reproduced against the API: a `cardId` with no entry in `cards`, a card id listed in two columns, a null column title, and a card missing `title` each return 500 with a bare "Internal Server Error". The transaction rolls back, so data is not corrupted (verified), but the client gets no useful message. A 2 MB card detail is also accepted (no size limits).
Action: reuse the stricter checks from `validate_ai_board_update` for PUT as well (one validator for both paths, returning 400), and add reasonable length limits on title and details.

### 8. Card order inside a column relies on insertion order
In `fetch_board_for_user`, `json_group_array(card.id)` is aggregated in a correlated subquery and the `ORDER BY card.position` is applied to the single-row result, not to the aggregation, so it has no effect. Order currently comes out right only because rows are saved in position order and scanned in rowid order (verified: reorder round-trips). Any later partial update or index change can break it silently.
Action: drop the aggregate; select cards ordered by `(column_id, position)` and build `cardIds` in Python, or use an ordered subquery. The code already fetches all cards sorted by position, so the `card_ids` column can simply be derived from that.

### 9. `validate_ai_board_update` has a dead check
In the loop over columns, the `cardIds` list-of-strings check is indented under the `raise` of the preceding `if` and never executes. A column with `cardIds: "abc"` or non-string ids passes this step (later set operations may still reject it, but with unrelated errors). Fix the indentation and add a test.

### 10. Blocking calls inside `async def` handlers
`ai_chat` is `async def` but calls `httpx.post` (up to 60 s) and synchronous sqlite, which blocks the event loop and stalls all other requests during an AI call. The board GET and PUT handlers are also `async def` with sync sqlite.
Action: make these handlers plain `def` (FastAPI runs them in a threadpool), or use `httpx.AsyncClient`. Plain `def` is the simplest.

### 11. Database lifecycle
- `init_db()` runs at import, at startup, and on every `fetch_board_for_user` and `save_board_for_user` (and `save` calls `fetch`, so twice per save). Run it once at startup.
- `with sqlite3.connect(...)` commits but does not close; connections are never closed. Use `contextlib.closing` or a small context manager.
- `@app.on_event("startup")` is deprecated (pytest shows the warning); use a lifespan handler.
- `save_board_for_user` reads `board_record["id"] if hasattr(...) else ...` after an INSERT that returns a cursor. This works only by accident (cursors have no `__getitem__`, so it takes the f-string fallback). Replace with an explicit board id.
- Primary keys on `cards` and `columns` are global (`id TEXT PRIMARY KEY`), so a second user's board cannot reuse `card-1` or `col-backlog`. This conflicts with the multi-user goal; make the key `(board_id, id)` or generate unique ids before adding users.
- `password_hash` stores the literal `"password"`. Harmless for the MVP but misleading; either hash it or name the intent in a comment.
- The schema in `docs/kanban_schema.json` (INTEGER ids) does not match the code (TEXT ids); update one of them.

### 12. Dockerfile
- `uv.lock` is not copied and `uv sync` is run without `--frozen`, so builds are not reproducible, and dev dependencies (pytest) are installed in the runtime image. Use `COPY backend/pyproject.toml backend/uv.lock` and `uv sync --frozen --no-dev`.
- Frontend stage uses `npm install` where `npm ci` is correct for a lockfile build.
- The container runs as root; add a non-root user (and make the data directory writable by it).
- `node:20-alpine`: Node 20 is end of life as of this date; move to a supported LTS.
- No `HEALTHCHECK`; `/api/health` exists and is the natural target.
- `.dockerignore` does not exclude `frontend/out`, `backend/data` or `.env`; the current COPY lines make this harmless, but it is one edit away from leaking.

### 13. Repo hygiene
- `backend/data/kanban.db` and `frontend/test-results/.last-run.json` are committed (commit 7d57774). Add `backend/data/`, `*.db`, `frontend/test-results/` to `.gitignore` and `git rm --cached` them. A committed DB means every dev run creates a diff and a real board could be published.
- `playwright.config.ts` is fine, but `npm run test:e2e` against the real dev DB modifies it (the "adds a card" test leaves a card behind every run; the "moves a card" test permanently moves `card-1`, so reruns pass trivially). See item 14.

### 14. Test gaps
Existing tests are decent for happy paths. Missing or weak:
- E2E depends on port 3000 being free: `reuseExistingServer: true` silently reused an unrelated site during this review, failing all 3 tests with a misleading "Username not found". Set `reuseExistingServer: false` (or use an uncommon port) so a conflict fails loudly.
- E2E does not start the backend, does not reset data, and does not cover: logout, reload persistence, rename persistence, delete, the AI chat flow (even with a mocked backend), or card editing (once added).
- Backend: no tests for PUT with malformed cards (item 7), the dead check (item 9), `/api/health`, or an AI request with a client board that differs from the stored one.
- Frontend: no test for the load-failure path (item 3), save failure banners, or concurrent saves (item 4); the AI sidebar has no direct component test (only an indirect one via the board test).
- Use a temp `DB_PATH` for e2e (env var) so tests never touch the developer's data.

## Low severity

### 15. Dead code and duplication (backend)
- `board_from_rows` is unused.
- `fetch_board_for_user` builds `card_map` and `board_data` with redundant `str()` conversions (ids are already text).
- `ai_chat` and `query_openrouter` each re-check types FastAPI already enforces (`payload: dict` is always a dict); consider small Pydantic models for board, card and chat request, which would also remove most hand validation in items 7 and 9. This is the one structural change worth making, since it replaces ~60 lines of manual checks.
- The HTML placeholder page in `configure_static` is ~45 lines used only when no static build exists; keep it a one-liner or drop it.
- The OpenRouter call hardcodes `HTTP-Referer: http://localhost:3000`; the app is served on 8000.
- The model name and URL are inline constants; fine for the MVP, but a module-level constant would help tests.
- Prompt injection: card text is passed to the model as data. This is acceptable here because the output is schema-validated and only changes this user's board, but note that a card can make the AI rewrite or delete other cards.

### 16. Frontend cleanups
- `KanbanBoard.tsx`: `cardsById = useMemo(() => board.cards, ...)` is a no-op memo; use `board.cards` directly. `getBoardUrl` does not `encodeURIComponent(username)`. `NEXT_PUBLIC_API_BASE_URL` is read but never set anywhere.
- `AuthGate.tsx`: the auth flag in `localStorage` is a client-only gate (acceptable for the MVP per the spec) but a sign-in screen flash occurs before the effect reads storage; render nothing until hydrated. Use a `type` for the form event instead of `React.FormEvent`.
- `AIChatSidebar.tsx`: the response is parsed with `response.json()` before checking `ok`, so a non-JSON error (proxy 502, HTML) shows a parse error instead of the HTTP status. It sends the whole board and history on each call (fine now, but history is unbounded).
- `next.config.ts`: Next warns that `rewrites` are ignored with `output: "export"`. They work under `next dev` only, which is what they are for; add a one-line comment, and declare `backendUrl` above its use.
- `createId` uses `Math.random`; fine for client card ids, but `crypto.randomUUID()` is simpler and collision-free.
- Layout: the five-column grid is `lg:grid-cols-5` inside a container that also holds a 320 px sidebar at `xl`, so columns are narrow at 1280 px. Worth a visual check.

### 17. Documentation
- `backend/AGENTS.md` still says "initial scaffolding... not yet connected to SQLite". `frontend/AGENTS.md` says the app is a demo not connected to the backend, and its "Important constraints" section contradicts the rest of the file; it also links the e2e test as `../tests/kanban.spec.ts` (wrong path).
- `docs/PLAN.md`: Parts 1-7 have unchecked checklists although the work is done; status line says "through Part 10 complete".
- `docs/kanban_schema.json` and the actual tables differ (item 11).
- `scripts/README.md` should mention the data volume once item 1 is done.

### 18. Dependencies
- `npm audit --omit=dev` reports findings (a high-severity `nanoid` advisory and a moderate `baseline-browser-mapping` one, both transitive). Run `npm audit fix`, re-run the tests, and review what remains.
- Backend dependencies are lower-bounded only (`fastapi>=0.115.0`); the lockfile fixes versions once `--frozen` is used (item 12).

## What is good
- Single-file backend is easy to follow and the AI contract is minimal: `{reply, boardUpdate}`, validated before anything is saved. Malformed AI output is rejected without touching the board (covered by tests).
- Saves are transactional: failed PUTs leave the previous board intact (verified).
- Backend tests isolate the DB with a temp path; the AI tests mock the HTTP call.
- Frontend logic for moves is isolated in `lib/kanban.ts` with unit tests; components are small.
- `.env` is gitignored and not copied into the image.

## Suggested order of work
1. Items 1 and 6 (two-line script changes, big impact).
2. Items 3, 4, 5 together (one refactor of the save path in `KanbanBoard.tsx`), then item 2 (card editing) on top of it.
3. Items 7, 8, 9, 10, 11 together as a backend pass; consider Pydantic models here.
4. Items 12 and 13 (Docker, gitignore).
5. Item 14 tests for everything changed above.
6. Items 15-18 as cleanup.
