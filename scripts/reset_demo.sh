#!/usr/bin/env bash
set -euo pipefail

# Reset MySQL volume and rebuild stack to ensure seed_demo.sql is applied

echo "Stopping and removing containers/volumes..."
docker compose down --volumes

echo "Rebuilding and starting services with demo seed..."
docker compose up -d --build

echo "Done. Adminer: http://127.0.0.1:8080 · API/UI: http://127.0.0.1:${API_PORT:-8000}/ui"
