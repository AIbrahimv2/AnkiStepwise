"""Load the real QueueDialog (AnkiWebView + QWebChannel pycmd bridge) offscreen,
serving the built bundle from a stub media server, and drive it via JS."""
import os
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness import *  # noqa: F401,F403
from harness import S, SRC, actions, col, mw, pump, ui, app

PORT = 5199
PAGES = {}
ANKI_WEB = "/Applications/Anki.app/Contents/Resources/app_packages/_aqt/data/web"


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/_anki/legacyPageData":
            pid = self.path.split("id=")[-1]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGES.get(pid, "").encode())
            return
        if path.startswith("/_anki/"):
            f = os.path.join(ANKI_WEB, path[len("/_anki/"):])
            if os.path.isfile(f):
                self.send_response(200)
                self.send_header("Content-Type", "text/css" if f.endswith(".css") else "application/javascript")
                self.end_headers()
                self.wfile.write(open(f, "rb").read())
                return
        prefix = "/_addons/tq/web/"
        if path.startswith(prefix):
            f = os.path.join(SRC, "web", path[len(prefix):])
            if os.path.isfile(f):
                self.send_response(200)
                self.send_header("Content-Type", "text/css" if f.endswith(".css") else "application/javascript")
                self.end_headers()
                self.wfile.write(open(f, "rb").read())
                return
        self.send_response(404)
        self.end_headers()


srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
mw.mediaServer = types.SimpleNamespace(
    getPort=lambda: PORT, set_page_html=lambda pid, html, ctx: PAGES.__setitem__(str(pid), html))
mw.app = app
mw.serverURL = lambda: f"http://127.0.0.1:{PORT}/"
mw.baseHTML = lambda: f'<base href="http://127.0.0.1:{PORT}/">'
mw.pm = types.SimpleNamespace(minimalist_mode=lambda: False, reduce_motion=lambda: False)

ui.restoreGeom = ui.saveGeom = lambda *a, **k: None
d = ui.QueueDialog(mw)
d.resize(1140, 760)
d.show()

result = {}


def js(expr, timeout=8.0):
    done = []
    d.web.evalWithCallback(expr, lambda r: done.append(r))
    t = time.time()
    while not done and time.time() - t < timeout:
        app.processEvents()
        time.sleep(0.02)
    return done[0] if done else "<timeout>"


def wait_for(expr, timeout=20.0):
    t = time.time()
    while time.time() - t < timeout:
        pump(5)
        v = js(expr, 2)
        if v not in (None, False, 0, "<timeout>"):
            return v
        time.sleep(0.2)
    return None


rows = wait_for("document.querySelectorAll('.row').length")
print("rows rendered in AnkiWebView:", rows)
assert rows and rows > 5, "tree did not render through the real bridge"
print("pycmd defined:", js("typeof pycmd"))
print("meter:", js("document.querySelector('.meter-count').textContent + ' ' + document.querySelector('.meter-of').textContent"))
print("first rows:", js("[...document.querySelectorAll('.row .label')].slice(0,4).map(x=>x.textContent).join(' | ')"))

# Tick the first resource's checkbox in the page and check the collection.
before = len(actions.load_state().queued())
js("document.querySelector('.row .cb').click()")
ok = wait_for("document.querySelectorAll('.item').length")
after = actions.load_state().queued()
print("queued via page click:", after)
assert len(after) == before + 1 and ok

# A change made elsewhere (e.g. the Browser sidebar) is pushed to the page.
actions.unqueue(after)
gone = wait_for("document.querySelectorAll('.item').length === 0")
print("push from Python updated page:", gone)
assert gone

# Toast routing: an action with the dialog as parent shows a web toast.
d.show_toast("hello from python")
toast = wait_for("[...document.querySelectorAll('.toast')].map(t => t.textContent).join(' | ').includes('hello') && [...document.querySelectorAll('.toast')].map(t => t.textContent).join(' | ')")
print("toast:", toast)
assert toast and "hello" in toast

print("\nWEBVIEW TEST PASSED")
srv.shutdown()
# QtWebEngine can crash in its own teardown, after the test has finished: leave
# without it, so a non-zero exit always means a real failure.
sys.stdout.flush()
os._exit(0)
