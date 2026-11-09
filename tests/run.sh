#!/usr/bin/env bash
# Run the tests with Anki's own Python: all of them, or the ones named
# (tests/run.sh test_bridge test_logic). Run tests/make_fixture.py first.
set -uo pipefail
cd "$(dirname "$0")"

PY="${ANKI_PYTHON:-}"
if [ -z "$PY" ]; then
  for p in "$HOME"/Library/Application\ Support/AnkiProgramFiles/python/*/bin/python3; do PY="$p"; done
fi
[ -x "$PY" ] || { echo "Anki's Python not found: set ANKI_PYTHON" >&2; exit 2; }
[ -f fixture/collection.anki2 ] || { echo "No test collection: run python3 tests/make_fixture.py" >&2; exit 2; }

if [ $# -gt 0 ]; then tests=("$@"); else tests=(test_*.py); fi
log="fixture/last-run.log"
: > "$log"
failed=0
for t in "${tests[@]}"; do
  t="${t%.py}"
  out="$(timeout 300 "$PY" "$t.py" 2>&1)"
  code=$?
  printf '== %s (exit %s)\n%s\n' "$t" "$code" "$out" >> "$log"
  if [ "$code" -eq 0 ]; then
    echo "ok    $t"
  else
    echo "FAIL  $t (exit $code)"
    failed=$((failed + 1))
  fi
done
echo
if [ "$failed" -gt 0 ]; then
  echo "$failed failed: see tests/$log"
  exit 1
fi
echo "All ${#tests[@]} passed"
