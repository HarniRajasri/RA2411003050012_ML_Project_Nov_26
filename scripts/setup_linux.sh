#!/usr/bin/env bash
# One-time setup for Linux/macOS. Run from anywhere:  ./scripts/setup_linux.sh [--with-eeg]
set -euo pipefail
cd "$(dirname "$0")/.."
WITH_EEG=0; [[ "${1:-}" == "--with-eeg" ]] && WITH_EEG=1

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PY="$c"; break; fi
done
[[ -n "$PY" ]] || { echo "ERROR: Python 3.11+ not found." >&2; exit 1; }
echo "Using $($PY --version)"

[[ -d .venv ]] || "$PY" -m venv .venv
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt
[[ $WITH_EEG -eq 1 ]] && .venv/bin/python -m pip install -r eeg/requirements.txt
[[ -f .env ]] || { cp .env.example .env; echo "Created .env"; }

if command -v node >/dev/null 2>&1; then
  (cd frontend && npm install --no-audit --no-fund && npm run build)
elif [[ -f frontend/dist/index.html ]]; then
  echo "Node.js not found; using the prebuilt dashboard."
else
  echo "WARNING: Node.js not found and no prebuilt dashboard. Install Node.js 18+ and re-run." >&2
fi

(cd backend && ../.venv/bin/python -m pytest)
echo
echo "Setup complete. Start with:  ./scripts/run_backend.sh   then open http://localhost:8000"
