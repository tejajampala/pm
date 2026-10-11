#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME="pm-mvp"
CONTAINER_NAME="pm-mvp-container"

cd "$(dirname "$0")/.."

docker build -t "$IMAGE_NAME" .
docker run --rm -d --name "$CONTAINER_NAME" --env-file .env -p 8000:8000 "$IMAGE_NAME"

echo "Project Management MVP is running at http://localhost:8000"
