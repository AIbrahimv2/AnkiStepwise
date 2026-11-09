from harness import *
from harness import actions, col, counts, widget, UNSUSPENDED, mw
idx = counts.build_index(col, "new")
def leaves_with_fresh(prefix):
    out=[]
    for k in idx.names:
        if k.startswith(prefix) and not idx.kids(k) and idx.fresh[k] >= 5: out.append(k)
    return out
A = leaves_with_fresh("#ak_step1_v12::#b&b::")
B = leaves_with_fresh("#ak_step1_v12::#bootcamp::")
today = lambda tags, mode="new": counts.today_units(col, counts.fresh_ids(col, tags, mode), mode)  # noqa: E731
sets = {k: today([idx.name(k)]) for k in A[:400] + B[:400]}
best=None
for a in A[:400]:
    for b in B[:400]:
        o=len(sets[a] & sets[b])
        if o and (best is None or o>best[0]): best=(o,a,b)
o,a,b = best
na, nb = idx.name(a), idx.name(b)
ua = len(sets[a]); ub=len(sets[b]); uni=len(sets[a]|sets[b])
print(f"A={na}\n  {ua} new\nB={nb}\n  {ub} new\noverlap {o}, unique {uni}")
assert len(today([na, nb])) == uni
actions.queue([na, nb])
html = widget.build_widget()
assert f"<b>{uni:,}</b>" in html, html[:300]
sus = len(counts.suspended_ids(col,[na,nb]))
actions.complete([na, nb])
assert len(UNSUSPENDED) == sus and sus > 0 and not counts.suspended_ids(col,[na,nb])
print(f"unique meter OK ({uni} not {ua+ub}); unsuspended {sus} cards on complete")
# after unsuspend, 'new' mode still counts them (unstarted), 'suspended' mode does not
assert len(today([na, nb])) == uni
assert len(today([na, nb], "suspended")) == 0
idx2 = counts.build_index(col, "suspended")
assert idx2.fresh[a] == 0 and idx2.total[a] == idx.total[a]
print("count modes OK")
