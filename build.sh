#!/usr/bin/env bash
# Build the web UI (web/ -> src/web/), then package src/ into a distributable
# .ankiaddon (a zip of the *contents* of src/, with no parent folder,
# excluding caches, user state, and logs).
set -euo pipefail
cd "$(dirname "$0")"

# The shared add-on kit (src/kit/ and web/src/kit/, from anki-addon-kit
# beside this repo): warn if this copy is behind it.
if [ -f ../anki-addon-kit/sync.py ]; then
  python3 ../anki-addon-kit/sync.py --check . >/dev/null \
    || echo "warning: the kit differs from anki-addon-kit; run its sync.py" >&2
fi

if command -v npm >/dev/null 2>&1; then
  npm --prefix web ci --silent
  npm --prefix web run build --silent
else
  echo "npm not found: packaging the existing src/web/ bundle" >&2
fi

mkdir -p dist
OUT="dist/stepwise.ankiaddon"
rm -f "$OUT"
( cd src && zip -r -X "../$OUT" . \
    -x '*__pycache__*' -x '*.pyc' -x 'meta.json' \
    -x 'user_files/*' -x '*.DS_Store' )
# What's new reads the changelog, at the top of the package.
zip -q -X "$OUT" CHANGELOG.md
echo "built $OUT"
