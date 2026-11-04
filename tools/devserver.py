"""Run the Tag Queue web UI outside Anki, against a copy of a real collection.

The page talks to the add-on's actual Python bridge (src/bridge.py), so what
you see is real data and real queue logic; only Anki's window is missing.
The collection is copied to a temp folder first, so the original is never
touched, and Colorful Tags data (if given) is only read.

Run it with Anki's own Python so `anki`/`aqt` import (macOS example):

    PY=~/Library/Application\\ Support/AnkiProgramFiles/python/cpython-3.13.5-macos-aarch64-none/bin/python3
    "$PY" tools/devserver.py --collection ~/Library/Application\\ Support/Anki2/User\\ 1/collection.anki2

Then either open http://127.0.0.1:5180 (serves the built src/web/ bundle),
or run `npm run dev` in web/ for live reload at http://localhost:5173 (it
proxies /bridge here). Add ?theme=dark for dark mode.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

SHELL = """<!doctype html>
<html><head><meta charset="utf-8"><title>Tag Queue (dev)</title>
<link rel="stylesheet" href="/web/app.css">
<script>
if (new URLSearchParams(location.search).get("theme") === "dark")
  document.documentElement.classList.add("night-mode");
window.pycmd = function (arg, cb) {
  fetch("/bridge", {method: "POST", body: arg}).then(r => r.json()).then(r => cb && cb(r));
  return false;
};
</script>
<script src="/web/app.js"></script>
</head><body><div id="root"></div></body></html>"""


def find_anki_packages() -> None:
    if importlib.util.find_spec("aqt") is None:
        for path in ("/Applications/Anki.app/Contents/Resources/app_packages",):
            if os.path.isdir(path):
                sys.path.insert(0, path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", required=True, help="collection.anki2 to copy and serve")
    ap.add_argument("--colorful-tags", help="Colorful Tags user_files/data.json to simulate the add-on")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5180)))
    args = ap.parse_args()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    find_anki_packages()

    work = tempfile.mkdtemp(prefix="tag-queue-dev-")
    for suffix in ("", "-wal"):
        src = args.collection + suffix
        if os.path.exists(src):
            shutil.copy(src, os.path.join(work, "collection.anki2" + suffix))

    from aqt.qt import QApplication, QMenu, QWidget

    qt_app = QApplication.instance() or QApplication(["tag-queue-dev"])

    import aqt
    from anki.collection import Collection

    col = Collection(os.path.join(work, "collection.anki2"))

    class AddonManager:
        def __init__(self):
            self.cfg = json.load(open(os.path.join(SRC, "config.json")))

        def getConfig(self, module):
            return json.loads(json.dumps(self.cfg))

        def writeConfig(self, module, cfg):
            self.cfg = json.loads(json.dumps(cfg))

        def setConfigUpdatedAction(self, module, fn):
            pass

        def setConfigAction(self, module, fn):
            pass

        def setWebExports(self, module, pattern):
            pass

    mw = QWidget()
    mw.col = col
    mw.addonManager = AddonManager()
    mw.state = "deckBrowser"
    mw.deckBrowser = types.SimpleNamespace(
        refresh=lambda: None, web=types.SimpleNamespace(eval=lambda js: None))
    mw.form = types.SimpleNamespace(menuTools=QMenu())
    aqt.mw = mw

    if args.colorful_tags:
        data = json.load(open(args.colorful_tags))

        class UserData:
            tags = data.get("tags", {})

            def save(self):  # read-only simulation
                pass

        fake = types.ModuleType("colorful_tags_dev.data")
        fake.UserData = UserData
        fake.user_data = UserData()
        sys.modules["colorful_tags_dev.data"] = fake

    spec = importlib.util.spec_from_file_location(
        "tag_queue_dev", os.path.join(SRC, "__init__.py"), submodule_search_locations=[SRC])
    pkg = importlib.util.module_from_spec(spec)
    sys.modules["tag_queue_dev"] = pkg
    spec.loader.exec_module(pkg)
    from tag_queue_dev import actions
    from tag_queue_dev.bridge import Bridge

    # Background ops run inline here.
    class SyncQueryOp:
        def __init__(self, *, parent, op, success):
            self.op, self.ok = op, success

        def failure(self, fn):
            return self

        def run_in_background(self):
            self.ok(self.op(col))

    class SyncUnsuspend:
        def __init__(self, card_ids):
            self.cids, self.ok = list(card_ids), None

        def success(self, fn):
            self.ok = fn
            return self

        def run_in_background(self):
            col.sched.unsuspend_cards(self.cids)
            actions.mark_index_dirty()
            actions.request_index()  # Anki recounts after the op; do the same
            if self.ok:
                self.ok(None)

    actions.QueryOp = SyncQueryOp
    actions.unsuspend_cards = lambda *, parent, card_ids: SyncUnsuspend(card_ids)
    actions.aqt = types.SimpleNamespace(dialogs=types.SimpleNamespace(
        open=lambda name, *a, **kw: print(f"[dev] would open {name} {kw.get('search') or ''}")))

    class Host(QWidget):
        @property
        def index(self):  # always the latest build, like the real window
            return actions.cached_index()

        def request_index(self):
            actions.request_index(self._set)

        def reload_index(self, force=False):
            if force:
                actions.mark_index_dirty()
            self.request_index()

        def _set(self, index):
            pass

        def push(self, event):
            print(f"[dev] push {event}")

        def show_toast(self, message):
            bridge.toast(message)

    host = Host()
    bridge = Bridge(host)
    actions.set_announcer(bridge.toast)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *a):
            pass

        def _send(self, body: bytes, ctype: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(SHELL.encode(), "text/html; charset=utf-8")
            if path.startswith("/web/") and ".." not in path:
                f = os.path.join(SRC, path.lstrip("/"))
                if os.path.isfile(f):
                    ctype = "text/css" if f.endswith(".css") else "application/javascript"
                    return self._send(open(f, "rb").read(), ctype + "; charset=utf-8")
            self._send(b"not found", "text/plain", 404)

        def do_POST(self):
            if self.path != "/bridge":
                return self._send(b"not found", "text/plain", 404)
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            result = bridge.handle(raw)
            self._send(json.dumps(result).encode(), "application/json")

    print(f"Tag Queue dev server on http://127.0.0.1:{args.port}  (collection copy in {work})")
    try:
        HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        col.close()
        shutil.rmtree(work, ignore_errors=True)
        qt_app.quit()


if __name__ == "__main__":
    main()
