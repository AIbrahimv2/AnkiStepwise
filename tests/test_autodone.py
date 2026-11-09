import json
from harness import *  # noqa
from harness import actions, col
from tq.bridge import Bridge
from tq.state import SEP
from aqt.qt import QWidget

class Host(QWidget):
    index = None
    def request_index(self): actions.request_index(self._s)
    def reload_index(self, force=False): pass
    def _s(self, i): self.index = i
    def push(self, e): pass
host = Host(); bridge = Bridge(host); actions.set_announcer(bridge.toast)
call = lambda cmd, **a: bridge.handle(json.dumps({"cmd": cmd, **a}))
call("boot"); idx = actions.cached_index()

# 1. queuing something with nothing left to unsuspend -> Done
leaf = next(k for k in idx.post_order if not idx.kids(k) and idx.total[k] > 3 and not idx.suspended.get(k, 0) and k.startswith("#ak_step1_v12::#b&b"))
r = call("queue", tags=[idx.name(leaf)])
entry = next((x["key"] for x in r["side"]["completed"] if leaf == x["key"] or leaf.startswith(x["key"] + SEP)), None)
assert not r["side"]["queued"] and entry, (leaf, entry)
print("1.", r["toasts"])
print("   queued", leaf.split(SEP)[-1], "-> Done entry:", entry.replace("#ak_step1_v12::", "S1/"))
node = call("children", key=leaf.rsplit(SEP, 1)[0])["nodes"]
print("   tree shows it:", next(n["status"] for n in node if n["key"] == leaf))

# 2. complete every child of a folder -> the folder becomes the Done entry
def candidates():
    for p in idx.post_order:
        kids = idx.kids(p)
        if (p.startswith("#ak_step1_v12::#pixorize") and 2 <= len(kids) <= 4
                and all(not idx.kids(c) and idx.suspended.get(c, 0) for c in kids)
                and not any(idx.suspended_mask[i] for i in idx.tag_cards.get(p, ()))):
            yield p, kids
parent, kids = next(candidates())
print(f"2. folder {idx.name(parent).split(SEP)[-1]} with {len(kids)} topics, all with suspended cards")
for c in kids[:-1]:
    r = call("complete", tags=[idx.name(c)])
    assert any(x["key"] == c for x in r["side"]["completed"])
r = call("complete", tags=[idx.name(kids[-1])])
done_keys = [x["key"] for x in r["side"]["completed"]]
assert parent in done_keys and not any(k in done_keys for k in kids), done_keys
print("   after the last one:", r["toasts"])
print("   Done list shows the folder, not its", len(kids), "topics ✓")
print("AUTO-DONE OK")
