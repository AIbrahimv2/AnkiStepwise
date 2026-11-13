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
# The first row is a sticky step header: scrolled past, it's held at the top
# and looks in view, so scrolling to it mustn't trust where it's drawn.
SCROLL = "document.querySelector('.tree').scrollTop"
press("G")
assert js(SCROLL) > 0, "G scrolls down"
press("g", "g")
assert js(SCROLL) == 0, "gg scrolls back up to the first row"
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

# --- the queue list's keys, and Shift+H / Shift+L between the two -----------------
idx = actions.cached_index()
picked = [k for k in idx.post_order if k.startswith("#ak_step1_v12::#b&b::") and not idx.kids(k)
          and idx.suspended.get(k, 0) > 0][:3]
assert len(picked) == 3, picked
names = [idx.name(k) for k in picked]
actions.queue(names)
d.push({"type": "sync"})  # the window isn't shown here, so it isn't told by itself
assert wait_for("document.querySelectorAll('.group .item').length === 3"), "queue rows render"

QSTATE = """JSON.stringify((() => {
  const c = document.querySelector('[data-keys="queue"] .cursor');
  return {
    focus: document.activeElement.dataset.keys || document.activeElement.className,
    cursor: c ? c.dataset.nav : null,
    tab: [...document.querySelectorAll('.side-panel [role=tab]')].findIndex((t) => t.getAttribute('aria-selected') === 'true'),
  };
})())"""
QSEND = """((keys) => {
  const list = document.querySelector('[data-keys="queue"]');
  for (const key of keys)
    list.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, shiftKey: /^[A-Z]$/.test(key) }));
})(%s)"""


def qstate():
    return json.loads(js(QSTATE))


def qpress(*keys):
    js(QSEND % json.dumps(keys))
    for _ in range(6):
        pump(5)
        time.sleep(0.05)
    return qstate()


def shift(letter):
    key = Qt.Key.Key_L if letter == "L" else Qt.Key.Key_H
    qt_key(key, M.ShiftModifier, letter, 0x25 if letter == "L" else 0x04, count=12)
    return qstate()


def rows_in_order():
    return json.loads(js("JSON.stringify([...document.querySelectorAll('[data-keys=\"queue\"] [data-nav]')].map((e) => e.dataset.nav))"))


s = shift("L")
assert s["focus"] == "queue" and s["cursor"] == rows_in_order()[0], ("Shift+L gives the queue the keys", s)
order = rows_in_order()
first, second, third = [x for x in order if x.startswith("r:")]
assert qpress("j")["cursor"] == first, "j"
assert qpress("2", "j")["cursor"] == third, "2j"
assert qpress("k")["cursor"] == second, "k"
assert qpress("g", "g")["cursor"] == order[0], "gg"
assert qpress("G")["cursor"] == order[-1], "G"
assert qpress("h")["cursor"] == order[0], "h goes to the resource"
qpress("h")
assert rows_in_order() == [order[0]], "h again closes it"
qpress("l")
assert rows_in_order() == order, "l opens it"
assert qpress("l")["cursor"] == order[1], "and again goes in"

# Space checks off and unchecks, s saves for later, x and dd remove.
tag = lambda nav: nav[2:].lower()


def has(tags, t):
    return t in {x.lower() for x in tags}


qpress("g", "g", "j")
qpress(" ")
assert wait_for("document.querySelectorAll('.group .item-check').length === 1"), "Space checks off"
assert has(actions.load_state().watched(), tag(first))
qpress(" ")
assert wait_for("document.querySelectorAll('.group .item-check').length === 0"), "Space again unchecks"
s = qpress("s")
assert wait_for("document.querySelectorAll('.group .item').length === 2"), "s moves it to Later"
assert has(actions.load_state().later(), tag(first))
assert qstate()["cursor"] == second, "the cursor takes the next row"
qpress("x")
assert wait_for("document.querySelectorAll('.group .item').length === 1"), "x removes it"
assert not has(actions.load_state().queued(), tag(second))
qpress("d", "d")
assert wait_for("document.querySelectorAll('.group .item').length === 0"), "dd removes it"
assert not actions.load_state().queued()

# gt / gT change tab; in Later, Space queues the topic again.
assert qpress("g", "t")["tab"] == 1, "gt"
assert qstate()["cursor"] is not None
assert wait_for("!!document.querySelector('.later-item')"), "Later shows"
qpress("j")
later_tag = tag(qstate()["cursor"])
qpress(" ")
assert wait_for("!document.querySelector('[data-nav=\"r:%s\"]')" % later_tag.replace('"', '\\"')), "Space queues it"
assert has(actions.load_state().queued(), later_tag)
assert qpress("g", "T")["tab"] == 0, "gT"

# Enter shows the topic in the tree and hands it the keys; Shift+H and
# Shift+L go back and forth, and the cursor stays where it was.
qpress("g", "g", "j")
row = qstate()["cursor"]
qpress("Enter")
assert wait_for("document.activeElement.classList.contains('tree')"), "Enter goes to the tree"
assert shift("L") == {**qstate(), "focus": "queue", "cursor": row}
assert shift("H")["focus"].startswith("tree"), "Shift+H gives the tree the keys"

# b: the topic's cards in Anki's browser, from the tree and from the queue
# (on a resource's row, all its topics).
import harness  # noqa: E402

harness.BROWSED.clear()
press("b")
assert len(harness.BROWSED) == 1 and harness.BROWSED[0], ("b in the tree (no Skim here)", harness.BROWSED)
press("B")
assert len(harness.BROWSED) == 2, "B in the tree"
harness.BROWSED.clear()
shift("L")
qpress("g", "g")
assert qstate()["cursor"].startswith("g:"), "the queue starts on a resource's row"
qpress("b")
assert len(harness.BROWSED) == 1 and "tag:" in harness.BROWSED[0][0], ("b on a resource's row", harness.BROWSED)
qpress("j")
qpress("b")
qpress("B")
assert len(harness.BROWSED) == 3, "b and B on a topic's row"
# Without Skim, p does nothing.
qpress("p")
assert not js("!!document.querySelector('.toast.error')"), "p without Skim is quiet"

# ? shows every key, from either list; Esc closes it.
js("document.body.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true, cancelable: true }))")
assert wait_for("document.querySelector('.modal h2') && document.querySelector('.modal h2').textContent === 'Keys'"), "? shows the keys"
keys_text = js("document.querySelector('.modal').textContent")
assert "Its cards in Anki's browser" in keys_text and "Skim" not in keys_text, keys_text
js("document.body.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))")
assert wait_for("!document.querySelector('.overlay')"), "Esc closes it"
shift("H")
actions.unqueue(actions.load_state().queued())
d.push({"type": "sync"})
print("queue keys work")

print("\nWEBVIEW TEST PASSED")
srv.shutdown()
# QtWebEngine can crash in its own teardown, after the test has finished: leave
# without it, so a non-zero exit always means a real failure.
sys.stdout.flush()
os._exit(0)
