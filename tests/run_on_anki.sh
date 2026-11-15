#!/usr/bin/env bash
# Run the tests on another Anki version: tests/run_on_anki.sh 24.6.3 [test_bridge ...].
# Use it to check the oldest version the AnkiWeb listing offers Stepwise to.
#
# Each version gets its own environment in tests/fixture/anki/<version>
# (gitignored), installed from PyPI with uv the first time (300 to 400 MB).
# It gets the Python and Qt the Mac app of that version shipped: Python 3.9
# and Qt 6.6 up to 25.02, then the launcher's Python 3.13 and default Qt.
# QT=qt66 (or qt67, qt68, qt69, qt610) picks one of the launcher's other Qt
# builds instead, for 25.07 and later.
set -euo pipefail
cd "$(dirname "$0")"

ver="${1:?usage: tests/run_on_anki.sh <version, e.g. 24.6.3> [tests...]}"
shift
env="fixture/anki/$ver${QT:+-$QT}"

if [ ! -x "$env/bin/python" ]; then
  case "$ver" in
    2.1.*|23.*|24.*|25.2|25.2.*)
      [ -z "${QT:-}" ] || { echo "QT= is for 25.07 and later" >&2; exit 2; }
      py=3.9
      pkgs=("aqt==$ver" pyqt6==6.6.1 pyqt6-qt6==6.6.2 pyqt6-webengine==6.6.0 pyqt6-webengine-qt6==6.6.2)
      ;;
    *)
      py=3.13
      pkgs=("aqt[${QT:-qt}]==$ver")
      ;;
  esac
  uv venv -q --python "$py" "$env"
  uv pip install -q --python "$env/bin/python" "${pkgs[@]}"
fi

# The launcher's default Qt pairs Qt Quick 6.9 with WebEngine 6.8, and that pair
# crashes offscreen (in QSGTexture) as soon as a web view paints, with or
# without Stepwise. Software rendering avoids it.
export QT_QUICK_BACKEND="${QT_QUICK_BACKEND:-software}"
"$env/bin/python" -c 'from anki.buildinfo import version; from PyQt6.QtCore import qVersion; print(f"Anki {version}, Qt {qVersion()}")' 2>/dev/null
ANKI_PYTHON="$PWD/$env/bin/python" exec ./run.sh "$@"
