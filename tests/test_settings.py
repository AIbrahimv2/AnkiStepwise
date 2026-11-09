"""The in-window Settings dialog's bridge: read, preview, validate, save and
the side effects of each change."""
import json

from harness import *  # noqa: F401,F403
from harness import FakeDeckBrowser, actions, load_colorful_tags_copy, mw

from tq import ui
from tq.bridge import Bridge
from aqt.qt import QAction, QKeySequence, QWidget

ud = load_colorful_tags_copy()


class Host(QWidget):
    pushes = []
    reloads = 0

    @property
    def index(self):
        return actions.cached_index()

    def request_index(self):
        actions.request_index(lambda i: None)

    def reload_index(self, force=False):
        Host.reloads += 1
        if force:
            actions.mark_index_dirty(membership=True)
        self.request_index()

    def push(self, e):
        self.pushes.append(e)

    def show_toast(self, m):
        bridge.toast(m)


host = Host()
bridge = Bridge(host)
n = 0


def call(cmd, **args):
    r = bridge.handle(json.dumps({"cmd": cmd, **args}))
    json.dumps(r)
    assert "error" not in r, r
    return r


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


# Anki's Config button opens these Settings, not the JSON editor.
check(mw.addonManager.open_config is ui.open_settings, "Config button opens in-window Settings")

# Asked for before the page loaded: boot opens them, once.
bridge.settings_on_boot = True
check(call("boot")["openSettings"] is True, "boot opens Settings when asked early")
check(call("boot")["openSettings"] is False, "only once")
check(bridge.booted, "booted")

s = call("settings")["settings"]
check(s["cardLimit"] == 150 and s["countMode"] == "new" and s["resourceRoots"] == ["#AK_Step*"], s)
check(s["defaults"]["cardLimit"] == 150 and s["defaults"]["shortcut"] == "Ctrl+Alt+Q", s["defaults"])
check(s["colorSyncAvailable"] is True and s["colors"]["queued"] == "#ff9300", "colours")

m = call("root_matches", patterns=["#AK_Step*", "#nothing*", ""])["matches"]
check(len(m[0]) >= 2 and all(t.lower().startswith("#ak_step") for t in m[0]), m[0])
check(m[1] == [] and m[2] == [], m)

# Bad values: reported by field, nothing saved.
writes = mw.addonManager.writes
r = call("save_settings", settings={"cardLimit": 0, "countMode": "weird",
                                     "colors": {"queued": "orange"}, "shortcut": "Ctrl+Nope+"})
check(set(r["problems"]) == {"cardLimit", "countMode", "colors.queued", "shortcut"}, r)
check(mw.addonManager.writes == writes, "nothing written when invalid")

# Limit + shortcut: saved, deck meter patched, Tools menu shortcut updated live.
actions.menu_action = QAction("Stepwise", mw)
actions.menu_action.setShortcut(QKeySequence("Ctrl+Alt+Q"))
evals = len(FakeDeckBrowser.web.evals)
r = call("save_settings", settings={**{k: s[k] for k in s if k in (
    "cardLimit", "countMode", "unsuspendOnComplete", "resourceRoots", "showOnDeck",
    "colorSync", "colors", "shortcut")}, "cardLimit": 120, "shortcut": "Shift+Ctrl+T"})
cfg = mw.addonManager.cfg
check(cfg["card_limit"] == 120 and r["side"]["limit"] == 120, "limit saved")
check(cfg["shortcut"] == "Ctrl+Shift+T", f"shortcut normalised: {cfg['shortcut']}")
check(actions.menu_action.shortcut().toString() == "Ctrl+Shift+T", "menu shortcut live")
check(len(FakeDeckBrowser.web.evals) > evals, "deck-screen meter refreshed")
check("Settings saved" in r["toasts"] and r["recount"] is False, r["toasts"])

# Nothing changed: no write, no toast.
writes = mw.addonManager.writes
r = call("save_settings", settings={"cardLimit": 120})
check(mw.addonManager.writes == writes and not r["toasts"], "no-op save is silent")

# Count mode: recount.
reloads = Host.reloads
r = call("save_settings", settings={"countMode": "suspended"})
check(r["recount"] is True and Host.reloads == reloads + 1, "count mode recounts")
check(cfg is not mw.addonManager.cfg and mw.addonManager.cfg["count_mode"] == "suspended", "mode saved")

# Resource folders: trimmed, blanks and duplicates dropped, recount.
r = call("save_settings", settings={"resourceRoots": [" #AK_Step* ", "", "#ak_step*", "#Other"]})
check(mw.addonManager.cfg["resource_roots"] == ["#AK_Step*", "#Other"], mw.addonManager.cfg["resource_roots"])
check(r["recount"] is True, "roots recount")

# Colours: every tag with a status is recoloured in the sidebar.
tag = "#AK_Step1_v12::#B&B::16_Neuro"
actions.queue([tag])
check(ud.tags[tag]["color"] == "#ff9300", "queued colour before")
r = call("save_settings", settings={"colors": {"queued": "#0096FF", "completed": "#00f900", "later": "#af52de"}})
check(mw.addonManager.cfg["queued_color"] == "#0096ff", "hex lower-cased")
check(ud.tags[tag]["color"] == "#0096ff", "existing queued tag recoloured")
check(r["colors"]["queued"] == "#0096ff", "page gets the new colours")

# Pins: unpinning from Settings.
mw.addonManager.cfg["pinned_resources"] = ["#AK_Step1_v12::#B&B", "#AK_Step1_v12::#Bootcamp"]
s = call("settings")["settings"]
check([p["label"] for p in s["pinned"]] == ["B&B", "Bootcamp"] and s["pinned"][0]["step"] == "Step 1"
      and s["pinned"][0]["stepIndex"] == 0, s["pinned"])
call("save_settings", settings={"pinned": ["#AK_Step1_v12::#Bootcamp"]})
check(mw.addonManager.cfg["pinned_resources"] == ["#AK_Step1_v12::#Bootcamp"], "unpinned")

# Shortcut cleared.
call("save_settings", settings={"shortcut": ""})
check(mw.addonManager.cfg["shortcut"] == "" and actions.menu_action.shortcut().isEmpty(), "shortcut cleared")

# A pushed request once booted.
w = types.SimpleNamespace(bridge=bridge, pushed=[])
ui.QueueDialog.open_settings(types.SimpleNamespace(bridge=bridge, push=lambda e: w.pushed.append(e)))
check(w.pushed == [{"type": "settings"}], "open Settings pushes once the page is up")

print(f"SETTINGS TESTS PASSED ({n} checks)")
