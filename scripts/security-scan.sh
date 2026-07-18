#!/usr/bin/env sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

if git rev-parse --git-dir >/dev/null 2>&1; then
  FILES=$(git ls-files)
else
  FILES=$(find . -type f -not -path './node_modules/*' -not -path './.next/*')
fi
printf '%s\n' "$FILES" | grep -E '(^|/)(\\.env|.*\\.db(-wal|-shm)?)$' && {
  echo "Forbidden tracked file detected" >&2; exit 1;
} || true
rg -n --hidden -g '!node_modules/**' -g '!.git/**' -g '!.vouch/**' \
  -g '!scripts/security-scan.sh' \
  '(sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY=sk-[A-Za-z0-9_-]+|/data/data/com\\.termux/files/home/)' . \
  && { echo "Potential secret or machine path detected" >&2; exit 1; } || true
echo "Security scan passed."
