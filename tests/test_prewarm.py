"""Startup with an index saved last session: the window is made ahead of
time, hidden, from the saved index, counting nothing. Opening it shows the
tree at once, rebuilds in the background, and says "Syncing" meanwhile."""
import os
import sys
import time

from harness import *  # noqa: F401,F403
from harness import FIXTURE, actions, app, col, pump, ui

from aqt.qt import QTimer
from tq import index_cache
from webview_stub import srv

n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1
    print("  ok ", msg)


def js(d, expr, timeout=8.0):
    out = []
    d.web.evalWithCallback(expr, lambda r: out.append(r))
    end = time.time() + timeout
    while not out and time.time() < end:
        app.processEvents()
        time.sleep(0.005)
    return out[0] if out else None


def wait(d, expr, timeout=30.0):
    end = time.time() + timeout
    while time.time() < end:
        v = js(d, expr, 2)
        if v:
            return v
        pump(2)
    return None


ROWS = "document.querySelectorAll('.tree [data-key]').length"

# Last session: counted and saved.
index_cache.USER_FILES = os.path.join(FIXTURE, "work", "user_files")
actions.request_index()
actions.save_index()
saved_names = actions.cached_index().names


class LaterQueryOp:
    """Like Anki's: the work runs after the caller returns (here a moment
    later on the same thread), so opening the window doesn't wait for it."""

    def __init__(self, *, parent, op, success):
        self.op, self.ok = op, success

    def failure(self, fn):
        return self

    def run_in_background(self):
        QTimer.singleShot(300, lambda: self.ok(self.op(col)))


actions.QueryOp = LaterQueryOp

# This session starts: read, not counted.
actions.reset()
builds = []
real_build = actions.build_index
actions.build_index = lambda *a: builds.append(1) or real_build(*a)
check(actions.load_saved_index(), "the saved index is read at startup")

ui.prewarm()
d = ui._dialog
check(d is not None and not d.isVisible(), "the window is made ahead of time, hidden")
check(wait(d, ROWS), "its page loads the tree from the saved index while hidden")
check(not builds, "and nothing is counted: startup isn't slowed")
check(js(d, "!!document.querySelector('.syncing')") is False, "nothing is syncing yet")

t = time.perf_counter()
ui.open_dialog()
app.processEvents()
rows = js(d, ROWS)
shown_ms = (time.perf_counter() - t) * 1000
check(rows and shown_ms < 300, f"opening it shows the tree at once ({shown_ms:.0f} ms, {rows} rows)")
check(wait(d, "document.querySelector('.syncing') && document.querySelector('.syncing').textContent === 'Syncing'"),
      "and says Syncing while it rebuilds the saved index in the background")
check(wait(d, "!document.querySelector('.syncing')"), "when the rebuild lands, Syncing goes away")
check(len(builds) == 1, "one rebuild, started by opening the window")
check(actions.cached_index().names == saved_names and not actions.index_stale(), "and the index is up to date")

actions.build_index = real_build
print(f"ok ({n} checks)")
srv.shutdown()
sys.stdout.flush()
os._exit(0)  # QtWebEngine can crash in its own teardown
