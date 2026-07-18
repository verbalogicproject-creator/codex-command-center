#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PMEM_PYTHON:-python}
PYTHONPATH="$ROOT/services/memory" "$PYTHON" - <<'PY'
from aria_memory.config import Settings
from aria_memory.db import Database
from aria_memory.embeddings import EmbeddingStore, create_provider

settings = Settings()
db = Database(settings.data_dir / "local.db", settings.seed_path)
print(EmbeddingStore(db, create_provider(settings)).sync().model_dump_json(indent=2))
PY

