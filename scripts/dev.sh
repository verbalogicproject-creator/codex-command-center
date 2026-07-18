#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -f "$ROOT/.env" ]; then
  set -a
  . "$ROOT/.env"
  set +a
fi
cd "$ROOT"
PYTHON=${PMEM_PYTHON:-"$ROOT/.venv/bin/python"}
test -x "$PYTHON" || PYTHON=$(command -v python)

PYTHONPATH="$ROOT/services/memory" "$PYTHON" -m uvicorn aria_memory.app:app \
  --host 127.0.0.1 --port 8000 --reload &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM

NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm --prefix "$ROOT/apps/web" run dev
