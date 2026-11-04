#!/usr/bin/env bash
# Build the web UI (web/ -> src/web/), then package src/ into a distributable
# .ankiaddon (a zip of the *contents* of src/, with no parent folder,
# excluding caches, user state, and logs).
set -euo pipefail
cd "$(dirname "$0")"

if command -v npm >/dev/null 2>&1; then
  npm --prefix web ci --silent
  npm --prefix web run build --silent
else
  echo "npm not found: packaging the existing src/web/ bundle" >&2
fi

mkdir -p dist
OUT="dist/anki-tag-queue.ankiaddon"
rm -f "$OUT"
( cd src && zip -r -X "../$OUT" . \
    -x '*__pycache__*' -x '*.pyc' -x 'meta.json' \
    -x 'user_files/*' -x '*.DS_Store' )
echo "built $OUT"
