"""The "new cards" count follows the decks' Bury new siblings option: a note
counts once, buried cards and notes with a sibling due today don't count,
and decks without the option count every card. Checked against rules
written out separately here, then by changing the collection copy."""
import json

from harness import *  # noqa: F401,F403
from harness import actions, col, counts, mw
from tq.bridge import Bridge
from aqt.qt import QWidget

n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


today, cutoff = col.sched.today, col.sched.day_cutoff


def bury_of():
    return {d.id: bool(col.decks.config_dict_for_deck_id(d.id)["new"]["bury"])
            for d in col.decks.all_names_and_ids()}


def expected(tags):
    """Today's new cards under `tags`, from the rules, by hand."""
    cids = counts.fresh_ids(col, tags, "new")  # every never-studied card
    if not cids:
        return 0
    bury = bury_of()
    nids = col.db.list(f"select distinct nid from cards where id in ({','.join(map(str, cids))})")
    total = 0
    wanted = set(cids)
    for nid in nids:
        cards = col.db.all("select id, queue, type, did, odid, due from cards where nid = ?", nid)
        due = any((q in (2, 3) and d <= today) or (q == 1 and d < cutoff) for _i, q, t, _did, _o, d in cards if t != 0)
        new = [(i, o or did) for i, q, t, did, o, d in cards if t == 0 and i in wanted and q not in (-2, -3)]
        b = [c for c in new if bury[c[1]]]
        total += (1 if b and not due else 0) + len(new) - len(b)
    return total


idx = counts.build_index(col, "new")
st = actions.load_state()
samples = {
    "resource B&B": ["#AK_Step1_v12::#B&B"],
    "Step 2 root": ["#AK_Step2_v12"],
    "Pathoma": ["#AK_Step1_v12::#Pathoma"],
}
leaves = [k for k in idx.post_order if not idx.kids(k) and idx.new.get(k, 0) >= 3][:300]
for k in leaves[:40]:
    samples[k] = [idx.name(k)]
multi = 0
for name, tags in samples.items():
    units = idx.units_under(tags)
    ref = counts.today_units(col, counts.fresh_ids(col, tags, "new"), "new")
    check(units == ref, (name, len(units), len(ref)))
    check(len(units) == expected(tags), (name, len(units), expected(tags)))
    if len(tags) == 1:
        check(idx.fresh.get(tags[0].lower(), 0) == len(units), ("per-tag count", name))
    multi += idx.new.get(tags[0].lower(), 0) > len(units)
check(multi > 0, "some sampled tags have siblings held back")
print(f"index, reference path and hand-written rules agree on {len(samples)} tag sets")

# Other modes count every card, as before.
for mode in ("suspended", "all"):
    i2 = counts.build_index(col, mode)
    for tags in list(samples.values())[:8]:
        check(len(i2.units_under(tags)) == len(counts.fresh_ids(col, tags, mode)), (mode, tags))
print("suspended / all modes unchanged")

# A note in a burying deck with 3+ new cards, none buried, no sibling due.
bury = bury_of()
row = None
for k in leaves:
    for nid in col.db.list(
        "select c.nid from cards c join notes n on n.id = c.nid where n.tags like ? group by c.nid"
        " having sum(c.type = 0 and c.queue not in (-2, -3)) >= 3 and sum(c.type != 0) = 0 limit 5",
        f"% {idx.name(k)} %",
    ):
        cards = col.db.all("select id, did, odid from cards where nid = ?", nid)
        if all(bury[o or d] for _i, d, o in cards):
            row = (k, nid, [c[0] for c in cards], cards[0][2] or cards[0][1])
            break
    if row:
        break
check(row, "found a note with three new siblings")
key, nid, cids, did = row
tag = idx.name(key)
k_cards = len(cids)
base = len(counts.build_index(col, "new").units_under([tag]))
check(-nid in counts.build_index(col, "new").units_under([tag]), "the note counts as one unit")

# Bury new siblings off: each card counts.
conf = col.decks.config_dict_for_deck_id(did)
conf["new"]["bury"] = False
col.decks.update_config(conf)
off = counts.build_index(col, "new")
check(len(off.units_under([tag])) >= base + k_cards - 1, (len(off.units_under([tag])), base, k_cards))
check(not any(u < 0 for u in off.units_under([tag])), "no note units without burying")
conf["new"]["bury"] = True
col.decks.update_config(conf)
check(len(counts.build_index(col, "new").units_under([tag])) == base, "back on: counts once again")

# Unsuspending (checking off) doesn't change the count.
col.sched.unsuspend_cards(cids)
check(len(counts.build_index(col, "new").units_under([tag])) == base, "unsuspended: same count")

# Buried cards don't count today; with one sibling left it still counts once.
col.sched.bury_cards(cids[:-1], manual=True)
check(len(counts.build_index(col, "new").units_under([tag])) == base, "one unburied sibling still counts")
col.sched.bury_cards(cids[-1:], manual=True)
got = len(counts.build_index(col, "new").units_under([tag]))
check(got == base - 1, ("all buried: none today", got, base, col.db.all("select id, queue, type from cards where nid = ?", nid)))
col.sched.unbury_cards(cids)
check(len(counts.build_index(col, "new").units_under([tag])) == base, "unburied: counts again")

# A sibling due today (a review) holds the note's new cards back.
col.sched.set_due_date([cids[0]], "0")
check(col.db.scalar("select type from cards where id = ?", cids[0]) == 2, "made a review")
check(len(counts.build_index(col, "new").units_under([tag])) == base - 1, "review sibling due today")
col.sched.set_due_date([cids[0]], "5")
check(len(counts.build_index(col, "new").units_under([tag])) == base, "due in 5 days: counts today")
print("bury option, buried cards and due siblings all followed")

# Through the bridge: the meter is the session's unique units, and a queue
# row says how many wait for later days.
actions.mark_index_dirty(membership=True)


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


bridge = Bridge(Host())
call = lambda cmd, **a: json.loads(json.dumps(bridge.handle(json.dumps({"cmd": cmd, **a}))))  # noqa: E731
call("boot")
r = call("queue", tags=[tag])
side = r["side"]
row = next(x for x in side["queued"] if x["tag"] == tag)
idx = actions.cached_index()
check(side["count"] == len(idx.units_under(actions.load_state().session_tags())), (side["count"],))
check(row["fresh"] == base and row["afterToday"] == idx.new[key] - base, row)
check(row["afterToday"] >= k_cards - 1, row)
print(f"meter {side['count']}, row {row['fresh']} today + {row['afterToday']} later")
print(f"\nBURY TESTS PASSED ({n} checks)")
