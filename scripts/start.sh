#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="pm-mvp"
CONTAINER_NAME="pm-mvp-container"
VOLUME_NAME="pm-mvp-data"

cd "$(dirname "$0")/.."

docker build -t "$IMAGE_NAME" .
docker run --rm -d --name "$CONTAINER_NAME" --env-file .env -p 127.0.0.1:8000:8000 -v "$VOLUME_NAME":/app/backend/data "$IMAGE_NAME"

echo "Project Management MVP is running at http://localhost:8000"
