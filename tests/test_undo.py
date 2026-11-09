"""Undo / redo of Stepwise actions, through the bridge like the page."""
import json

from harness import *  # noqa: F401,F403
from harness import actions, col, counts, load_colorful_tags_copy
from tq import history
from tq.bridge import Bridge
from tq.state import COMPLETED, LATER, QUEUED
from aqt.qt import QWidget

ud = load_colorful_tags_copy()


class SyncSuspend:
    def __init__(self, card_ids):
        self.cids = list(card_ids)

    def run_in_background(self):
        col.sched.suspend_cards(self.cids)
        actions.mark_index_dirty()


actions.suspend_cards = lambda *, parent, card_ids: SyncSuspend(card_ids)


class Host(QWidget):
    index = None

    def request_index(self):
        actions.request_index(self._s)

    def reload_index(self, force=False):
        pass

    def _s(self, i):
        self.index = i

    def push(self, e):
        pass

    def show_toast(self, m):
        bridge.toast(m)


host = Host()
bridge = Bridge(host)
call = lambda cmd, **a: json.loads(json.dumps(bridge.handle(json.dumps({"cmd": cmd, **a}))))  # noqa: E731
call("boot")
idx = actions.cached_index()
n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


def status(tag):
    return actions.load_state().status(tag)


# Two unfinished leaf topics with suspended cards, in one resource.
leaves = [k for k in idx.post_order if k.startswith("#ak_step1_v12::#pathoma") and not idx.kids(k)
          and idx.suspended.get(k, 0) >= 2 and not idx.waiting.get(k, 0)]
a, b, c = (idx.name(k) for k in leaves[:3])

r = call("undo")
check("Nothing to undo" in r["toasts"], r["toasts"])

# Queue, undo, redo.
call("queue", tags=[a])
check(status(a) == QUEUED and ud.tags[a]["color"] == "#ff9300", "queued")
r = call("undo")
check(status(a) is None and "color" not in ud.tags.get(a, {}), "undo unqueues and uncolours")
check(any(t.startswith("Undone\nQueued ") for t in r["toasts"]), r["toasts"])
check(not any(x["tag"] == a for x in r["side"]["queued"]), "side panel updated")
r = call("redo")
check(status(a) == QUEUED and any(t.startswith("Redone\nQueued ") for t in r["toasts"]), r["toasts"])

# Check off unsuspends; undo puts it back in the queue and re-suspends.
sus = counts.suspended_ids(col, [a])
check(len(sus) >= 2, "has suspended cards")
call("complete", tags=[a])
check(actions.load_state().effective(a)[0] == COMPLETED and not counts.suspended_ids(col, [a]), "checked off")
call("undo")
check(status(a) == QUEUED, "undo of check-off: queued again")
check(set(counts.suspended_ids(col, [a])) == set(sus), "its cards are suspended again")
check(a not in actions.load_state().watched(), "and not watched")
call("redo")
check(actions.load_state().effective(a)[0] == COMPLETED and not counts.suspended_ids(col, [a]), "redo")

# Undo only reverts that action: a change made elsewhere since survives.
call("queue", tags=[b])
actions.save_later([c])  # e.g. from the Browser sidebar, not undoable here
call("undo")
check(status(b) is None and status(c) == LATER, "unrelated later change kept")

# A new action clears redo.
call("later", tags=[b])
call("undo")
call("queue", tags=[b])
r = call("redo")
check("Nothing to redo" in r["toasts"], r["toasts"])

# No-ops leave no step; history is capped.
history.reset()
call("unqueue", tags=["#nope::nothing"])
check(not history._undo, "no-op not recorded")
for i in range(history.LIMIT + 5):
    call("later" if i % 2 == 0 else "unlater", tags=[b])
check(len(history._undo) == history.LIMIT, len(history._undo))

print(f"UNDO TESTS PASSED ({n} checks)")
