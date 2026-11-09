"""Load the real QueueDialog (AnkiWebView + QWebChannel pycmd bridge) offscreen,
serving the built bundle from a stub media server, and drive it via JS."""
import json
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

# Numbers before tree keys, like vim.
from aqt.qt import QApplication, QEvent, QKeyEvent, Qt  # noqa: E402

SEND = """((keys) => {
  const tree = document.querySelector('.tree');
  for (const key of keys)
    tree.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, shiftKey: key === 'G' }));
})(%s)"""
LINE = "[...document.querySelectorAll('.tree [data-key]')].findIndex((r) => r.classList.contains('selected'))"


def press(*keys):
    js(SEND % json.dumps(keys))
    pump(5)
    time.sleep(0.1)
    pump(5)
    return js(LINE)


total = js("document.querySelectorAll('.tree [data-key]').length")
assert total > 25, total
assert press("g", "g") == 0
assert press("1", "0", "j") == 10, "10j"
assert press("8", "k") == 2, "8k"
assert press("3", "ArrowDown") == 5, "arrow keys take a number"
assert press("3", "Shift", "j") == 8, "pressing Shift keeps the number"
assert press("5", "Escape", "j") == 9, "Esc cancels the number and keeps the selection"
assert press("0", "j") == 10, "0 alone isn't a number"
assert press("5", "n", "j") == 11, "any other key uses the number up"
assert press("2", "0", "G") == 19, "20G"
assert press("5", "g", "g") == 4, "5gg"
assert press("9", "9", "9", "9", "j") == total - 1, "stops at the last row"
assert press("9", "9", "9", "9", "k") == 0, "stops at the first row"
# Ctrl keys go through Qt as real key events, because that's what differs from
# a browser: on a Mac the Control key arrives as Qt's Meta modifier, the page
# sees metaKey, and Control+d's key is the control character \\x04.
M = Qt.KeyboardModifier
proxy = d.web.focusProxy() or d.web


def qt_key(key, mods, text, native_key, count=8):
    for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
        QApplication.sendEvent(proxy, QKeyEvent(kind, key, mods, 0, native_key, 0, text))
    for _ in range(count):
        pump(5)
        time.sleep(0.03)
    return js(LINE)


def control_d():
    return qt_key(Qt.Key.Key_D, M.MetaModifier, "\x04", 0x02)


def control_u():
    return qt_key(Qt.Key.Key_U, M.MetaModifier, "\x15", 0x20)


js("document.querySelector('.tree').focus(); 1")
d.web.setFocus()
pump(20)
half = js("Math.max(1, Math.floor(document.querySelector('.tree').clientHeight / 30 / 2))")
press("g", "g")
assert control_d() == half, "Control-d moves half a page"
assert control_u() == 0, "Control-u moves back"
assert qt_key(Qt.Key.Key_D, M.ControlModifier, "d", 0x02) == half, "so does the other Ctrl modifier"
assert qt_key(Qt.Key.Key_U, M.ControlModifier, "u", 0x20) == 0
assert qt_key(Qt.Key.Key_D, M.MetaModifier, "D", 0x02) == half, "Caps Lock doesn't stop it"
press("g", "g")
press("3")
assert control_d() == 3, "a number sets how far Control-d moves"
assert control_d() == 6, "and it's remembered"
assert control_u() == 3, "for Control-u too"

# Control-r redoes, for the same reason.
queued = len(actions.load_state().queued())
js("document.querySelector('.row .cb').click()")
assert wait_for(f"document.querySelectorAll('.item').length > {queued}"), "queued a topic"
press("u")
assert wait_for(f"document.querySelectorAll('.item').length === {queued}"), "u undoes"
qt_key(Qt.Key.Key_R, M.MetaModifier, "\x12", 0x0F)
assert wait_for(f"document.querySelectorAll('.item').length > {queued}"), "Control-r redoes"
press("u")
assert wait_for(f"document.querySelectorAll('.item').length === {queued}")

press("4", "2")
assert js("document.querySelector('.count-pending')?.textContent") == "42", "the number shows while it's pending"
press("Escape")
assert not js("document.querySelector('.count-pending')"), "and goes once it's cancelled"
print("number prefixes work")

print("\nWEBVIEW TEST PASSED")
srv.shutdown()
# QtWebEngine can crash in its own teardown, after the test has finished: leave
# without it, so a non-zero exit always means a real failure.
sys.stdout.flush()
os._exit(0)
