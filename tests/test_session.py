"""The daily workflow: plan, watch + check, study, carry over."""
import json
from harness import *  # noqa
from harness import actions, col, mw
from tq.bridge import Bridge
from aqt.qt import QWidget

class Host(QWidget):
    @property
    def index(self): return actions.cached_index()  # like the real window
    def request_index(self): actions.request_index(self._s)
    def reload_index(self, force=False):
        if force: actions.mark_index_dirty()
        actions.request_index(self._s)
    def _s(self, i): pass
    def push(self, e): pass
host = Host(); bridge = Bridge(host); toasts = []
actions.set_announcer(toasts.append)
def call(cmd, **a):
    r = bridge.handle(json.dumps({"cmd": cmd, **a})); assert "error" not in r, r
    toasts.extend(r.get("toasts", [])); return r
def recount():  # what happens after reviews: index rebuilt, consolidation runs
    actions.mark_index_dirty(); actions.request_index()
def rows(side): return {r["key"]: r for r in side["queued"]}

assert mw.addonManager.cfg["count_mode"] == "new", "meter counts new cards"
call("boot"); idx = actions.cached_index()
# Topics from a folder with more left in it, so checking them off can't finish
# the folder (a finished folder replaces its topics' rows in Done).
by_folder = {}
for k in idx.post_order:
    if (k.startswith("#ak_step1_v12::#pixorize::") and not idx.kids(k)
            and 2 <= idx.suspended.get(k, 0) <= 12 and not idx.waiting.get(k, 0)):
        by_folder.setdefault(k.rsplit("::", 1)[0], []).append(k)
pick = next(v for v in by_folder.values() if len(v) >= 5)[:4]
a, b, c, d = [idx.name(k) for k in pick]
side = call("queue", tags=[a, b, c])["side"]
M = side["count"]; print(f"1. planned 3 topics: {M} new cards (limit {side['limit']})")

side = call("complete", tags=[a])["side"]; recount(); side = call("sync")["side"]
r = rows(side)[a.lower()]
print(f"2. watched + checked {a.split('::')[-1]}: meter {side['count']} (was {M}); row watched={r['watched']}, "
      f"suspended={r['suspended']}, counted={r['fresh']}; watched {side['watched']}/{len(side['queued'])}")
assert side["count"] == M and r["watched"] and r["suspended"] == 0 and r["fresh"] > 0
assert any(x["key"] == a.lower() for x in side["completed"])

cids = col.find_cards(f'"tag:{a}"'.replace("_", "\\_"))
col.db.execute(f"update cards set type=2, queue=2, ivl=1, due=0 where id in ({','.join(map(str, cids))})")
toasts.clear(); recount(); side = call("sync")["side"]
print(f"3. studied all {len(cids)} cards of it: meter {side['count']}; in queue: {a.lower() in rows(side)}; toast: {toasts[-1:]}")
assert a.lower() not in rows(side) and side["count"] == M - r["fresh"]
assert any(x["key"] == a.lower() for x in side["completed"])

side = call("complete", tags=[b])["side"]; side = call("unwatch", tags=[b])["side"]
rb = rows(side)[b.lower()]
print(f"4. checked then undid {b.split('::')[-1]}: watched={rb['watched']}, status back to queued")
assert not rb["watched"] and actions.load_state().status(b) == "queued"

call("complete", tags=[c]); side = call("finish_session")["side"]
print(f"5. clear watched: queue now {[x['title'] for x in side['queued']]}; {c.split('::')[-1]} still done: "
      f"{actions.load_state().effective(c)[0]}")
assert c.lower() not in rows(side) and actions.load_state().effective(c)[0] == "completed"

call("later", tags=[d])
cids = col.find_cards(f'"tag:{d}"'.replace("_", "\\_"))
col.db.execute(f"update cards set queue=0 where id in ({','.join(map(str, cids))})")  # unsuspended, unstudied
recount(); side = call("sync")["side"]
print(f"6. Later topic unsuspended but unstudied: still in Later = {any(x['key']==d.lower() for x in side['later'])}")
assert any(x["key"] == d.lower() for x in side["later"])
col.db.execute(f"update cards set type=2, queue=2, ivl=1 where id in ({','.join(map(str, cids))})")
recount(); side = call("sync")["side"]
print(f"7. ...and once studied: in Later = {any(x['key']==d.lower() for x in side['later'])}, "
      f"done = {actions.load_state().effective(d)[0]}")
assert not any(x["key"] == d.lower() for x in side["later"]) and actions.load_state().effective(d)[0] == "completed"
print("SESSION WORKFLOW OK")
