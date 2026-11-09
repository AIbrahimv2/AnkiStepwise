"""Narrow windows in the real QueueDialog: load it (AnkiWebView + QWebChannel pycmd bridge) offscreen,
serving the built bundle from a stub media server, and drive it via JS."""
import os
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness import *  # noqa: F401,F403
from harness import S, SRC, actions, col, mw, pump, ui, app

PORT = 5198
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
assert rows and rows > 5, "tree did not render"
print("Chromium:", js("navigator.userAgent.match(/Chrome\\/[\\d.]+/)[0]"))
print("container queries supported:", js("CSS.supports('container-type: inline-size')"))
print("minimum size:", d.minimumSize().width(), "x", d.minimumSize().height())
assert d.minimumSize().width() == 440

STATE = """JSON.stringify({
  vw: innerWidth,
  heads: [...document.querySelectorAll('.tree-head > span')].filter(e => e.offsetParent).map(e => e.textContent),
  tree: !!document.querySelector('.tree-panel').offsetParent,
  side: !!document.querySelector('.side-panel')?.offsetParent,
  paneSwitch: !!document.querySelector('.pane-switch')?.offsetParent,
  branding: !!document.querySelector('.header, .app-icon, .title, .subtitle'),
  actionsIn: [...document.querySelectorAll('.page-actions')].filter(e => e.offsetParent).map(e => e.parentElement.className),
  limitOwnLine: document.querySelector('.meter-top').offsetHeight > 50,
  barW: document.querySelector('.tree .mini-track')?.offsetWidth ?? null,
  overflow: [...document.querySelectorAll('.panel, .meter-top, .side-footer, .toolbar, .header, .row, .btn')]
    .filter(e => e.offsetParent && e.scrollWidth > e.clientWidth + 1).length,
})"""
import json

# The tree keeps its two columns at every width; the bar shortens instead.
HEADS = ["Topic", "Left", "Progress"]


def at(w, h=760):
    d.resize(w, h)
    for _ in range(30):
        pump(2)
        time.sleep(0.03)
    s = json.loads(js(STATE))
    print(w, s)
    return s


s = at(1140)
assert not s["branding"] and s["actionsIn"] == ["toolbar"], s
s0 = s
assert s["heads"] == HEADS and s["side"] and not s["paneSwitch"]
assert not s["limitOwnLine"] and not s["overflow"]
s = at(860)
assert s["heads"] == HEADS and s["side"] and s["limitOwnLine"] and not s["overflow"]
assert s0["barW"] == 84 and s["barW"] == 64, (s0["barW"], s["barW"])
s = at(780)
assert s["heads"] == HEADS and s["side"] and not s["overflow"]
s = at(700)
assert not s["branding"] and s["actionsIn"] == ["topbar"], s
assert s["paneSwitch"] and s["tree"] and not s["side"] and not s["overflow"]
js("document.querySelectorAll('.pane-switch button')[1].click()")
pump(5)
s = json.loads(js(STATE))
print("queue pane:", s)
assert s["side"] and not s["tree"] and not s["overflow"]
d.resize(300, 300)
pump(5)
print("resized to 300 wide, got", d.width())
assert d.width() >= 440
s = at(440)
assert s["paneSwitch"] and s["side"] and not s["overflow"]
js("document.querySelectorAll('.pane-switch button')[0].click()")
s = at(440)
assert s["tree"] and s["heads"] == HEADS and not s["overflow"]
# --- the queue section --------------------------------------------------------
# Whatever is still unstudied: a folder with a deeper topic between two of its
# own, and a topic right under the resource that sorts after that folder.
idx = actions.cached_index()


def has_cards(k):
    return not idx.kids(k) and idx.suspended.get(k, 0) > 0


def pick_topics():
    for folder in idx.post_order:
        if not folder.startswith("#ak_step1_v12::") or folder.count("::") != 2:
            continue  # a folder right under a Step 1 resource
        kids, siblings = idx.kids(folder), idx.kids(folder.rsplit("::", 1)[0])
        after = siblings[siblings.index(folder) + 1:]
        direct = next((k for k in after if idx.suspended.get(k, 0) > 0), None)
        for j, mid in enumerate(kids):
            deep = next((g for g in idx.kids(mid) if has_cards(g)), None)
            first = next((k for k in kids[:j] if has_cards(k)), None)
            last = next((k for k in kids[j + 1:] if has_cards(k)), None)
            if direct and deep and first and last:
                return [first, deep, last, direct]
    raise AssertionError("need a folder with a deeper topic between two of its own")


picked = [idx.name(k) for k in pick_topics()]
at(1140)  # the last narrow check left the topics showing instead of the queue
actions.queue(picked)
assert wait_for("document.querySelectorAll('.group .item').length >= 4"), "queue rows did not render"
LAYOUT = """JSON.stringify((() => {
  const all = (s) => [...document.querySelectorAll(s)];
  const uniq = (s, f) => [...new Set(all(s).map(f))];
  const edge = (s, side) => uniq(s, (e) => Math.round(e.getBoundingClientRect()[side]));
  return {
    order: all('.group .cluster-label, .group .item').map((e) => e.matches('.cluster-label') ? 'h:' + e.textContent : 'r'),
    text: edge('.group-title, .group .item-title', 'left'),
    headings: uniq('.cluster-label', (e) => Math.round(e.getBoundingClientRect().left + parseFloat(getComputedStyle(e).paddingLeft))),
    marks: edge('.group .item-check, .group .item-bullet', 'left'),
    markSizes: uniq('.group .item-check, .group .item-bullet', (e) => Math.round(e.getBoundingClientRect().width)),
    numbers: edge('.group-meta b, .group .item-meta b', 'right'),
    rowHeights: uniq('.group .item', (e) => Math.round(e.getBoundingClientRect().height)),
    restingButtons: uniq('.list .item-actions, .group-head .item-actions', (e) => e.offsetWidth),
  };
})())"""
for width in (1140, 860):
    at(width)
    q = json.loads(js(LAYOUT))
    print("queue section", width, q)
    heads = [x for x in q["order"] if x != "r"]
    assert q["order"][0] == "r", "a topic right under the resource comes before any heading"
    assert len(heads) == 2 == len(set(heads)), "one heading per folder"
    assert q["order"].count("r") == 4, q["order"]
    assert len(q["text"]) == 1 and q["headings"] == q["text"], "names and headings share one left edge"
    assert len(q["marks"]) == 1 and q["markSizes"] == [14], "marks share one left edge and size"
    assert len(q["numbers"]) == 1, "numbers share one right edge"
    assert len(q["rowHeights"]) == 1, "every row is the same height"
    assert q["restingButtons"] == [0], "row buttons take no room until hovered"

# A resource's buttons sit at the right edge, right beside its number. This
# window never has real focus or hover, so the test shows them with a style.
gap = json.loads(js("""JSON.stringify((() => {
  const show = document.createElement('style');
  show.textContent = '.group-head .item-actions { width: auto !important; }';
  document.head.append(show);
  const head = document.querySelector('.group-head');
  const buttons = head.querySelector('.item-actions');
  const out = {
    width: buttons.offsetWidth,
    gap: head.querySelector('.group-meta').getBoundingClientRect().left - buttons.getBoundingClientRect().right,
  };
  show.remove();
  return out;
})())"""))
print("resource buttons", gap)
assert gap["width"] > 0 and 0 <= gap["gap"] <= 12, gap

# The ring checks a topic off and the check takes that back, without also
# jumping to the topic in the tree.
assert not js("document.querySelector('.item-sub')"), "no captions beside the numbers"
selected = "document.querySelector('.row.selected, .row.active, .row.flash')?.textContent ?? ''"
before = js(selected)
assert js("document.querySelector('.group .item-bullet').click(); true")
assert wait_for("document.querySelectorAll('.group .item-check').length === 1"), "ring checks off"
assert len(actions.load_state().watched()) == 1
assert js(selected) == before, "clicking the mark doesn't reveal the topic"
assert js("document.querySelector('.group .item-check').click(); true")
assert wait_for("document.querySelectorAll('.group .item-check').length === 0"), "check takes it back"
assert not actions.load_state().watched()

print("\nNARROW TEST PASSED")
srv.shutdown()
# QtWebEngine can crash in its own teardown, after the test has finished: leave
# without it, so a non-zero exit always means a real failure.
sys.stdout.flush()
os._exit(0)
