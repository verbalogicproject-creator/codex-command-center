#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT[dev]"
npm --prefix "$ROOT/apps/web" ci
mkdir -p "$ROOT/data"
echo "Setup complete. Copy .env.example to .env, then run scripts/dev.sh"

