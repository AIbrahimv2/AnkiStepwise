#!/usr/bin/env bash
# Package src/ into a distributable .ankiaddon (a zip of the *contents* of
# src/, with no parent folder, excluding caches, user state, and logs).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
OUT="dist/anki-tag-queue.ankiaddon"
rm -f "$OUT"
( cd src && zip -r -X "../$OUT" . \
    -x '*__pycache__*' -x '*.pyc' -x 'meta.json' \
    -x 'user_files/*' -x '*.DS_Store' )
echo "built $OUT"
