#!/usr/bin/env bash
# Optional dev server on :5173 (the backend already serves the built dashboard on :8000).
set -euo pipefail
cd "$(dirname "$0")/../frontend"
[[ -d node_modules ]] || npm install --no-audit --no-fund
exec npm run dev
