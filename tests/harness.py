"""Load the Stepwise add-on against a scratch copy of the test collection, with
a fake `mw`, offscreen Qt and synchronous ops. Imported by the test scripts.

Run the tests with tests/run.sh. The collection comes from tests/fixture/
(gitignored), which tests/make_fixture.py fills."""

import json
import os
import shutil
import sys
import types

S = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(S), "src")
FIXTURE = os.path.join(S, "fixture")

if not os.path.exists(os.path.join(FIXTURE, "collection.anki2")):
    sys.exit("No test collection: run tests/make_fixture.py first.")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "/Applications/Anki.app/Contents/Resources/app_packages")

# Fresh copy of the collection for every run.
work = os.path.join(FIXTURE, "work")
shutil.rmtree(work, ignore_errors=True)
os.makedirs(work)
for f in ("collection.anki2", "collection.anki2-wal"):
    src = os.path.join(FIXTURE, f)
    if os.path.exists(src):
        shutil.copy(src, work)

# Package alias without a hyphen.
pkg_link = os.path.join(FIXTURE, "pkgs", "tq")
os.makedirs(os.path.dirname(pkg_link), exist_ok=True)
if os.path.islink(pkg_link) and os.readlink(pkg_link) != SRC:
    os.unlink(pkg_link)
if not os.path.islink(pkg_link):
    os.symlink(SRC, pkg_link)
sys.path.insert(0, os.path.dirname(pkg_link))

from aqt.qt import QApplication, QMenu  # noqa: E402

app = QApplication.instance() or QApplication(["test"])

import aqt  # noqa: E402
from anki.collection import Collection  # noqa: E402

col = Collection(os.path.join(work, "collection.anki2"))
# Functional tests start from an empty queue; profiling keeps the real one.
if not os.environ.get("KEEP_STATE"):
    col.remove_config("tagQueue")


class FakeAddonManager:
    def __init__(self):
        self.cfg = json.load(open(os.path.join(SRC, "config.json")))
        self.writes = 0

    def getConfig(self, module):
        return json.loads(json.dumps(self.cfg))

    def writeConfig(self, module, cfg):
        self.writes += 1
        self.cfg = json.loads(json.dumps(cfg))

    def setConfigUpdatedAction(self, module, fn):
        self.config_action = fn

    def setConfigAction(self, module, fn):
        self.open_config = fn

    def setWebExports(self, module, pattern):
        self.web_exports = pattern


class FakeWeb:
    evals = []

    def eval(self, js):
        FakeWeb.evals.append(js)


class FakeDeckBrowser:
    refreshes = 0
    web = FakeWeb()

    def refresh(self):
        FakeDeckBrowser.refreshes += 1


from aqt.qt import QWidget  # noqa: E402

mw = QWidget()
mw.col = col
mw.addonManager = FakeAddonManager()
mw.state = "deckBrowser"
mw.deckBrowser = FakeDeckBrowser()
mw.form = types.SimpleNamespace(menuTools=QMenu())
aqt.mw = mw

import tq  # noqa: E402
from tq import actions, counts, state, ui, colorsync, widget, browser_menu  # noqa: E402,F401

# --- synchronous stand-ins for background ops ---------------------------------


class SyncQueryOp:
    def __init__(self, *, parent, op, success):
        self.op, self.ok, self.fail = op, success, None

    def failure(self, fn):
        self.fail = fn
        return self

    def run_in_background(self):
        try:
            res = self.op(col)
        except Exception as e:  # pragma: no cover
            if self.fail:
                self.fail(e)
                return
            raise
        self.ok(res)


UNSUSPENDED = []


class SyncUnsuspend:
    def __init__(self, card_ids):
        self.cids = list(card_ids)
        self.ok = None

    def success(self, fn):
        self.ok = fn
        return self

    def run_in_background(self):
        col.sched.unsuspend_cards(self.cids)
        UNSUSPENDED.extend(self.cids)
        actions.mark_index_dirty()
        if self.ok:
            self.ok(None)


TOOLTIPS = []
actions.QueryOp = SyncQueryOp
actions.unsuspend_cards = lambda *, parent, card_ids: SyncUnsuspend(card_ids)
actions.tooltip = lambda msg, **kw: TOOLTIPS.append(msg)
ui.tooltip = lambda msg, **kw: TOOLTIPS.append(msg)
ui.restoreGeom = ui.saveGeom = lambda *a, **k: None
ui.restoreSplitter = ui.saveSplitter = lambda *a, **k: None
BROWSED = []
actions.aqt = types.SimpleNamespace(dialogs=types.SimpleNamespace(
    open=lambda name, *a, **kw: BROWSED.append(kw.get("search"))))


def load_colorful_tags_copy():
    """Register a fake Colorful Tags module holding a copy of the fixture's data."""
    data = json.load(open(os.path.join(FIXTURE, "colorful_tags.json")))

    class UserData:
        def __init__(self):
            self.tags = data["tags"]
            self.saves = 0

        def save(self):
            self.saves += 1

    mod = types.ModuleType("fake_colorful.data")
    mod.UserData = UserData
    mod.user_data = UserData()
    sys.modules["fake_colorful.data"] = mod
    return mod.user_data


def pump(n=5):
    for _ in range(n):
        app.processEvents()
