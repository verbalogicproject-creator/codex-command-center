#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: scripts/import-local-db.sh /path/to/source.db" >&2
  exit 2
fi
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SOURCE=$1
test -f "$SOURCE" || { echo "Source database not found" >&2; exit 1; }
mkdir -p "$ROOT/data"
cp "$SOURCE" "$ROOT/data/local.db"
echo "Copied source database to gitignored data/local.db; source was not modified."

