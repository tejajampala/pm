# Frontend agent guide

## Overview

Next.js (static export) single-board Kanban UI. It signs in with the hardcoded demo user, loads and saves the board through the backend API, and includes an AI chat sidebar. In Docker, FastAPI serves the build and `/api` on one origin; under `next dev`, `/api/*` is proxied to `BACKEND_API_URL` (default `http://127.0.0.1:8000`).

## Structure

- [src/app/page.tsx](src/app/page.tsx) renders `AuthGate`.
- [src/components/AuthGate.tsx](src/components/AuthGate.tsx) checks `user` / `password` in the browser, keeps the session flag in `localStorage` (read with `useSyncExternalStore`, so nothing renders until the session is known), and provides logout.
- [src/components/KanbanBoard.tsx](src/components/KanbanBoard.tsx) owns board state. It loads the board (an error with Retry is shown on failure; it never falls back to seed data), applies changes through one `updateBoard` helper, and saves the full board with a serialized queue so PUTs run one at a time, in order. It also handles drag and drop (dnd-kit) and applies AI updates (already saved by the backend).
- [src/components/KanbanColumn.tsx](src/components/KanbanColumn.tsx) renders a column; the title input saves on blur or Enter, not per keystroke.
- [src/components/KanbanCard.tsx](src/components/KanbanCard.tsx) shows a card with inline Edit and Remove.
- [src/components/NewCardForm.tsx](src/components/NewCardForm.tsx), [KanbanCardPreview.tsx](src/components/KanbanCardPreview.tsx) are the add form and drag overlay.
- [src/components/AIChatSidebar.tsx](src/components/AIChatSidebar.tsx) waits for pending saves, sends board, last 20 messages and the prompt to `/api/ai/chat`, and shows errors.
- [src/lib/kanban.ts](src/lib/kanban.ts) has the board types, seed data (`initialData`, used by tests), `moveCard`, and `createId`.

## State model

`{ columns: [{id, title, cardIds}], cards: { [id]: {id, title, details} } }`, shared with the backend. The five column ids are fixed.

## Layout

The chat sidebar sits beside the board only at the `2xl` breakpoint; below that it stacks under the board so five columns stay readable.

## Tests

- `npm run test:unit`: Vitest and React Testing Library (`src/**/*.test.ts(x)`).
- `npm run test:e2e`: Playwright. The config starts its own backend (port 8100, temporary database, AI key blanked) and dev server (port 3100) and never reuses an existing server. Each test resets the board through the API first.
- `npm run lint`, `npm run build` (type-checks tests too).

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
