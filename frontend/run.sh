#!/usr/bin/env bash
# Launch the WordPress Content Factory web UI (local only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

"$PY" -m pip install -q -r frontend/requirements.txt
exec "$PY" frontend/server.py
