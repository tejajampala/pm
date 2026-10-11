# Database approach

## Goal

Store the kanban board and user relationship in SQLite in a way that matches the MVP requirements while leaving room for future multi-user and multi-board expansion.

## Why SQLite

- The app is designed to run locally in a Docker container.
- SQLite is simple to operate, requires no external service, and is a natural fit for a small MVP.
- The data model remains easy to evolve if the project later grows to support more users or more boards per user.

## Proposed schema

The schema is captured in [kanban_schema.json](kanban_schema.json).

### Users

Tracks the authenticated account. For the MVP, there is only one hardcoded sign-in user, but the database is shaped for future real user support.

### Boards

Represents the project board created for a user. The MVP supports only one board per user, but this table is already structured for future multi-board scenarios.

### Columns

Stores each board column and its order. This keeps the board flexible while still supporting the fixed-column structure used in the UI.

### Cards

Stores each card with its title, details, and column placement. `position` is important for drag-and-drop ordering within a column.

## Data model decisions

- Ids are text. Columns and cards use a per-board key `(board_id, id)`, so different boards can reuse ids such as `card-1`.
- Each card belongs to one board and one column.
- Each column belongs to one board.
- Each board belongs to one user.
- Order is stored as an integer position and read by sorting on it, not by insertion order.
- Titles are mutable, which fits the requirement that fixed columns can be renamed.

## MVP assumptions

- There is only one board per user.
- User sign-in is still hardcoded as `user` / `password` for the MVP.
- The database initializes automatically at startup if it does not already exist. In Docker it lives in the `pm-mvp-data` volume so it survives restarts.
- Card updates, column renames, and drag-and-drop moves are persisted through backend API calls.

## Future extension path

The schema supports straightforward growth toward:

- multiple users with secure auth
- multiple boards per user
- more complex card metadata
- audit history or timestamps for board changes

This keeps the design small now without forcing a rewrite later.
