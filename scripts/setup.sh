#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python}

case "${PREFIX:-}" in
  *com.termux*)
    # Termux ships working native packages (notably NumPy) in its Python
    # site-packages. PyPI does not publish Android wheels, so an isolated venv
    # would try—and fail—to compile NumPy against Android libc.
    "$PYTHON" - <<'PY'
try:
    import numpy
except ImportError:
    raise SystemExit(
        "Termux NumPy is missing. Run `pkg install python-numpy`, then rerun setup."
    )
PY
    "$PYTHON" -m venv --clear --system-site-packages "$ROOT/.venv"
    "$ROOT/.venv/bin/python" -m pip install --no-deps -e "$ROOT[dev]"
    "$ROOT/.venv/bin/python" - <<'PY'
modules = ("fastapi", "httpx", "numpy", "openai", "pydantic", "pytest", "uvicorn")
missing = []
for module in modules:
    try:
        __import__(module)
    except ImportError:
        missing.append(module)
if missing:
    raise SystemExit(
        "Missing Termux Python dependencies: "
        + ", ".join(missing)
        + ". Install them in the Termux Python environment and rerun setup."
    )
PY
    ;;
  *)
    "$PYTHON" -m venv --clear "$ROOT/.venv"
    "$ROOT/.venv/bin/python" -m pip install -e "$ROOT[dev]"
    ;;
esac

npm --prefix "$ROOT/apps/web" ci
mkdir -p "$ROOT/data"
echo "Setup complete. Copy .env.example to .env, then run scripts/dev.sh"
