FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend .
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/backend/static

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
COPY --from=frontend-build /app/frontend/out /app/backend/static

WORKDIR /app/backend
RUN uv sync

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
