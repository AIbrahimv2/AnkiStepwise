"""Topics that would add no cards: every card of theirs is in the queue
already, through other resources' topics (the same notes carry tags from
several resources). The tree marks them, and Hide done hides them."""
import json
import time
from collections import defaultdict

from harness import *  # noqa: F401,F403
from harness import actions
from tq.bridge import Bridge
from tq.state import SEP
from aqt.qt import QWidget


class Host(QWidget):
    @property
    def index(self):
        return actions.cached_index()

    def request_index(self):
        actions.request_index(lambda i: None)

    def reload_index(self, force=False):
        if force:
            actions.mark_index_dirty()
        actions.request_index(lambda i: None)

    def push(self, e):
        pass


bridge = Bridge(Host())


def call(cmd, **a):
    r = bridge.handle(json.dumps({"cmd": cmd, **a}))
    assert "error" not in r, r
    return r


checks = 0


def check(ok, what):
    global checks
    assert ok, what
    checks += 1


call("boot")
call("set_option", key="hideCompleted", value=False)
idx = actions.cached_index()
view = bridge.view()
check(idx is not None and idx.mode == view.mode, "the index counts the configured way")
roots = set(view.roots)


def resource(key):
    parts = key.split(SEP)
    return SEP.join(parts[:2]) if parts[0] in roots and len(parts) > 2 else None


# Which tags each card's note carries, to find a topic whose every note is
# also tagged in other resources.
tags_of = defaultdict(list)
for tag, cards in idx.tag_cards.items():
    for i in cards:
        tags_of[i].append(tag)

found = None
for key in sorted(idx.names):
    res = resource(key)
    if res is None or idx.kids(key) or not 0 < idx.fresh.get(key, 0) <= 30:
        continue
    if view.status_of(key)[0] is not None:
        continue
    others = {t for i in idx.tag_cards.get(key, ()) for t in tags_of[i]
              if resource(t) not in (None, res)}
    if not others or len(others) > 6 or any(view.status_of(t)[0] for t in others):
        continue
    if idx.units_under([key]) <= idx.units_under(others):
        found = key, sorted(others)
        break
check(found, "a topic whose cards other resources' topics hold too (the test needs one)")
key, others = found
name = idx.name(key)
print(f"{name}\n  covered by {[idx.name(t) for t in others]}")

check(not bridge.view().node(key)["covered"], "not covered while the queue is empty")

actions.queue([idx.name(t) for t in others])
view = bridge.view()
node = view.node(key)
check(node["covered"] and node["check"] == "off" and node["status"] is None, node)
check(view.projection([name])[0] == 0, "queuing it adds nothing")
check(not any(view.node(t)["covered"] for t in others), "the queued topics themselves aren't")
res = resource(key)
check(not view.node(res)["covered"], "nor is the whole resource")

# Replies to the page carry it, for every row it sends (hidden ones too).
r = call("sync", visible=[key] + others)
check([n["key"] for n in r["nodes"] if n["covered"]] == [key], r["nodes"])

# Hide done leaves it out of search results; with Hide done off it's there.
query = idx.last(key)
r = call("search", query=query)
check(key in r["matches"], f"{query!r} finds it")
call("set_option", key="hideCompleted", value=True)
r = call("search", query=query)
check(key not in r["matches"], "Hide done hides it")
check(r["summary"]["count"] == len(r["matches"]), "and the count agrees")
call("set_option", key="hideCompleted", value=False)

# Ruling out topics bigger than the queue is what keeps this cheap.
t = time.time()
big = call("children", key=res)["nodes"]
check(time.time() - t < 1.0, f"listing {len(big)} rows took {time.time() - t:.2f}s")

# Once they leave the queue, it adds cards again.
actions.unqueue([idx.name(t) for t in others])
check(not bridge.view().node(key)["covered"], "uncovered once they leave the queue")
print(f"COVERED TESTS PASSED ({checks} checks)")
