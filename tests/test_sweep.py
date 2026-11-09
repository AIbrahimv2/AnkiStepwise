"""The Done sweep: tags never queued or coloured, but fully studied, get
marked completed (in resources you use, no deeper than you work there)."""
import json
import time

from harness import *  # noqa: F401,F403
from harness import actions, col, load_colorful_tags_copy
from tq import rollup
from tq.bridge import Bridge
from tq.state import COMPLETED, QUEUED, SEP, QueueState
from aqt.qt import QWidget

ud = load_colorful_tags_copy()


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


host = Host()
bridge = Bridge(host)
said = []
actions.set_announcer(said.append)
call = lambda cmd, **a: bridge.handle(json.dumps({"cmd": cmd, **a}))  # noqa: E731
call("boot")
idx = actions.cached_index()
n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


# Nothing queued or completed anywhere: no resource is "used", nothing swept.
actions.consolidate()
check(not actions.load_state().tags, "empty state sweeps nothing")

# Queue one unfinished Pixorize topic five levels deep: Pixorize is now used,
# down to that depth.
pix = "#ak_step1_v12::#pixorize"
topic = next(k for k in idx.post_order if k.startswith(pix + SEP) and k.count(SEP) + 1 == 5
             and idx.suspended.get(k, 0) > 2)
call("queue", tags=[idx.name(topic)])
state = actions.load_state()
swept = [t for t, e in state.tags.items() if e["status"] == COMPLETED]
keys = [t.lower() for t in swept]
check(state.status(idx.name(topic)) == QUEUED, "the unfinished topic stays queued")
check(len(keys) > 20, f"swept {len(keys)}")
check(all(k.startswith(pix + SEP) for k in keys), "only the used resource")
check(all(k.count(SEP) + 1 <= 5 for k in keys), "no deeper than the queued topic")
check(all(rollup.studied(idx, k) for k in keys), "every swept tag is fully studied")
check(all(k.rsplit(SEP, 1)[0] not in keys for k in keys), "only the highest in each branch")
check(all(not rollup.studied(idx, k.rsplit(SEP, 1)[0]) or k.count(SEP) + 1 <= 2 for k in keys),
      "a swept tag's parent isn't fully studied (or it'd be the one marked)")
now = int(time.time())
ats = [state.tags[t]["at"] for t in swept]
check(all(0 < a <= now for a in ats), "dated by the cards' first reviews")
check(min(ats) < now - 86400, "dates are when they were studied, not today")
check(all(ud.tags.get(t, {}).get("color") == "#00f900" for t in swept), "coloured green in Colorful Tags")
check(any(f"Marked {len(keys):,} topics done" in s for s in said), said)

# Nothing else in the tree changed: other resources untouched.
other = "#ak_step1_v12::#uworld"
check(not any(t.lower().startswith(other) for t in state.tags), "question banks untouched")

# Running again finds nothing new.
said.clear()
before = json.dumps(actions.load_state().to_dict(), sort_keys=True)
actions.consolidate()
check(json.dumps(actions.load_state().to_dict(), sort_keys=True) == before and not said, "idempotent")

# The pure function agrees with what was stored.
check(rollup.sweep(idx, QueueState(actions.load_state().to_dict()), {"#ak_step1_v12"}) == [], "nothing left")

# Done tab lists them, newest first.
side = json.loads(json.dumps(call("sync", visible=[])["side"]))
check(side["doneTotal"] == len(keys) and len(side["completed"]) == min(100, len(keys)), (side["doneTotal"], len(keys)))
ats = [state.tags[idx.name(r["key"])]["at"] if idx.name(r["key"]) in state.tags else 0 for r in side["completed"]]
page2 = call("done_page", offset=100, limit=200)
check(page2["total"] == len(keys) and len(page2["rows"]) == min(200, max(0, len(keys) - 100)), "next page")
check(not {r["key"] for r in page2["rows"]} & {r["key"] for r in side["completed"]}, "pages don't overlap")

print(f"SWEEP TESTS PASSED ({n} checks; swept {len(keys)} Pixorize topics)")
