"""The tree's open folders and closed step sections survive a reopen."""
import json
from harness import *  # noqa: F401,F403
from harness import actions, mw
from tq import bridge as bridge_mod
from tq.bridge import Bridge
from aqt.qt import QWidget


class Host(QWidget):
    @property
    def index(self):
        return actions.cached_index()

    def request_index(self):
        actions.request_index(lambda i: None)

    def reload_index(self, force=False):
        pass

    def push(self, e):
        pass


# Stand in for Anki's per-profile dict, which it saves with the profile.
import types
mw.pm = types.SimpleNamespace(profile={})
b = Bridge(Host())
call = lambda cmd, **a: json.loads(json.dumps(b.handle(json.dumps({"cmd": cmd, **a}))))  # noqa: E731
first = call("boot")
assert first["tree"] == {"open": [], "closed": []}, first["tree"]
idx = actions.cached_index()
real = "#ak_step1_v12::#b&b"
call("save_tree", open=["__root__:#ak_step1_v12", real, "#gone::folder"], closed=["__root__:#ak_step3_v12"])
assert mw.pm.profile[bridge_mod.TREE_KEY]["open"][1] == real, "kept in the profile"
again = Bridge(Host())  # a fresh window, as after restarting Anki
t = json.loads(json.dumps(again.handle(json.dumps({"cmd": "boot"}))))["tree"]
assert t["open"] == ["__root__:#ak_step1_v12", real], t  # missing folder dropped, section kept
assert t["closed"] == ["__root__:#ak_step3_v12"], t
print("TREE MEMORY TESTS PASSED")
