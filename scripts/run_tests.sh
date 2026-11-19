#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
(cd "$ROOT/backend" && "$ROOT/.venv/bin/python" -m pytest)
if "$ROOT/.venv/bin/python" -c "import numpy, scipy" 2>/dev/null; then (cd "$ROOT" && .venv/bin/python -m pytest eeg -q); fi
