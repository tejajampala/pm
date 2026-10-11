# Backend agent guide

## Overview

This backend is a FastAPI service for the Project Management MVP. It is intentionally simple at this stage: it should provide a minimal health endpoint and serve a basic static page at the root route while the rest of the app is being integrated.

## Current state

The backend is in its initial scaffolding phase. It is not yet connected to SQLite, user authentication, or the frontend build output. The immediate goal is to confirm that the service starts successfully and exposes a working local API.

## Runtime expectations

- Python 3.12+
- FastAPI
- Uvicorn
- uv for dependency management in the container

## Core endpoints

- `/`
  Returns a simple HTML page showing that the backend is running.

- `/api/health`
  Returns a JSON object with the service status and a simple hello-world payload.

- `/api/users/{username}/board`
  Reads or persists the user's Kanban board.

- `/api/ai/chat`
  Sends a board-aware prompt to OpenRouter and validates/persists an optional structured board update.

## Architecture

The app is organized as a minimal package in [app/main.py](app/main.py). It is deliberately lightweight so the scaffolding can be validated before more complex features are added.

## Future phases

The backend has evolved to include:

- serve the static Next.js frontend at /
- persist board state in SQLite
- expose board CRUD APIs for a user
- integrate with OpenRouter using the root `.env` configuration
- validate and process structured AI responses for Kanban updates
