#!/usr/bin/env bash
# Standalone simulated students:  ./scripts/run_simulator.sh 25 600   (students, seconds; 0 = until Ctrl+C)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/python" "$ROOT/simulator/student_simulator.py" --students "${1:-20}" --duration "${2:-0}" --flaky
