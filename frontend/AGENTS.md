# Frontend agent guide

## Overview

This frontend is a Next.js demo app for a single-board Kanban project management interface. It is currently a static frontend-only MVP and has not yet been integrated with authentication, a database, or the backend API.

## Current app structure

- [src/app/page.tsx](src/app/page.tsx)  
  The homepage renders the Kanban board component.

- [src/components/KanbanBoard.tsx](src/components/KanbanBoard.tsx)  
  Main board container. It loads and saves board state through the backend, manages drag-and-drop, column renaming, card creation/deletion, and applies AI board updates.
- [src/components/AIChatSidebar.tsx](src/components/AIChatSidebar.tsx)  
  Board-aware AI chat UI. It sends the current board and conversation history to the backend and applies returned board updates.

- [src/components/KanbanColumn.tsx](src/components/KanbanColumn.tsx)  
  Renders one column with its title, cards, and a form for adding cards.

- [src/components/KanbanCard.tsx](src/components/KanbanCard.tsx)  
  Displays a card in the board UI and supports card editing behavior.

- [src/components/KanbanCardPreview.tsx](src/components/KanbanCardPreview.tsx)  
  Drag overlay preview used during drag operations.

- [src/components/NewCardForm.tsx](src/components/NewCardForm.tsx)  
  Form used to create new cards inside a column.

- [src/lib/kanban.ts](src/lib/kanban.ts)  
  Contains the board data model, initial seed data, card movement logic, and helper functions.

## State model

The board data is loaded from and persisted to the backend, with React state keeping the current view responsive. The structure is:

- columns: ordered column list with id, title, and cardIds
- cards: record keyed by card id, each containing id, title, and details

The move logic supports moving cards:

- between columns
- within the same column
- to specific positions in a list

## Current behavior

The existing demo includes:

- a five-column Kanban layout
- placeholder project cards with text content
- drag-and-drop card movement
- column renaming
- card creation and deletion
- a visual card drag overlay
- demo sign-in and logout
- OpenRouter-backed board chat for card creation, editing, and movement

## Testing setup

- [src/lib/kanban.test.ts](src/lib/kanban.test.ts)  
  Unit tests covering kanban logic and board movement behavior.

- [src/components/KanbanBoard.test.tsx](src/components/KanbanBoard.test.tsx)  
  Component tests for the board UI.

- [tests/kanban.spec.ts](../tests/kanban.spec.ts)  
  End-to-end browser-style test coverage for the Kanban experience.

The project uses:

- Vitest for unit tests
- React Testing Library for component tests
- Playwright for browser-level tests

## Important constraints for future work

- This is a demo-only frontend; it is not yet connected to the backend or database.
- Auth is not yet implemented and there is no user-specific board state.
- The board data is local only and resets on refresh.
- The project is expected to evolve toward a Dockerized, FastAPI-backed, SQLite-persisted app, but the current frontend is still the standalone demo.

## Working approach

When implementing future phases, preserve the current board behavior while progressively replacing the local in-memory state with backend-backed persistence, adding auth, and then integrating AI-driven board actions.
