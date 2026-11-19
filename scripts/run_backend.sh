#!/usr/bin/env bash
# Starts the backend (API + WebSocket + built dashboard). Ctrl+C to stop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="0.0.0.0"; PORT="8000"
if [[ -f "$ROOT/.env" ]]; then
  v=$(grep -E '^\s*BACKEND_HOST\s*=' "$ROOT/.env" | tail -1 | cut -d= -f2 | tr -d ' \r') && [[ -n "${v:-}" ]] && HOST="$v"
  v=$(grep -E '^\s*BACKEND_PORT\s*=' "$ROOT/.env" | tail -1 | cut -d= -f2 | tr -d ' \r') && [[ -n "${v:-}" ]] && PORT="$v"
fi
[[ -x "$ROOT/.venv/bin/python" ]] || { echo "Run ./scripts/setup_linux.sh first." >&2; exit 1; }
cd "$ROOT/backend"
echo "KHorizon backend on http://localhost:$PORT  (API docs: /docs)"
exec "$ROOT/.venv/bin/python" -m uvicorn app.main:create_app --factory --host "$HOST" --port "$PORT"
