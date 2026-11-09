"""Run the automatic done/roll-up on the user's real state (copy)."""
import os, time
os.environ["KEEP_STATE"] = "1"
from harness import *  # noqa
from harness import actions, col
from tq import rollup
from tq.state import SEP, COMPLETED, is_under

said = []
actions.set_announcer(said.append)
before = actions.load_state()
b_q, b_l, b_c = before.queued(), before.later(), before.completed()
print(f"before: {len(b_q)} queued, {len(b_l)} later, {len(b_c)} completed")
actions.request_index(lambda i: None)     # builds the index; consolidation runs on build
idx = actions.cached_index()
t = time.perf_counter(); done, dl = rollup.done_tags(idx, b_c); ms = (time.perf_counter() - t) * 1000
print(f"done_tags: {len(done):,} of {len(idx.names):,} tags done ({ms:.0f} ms)")
after = actions.load_state()
a_q, a_l, a_c = after.queued(), after.later(), after.completed()
print(f"after:  {len(a_q)} queued, {len(a_l)} later, {len(a_c)} completed")
print("announced:"); [print("  •", m) for m in said]
moved = [t for t in b_q + b_l if t not in a_q + a_l]
print("moved to Done:", [t.split(SEP)[-1] for t in moved])
new_tops = [t for t in a_c if t not in b_c]
for top in new_tops:
    covered = [t for t in b_c + moved if is_under(t, top) and t.lower() != top.lower()]
    print(f"rolled up: {top.replace('#AK_Step1_v12::','S1/')}  (covers {len(covered)} entries)")

# invariants
for t in a_q + a_l:
    assert idx.suspended.get(t.lower(), 0) or not idx.total.get(t.lower(), 0), f"still queued with nothing to unsuspend: {t}"
for t in a_c:
    assert not any(is_under(t, o) and o.lower() != t.lower() for o in a_c), f"redundant completed child: {t}"
for t in b_c + moved:
    assert after.effective(t)[0] == COMPLETED, f"lost completion: {t}"
done2, _ = rollup.done_tags(idx, a_c)
roots = {r for r in idx.kids("") if r.startswith("#ak_step")}
for t in a_c:
    parent = t.lower().rsplit(SEP, 1)[0]
    assert parent in roots or parent not in done2 or SEP not in t, f"should have rolled up further: {t}"
print("INVARIANTS OK")
# idempotent: running again changes nothing
said.clear(); actions.consolidate()
assert actions.load_state().to_dict() == after.to_dict() and not said
print("second run: no changes ✓")
