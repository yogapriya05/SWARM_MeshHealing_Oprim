#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [[ ! -x .venv/bin/python ]]; then
    "$PYTHON_BIN" -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt

if [[ ! -f frontend/dist/index.html ]]; then
    if ! command -v npm >/dev/null 2>&1; then
        echo "Node.js/npm is required to build the frontend. Install Node.js 18+ and run this script again." >&2
        exit 1
    fi
    echo "Frontend build not found; installing frontend dependencies and building it..."
    (cd frontend && npm ci && npm run build)
fi

exec .venv/bin/python run.py "$@"
