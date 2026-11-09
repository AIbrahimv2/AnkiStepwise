"""Suspended / waiting / buried breakdown must match Anki's own searches."""
import os
os.environ["KEEP_STATE"] = "1"
from harness import *  # noqa
from harness import col, counts, mw
from tq.config import get_config

# Anki un-buries cards every day, so bury some here: by hand and as siblings.
new = [cid for (cid,) in col.db.all("select id from cards where type=0 and queue=0 limit 60")]
assert len(new) == 60, "expected unsuspended new cards in this collection"
col.sched.bury_cards(new[:30])
col.sched.bury_cards(new[30:], manual=False)

idx = counts.build_index(col, "suspended")
# tags of notes that have buried new cards, plus their parents
rows = col.db.all("select n.tags from cards c join notes n on n.id=c.nid where c.type=0 and c.queue in (-2,-3)")
tags = sorted({t for (ts,) in rows for t in ts.split()})[:12]
parents = sorted({t.rsplit("::", 1)[0] for t in tags if "::" in t})[:6]
assert tags and parents, "the buried cards should have tags"
n = 0
for t in tags + parents + ["#AK_Step1_v12::#B&B", "#AK_Step2_v12"]:
    k = t.lower()
    susp = len(counts.card_ids(col, [t], "is:suspended"))
    wait = len(counts.card_ids(col, [t], "is:new -is:suspended"))
    bur = len(counts.card_ids(col, [t], "is:new is:buried"))
    got = (idx.suspended.get(k, 0), idx.waiting.get(k, 0), idx.buried.get(k, 0))
    assert got == (susp, wait, bur), (t, got, (susp, wait, bur))
    assert idx.fresh.get(k, 0) == susp, "suspended mode counts suspended only"
    n += 1
    if bur:
        print(f"  {t.split('::')[-1][:40]:40} suspended {susp:4}  waiting {wait:3}  buried {bur:3} ✓")
print(f"{n} tags match Anki's searches")
# v3: the meter counts new cards; v2's automatic switch to "suspended" is undone once,
# an old config keeps "new", and a choice made afterwards sticks
mw.addonManager.cfg = {"count_mode": "new", "card_limit": 150}
assert get_config()["count_mode"] == "new" and mw.addonManager.cfg["config_version"] == 3
mw.addonManager.cfg = {"count_mode": "suspended", "card_limit": 150, "config_version": 2}
assert get_config()["count_mode"] == "new" and mw.addonManager.cfg["config_version"] == 3
mw.addonManager.cfg["count_mode"] = "suspended"
assert get_config()["count_mode"] == "suspended", "explicit choice after migration is kept"
print("config migration OK")
print("BURIED BREAKDOWN MATCHES")
