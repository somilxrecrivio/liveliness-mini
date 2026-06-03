#!/usr/bin/env bash
# Start the FastAPI backend (CPU-only).
set -euo pipefail
cd "$(dirname "$0")"

# shellcheck disable=SC1091
[ -d ".venv" ] && source .venv/bin/activate

# Load PORT/HOST from .env if present.
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
if [ -f ".env" ]; then
  HOST="$(grep -E '^HOST=' .env | cut -d= -f2 | tr -d '"' || echo "$HOST")"
  PORT="$(grep -E '^PORT=' .env | cut -d= -f2 | tr -d '"' || echo "$PORT")"
fi

exec uvicorn backend.app:app --host "$HOST" --port "$PORT" --reload
