# Project Management MVP Execution Plan

Status: user-approved; AI implementation through Part 10 is complete.

## Goal

Build the MVP described in [AGENTS.md](../AGENTS.md): a local Dockerized Project Management app with a sign-in screen, a single Kanban board per user, editable/movable cards, renameable fixed columns, and an AI sidebar that can create, update, and move cards via structured outputs.

## Current state

The frontend already contains a static demo Kanban board in the Next.js app, with drag-and-drop logic and a test setup already in place. The backend, Docker scaffolding, authentication, persistence, and AI integration are not yet implemented.

---

## Part 1: Planning and repo readiness

Checklist:

- [ ] Confirm the business requirements and constraints from [AGENTS.md](../AGENTS.md)
- [ ] Review the existing frontend implementation in [frontend](../frontend)
- [ ] Document the current frontend architecture in [frontend/AGENTS.md](../frontend/AGENTS.md)
- [ ] Expand this plan with detailed phases, checklists, test expectations, and success criteria
- [ ] Pause for user approval before starting implementation work

Tests:

- None required for planning-only work beyond verifying the repo docs are present and readable

Success criteria:

- The plan clearly explains each phase in order
- The frontend AGENTS file accurately maps the current code structure
- The user explicitly approves the plan before moving to scaffolding

---

## Part 2: Scaffolding and local runtime

Objective:

Set up the local runtime so the app can be started in Docker and a minimal FastAPI + static serving setup is proven working.

Checklist:

- [ ] Create the Docker configuration for the app container
- [ ] Add Python project setup using uv in the backend runtime
- [ ] Create the FastAPI application entrypoint and minimal health route
- [ ] Serve a basic static page at / to confirm the app runs locally
- [ ] Add a backend API endpoint returning a simple response to confirm connectivity
- [ ] Add start/stop scripts in [scripts](../scripts) for Mac, Windows, and Linux
- [ ] Validate the app boots successfully in the local environment

Tests:

- [ ] Run the app locally and confirm the root route returns the expected static page
- [ ] Hit the backend health/API route and confirm a successful response
- [ ] Verify the container startup and shutdown scripts do not fail

Success criteria:

- The app starts reliably in Docker locally
- A basic root page is served successfully
- A basic API call succeeds from the backend
- The runtime is stable enough to support the subsequent frontend integration work

---

## Part 3: Frontend integration and static serving

Objective:

Integrate the working frontend demo into the app so it is served as the production web app at /.

Checklist:

- [ ] Confirm the existing Next.js app can be built for production
- [ ] Update the app wiring so the built static frontend is served by FastAPI at /
- [ ] Preserve the demo Kanban board view and drag-and-drop interactions
- [ ] Ensure the frontend route works correctly in production mode
- [ ] Add or update unit tests for board behavior and rendering
- [ ] Add or update integration tests covering the app homepage

Tests:

- [ ] Run the frontend unit tests for kanban logic
- [ ] Run frontend integration or browser tests to confirm the board renders
- [ ] Build the frontend and verify production output is generated without errors

Success criteria:

- The app shows the Kanban board at the root route
- The frontend builds cleanly in production mode
- The existing demo functionality remains intact while being served by the containerized app

---

## Part 4: Fake sign-in experience

Objective:

Add the MVP authentication flow using the fixed dummy credentials user / password, with logout behavior and protected board access.

Checklist:

- [ ] Define the sign-in page and flow for first-time access as a hardcoded auth check
- [ ] Implement dummy login credentials: user / password
- [ ] Prevent access to the Kanban until a valid login occurs
- [ ] Add a logout action to return to the sign-in screen
- [ ] Store the sign-in state in a simple browser/session mechanism suitable for the MVP
- [ ] Add tests covering valid login, invalid login, and logout behavior

Tests:

- [ ] Attempt unauthenticated access and confirm redirect to sign-in
- [ ] Sign in with valid credentials and confirm the board loads
- [ ] Sign in with invalid credentials and confirm failure state
- [ ] Log out and confirm the user is returned to the sign-in flow

Success criteria:

- Only authenticated users can view the board
- The login experience matches the MVP requirement without over-engineering
- The sign-in and logout flows are covered by automated tests

---

## Part 5: Database modeling and schema approval

Objective:

Design a SQLite-backed data model for the Kanban board and the user relationship, then get explicit approval before backend persistence work begins.

Checklist:

- [ ] Define a minimal data model for users, boards, columns, cards, and optional metadata
- [ ] Ensure the design supports future multi-user extension without adding unnecessary complexity now
- [ ] Save the schema definition as JSON in the docs folder
- [ ] Document the database approach in docs with the rationale and constraints
- [ ] Present the schema to the user for sign-off
- [ ] Do not start persistence implementation until approval is granted

Tests:

- [ ] Validate that the schema file is valid JSON
- [ ] Check the schema matches the MVP requirements and future extensibility expectations

Success criteria:

- The schema captures the board structure in a clear, reviewable format
- The user approves the database model before backend implementation begins
- The implementation plan is aligned with the stored schema and MVP constraints

---

## Part 6: Backend persistence API

Objective:

Implement the FastAPI API to read and update the Kanban for a given user, with SQLite auto-initialization if the database does not yet exist.

Checklist:

- [ ] Create the SQLite database if it does not exist
- [ ] Add the backend model layer for user and board data persistence
- [ ] Implement API routes to fetch the current Kanban for a user
- [ ] Implement API routes to update columns, card positions, card content, and card creation/deletion
- [ ] Ensure data is persisted correctly and consistently
- [ ] Add backend unit tests for create, read, update, and delete behavior

Tests:

- [ ] Verify database initialization works on a fresh environment
- [ ] Test fetching an empty or existing board
- [ ] Test moving cards between columns and within a column
- [ ] Test renaming columns and editing card details
- [ ] Test creating and deleting cards
- [ ] Verify the backend persists with SQLite correctly between requests

Success criteria:

- The backend can fully manage the Kanban board for a user
- The database is created automatically when missing
- Backend unit tests cover the main CRUD and board-mutation flows

---

## Part 7: Frontend + backend integration

Objective:

Replace the static in-memory board state with real API-backed persistence so the system behaves like a real Kanban app.

Checklist:

- [ ] Connect the frontend to the backend API for initial board load
- [ ] Send card movement, creation, deletion, and rename operations to the backend
- [ ] Refresh UI state after successful saves
- [ ] Handle loading and error states gracefully
- [ ] Verify board data remains consistent after reloads
- [ ] Run end-to-end tests covering the full user flow

Tests:

- [ ] Confirm the board loads from the API on first render
- [ ] Confirm changes persist after drag/drop and edits
- [ ] Confirm the UI updates properly after a server-side mutation
- [ ] Confirm loading and failed-request behavior is understandable

Success criteria:

- The frontend is no longer relying only on local state
- The Kanban actions persist across refreshes and user sessions
- The app behaves consistently in integration tests

---

## Part 8: AI connectivity with OpenRouter

Objective:

Connect the backend to OpenRouter and prove that a simple AI call works before integrating it into the Kanban assistant.

Checklist:

- [x] Add the OpenRouter configuration using the project root environment file
- [x] Use the specified model: openai/gpt-oss-120b
- [x] Implement a backend endpoint or service for a simple AI verification call
- [x] Run a minimal test prompt such as 2 + 2 to confirm connectivity
- [x] Validate request/response handling and error reporting

Tests:

- [x] Call the AI with a trivial prompt and verify a valid response
- [x] Confirm authentication and model configuration work correctly
- [x] Confirm API failure cases are surfaced clearly for troubleshooting

Success criteria:

- The backend can reach OpenRouter successfully
- A simple prompt receives a valid model response
- The service is ready for Kanban-aware AI actions

---

## Part 9: AI board-aware structured output flow

Objective:

Feed the AI the Kanban state and user question with optional conversation history, then require structured outputs that include both a user-visible answer and an optional board update.

Checklist:

- [x] Define the AI request payload: current board JSON, user prompt, and conversation history
- [x] Define the response contract with structured fields for user reply and optional card/column updates
- [x] Implement backend validation for structured outputs
- [x] Ensure card updates are mapped cleanly to the board model
- [x] Test both answer-only and board-update responses
- [x] Avoid over-engineering the schema; keep the output contract minimal and deterministic

Tests:

- [x] Verify a natural-language prompt returns a valid structured response
- [x] Verify the AI can create a new card with a valid payload
- [x] Verify the AI can edit an existing card title/details
- [x] Verify the AI can move cards between columns when explicitly requested
- [x] Verify invalid or malformed responses are rejected safely

Success criteria:

- The AI responds with structured outputs that the backend can parse reliably
- The AI can make useful board updates within the MVP scope
- The backend rejects malformed AI output before damaging board state

---

## Part 10: Sidebar AI chat and automatic UI refresh

Objective:

Add the final chat experience in the UI, allowing the user to ask the AI for changes and automatically updating the board when the model returns a valid update.

Checklist:

- [x] Add an AI chat sidebar to the UI
- [x] Allow users to send questions and receive responses
- [x] Pass the current board state and conversation context to the backend
- [x] Parse structured AI output and apply valid Kanban updates automatically
- [x] Refresh the board immediately after the AI updates the state
- [x] Keep the chat experience simple and readable while matching the product’s visual language
- [x] Add UI tests for the AI chat workflow and board update behavior

Tests:

- [x] Chat with the AI and confirm the response is displayed
- [x] Ask the AI to create or edit a card and confirm the board updates
- [x] Ask the AI to move a card and confirm the card position changes
- [x] Confirm the UI refreshes without manual reload
- [x] Confirm invalid structured responses do not silently corrupt the board

Success criteria:

- The AI sidebar is functional and visually integrated into the app
- The board reflects AI-driven changes immediately
- The user can use the AI assistant as the final MVP feature without manual data refresh

---

## Quality gates for each phase

For every completed phase, the agent should verify:

- [ ] The change matches the MVP requirement, not a broader feature set
- [ ] The solution stays simple and avoids unnecessary abstraction
- [ ] Unit and integration tests cover the affected behavior
- [ ] The code is consistent with the existing project structure and no unnecessary dependencies are introduced
- [ ] The root cause of any issue is identified before implementation and fixed with evidence

## Approval gate

Implementation should stop at the end of Part 1 until the user approves the plan. After approval, the work should proceed in order, one phase at a time, with tests proving each phase succeeds before the next phase begins.
