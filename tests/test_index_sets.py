"""The in-memory card sets must match Anki's own search exactly."""
from harness import *  # noqa
from harness import actions, col, counts
st = actions.load_state()
queued, later = st.queued(), st.later()
for mode in ("new", "suspended", "all"):
    idx = counts.build_index(col, mode)
    cases = {
        "whole queue": queued,
        "all later": later,
        "queue+later": queued + later,
        "single later topic": later[:1],
        "resource B&B": ["#AK_Step1_v12::#B&B"],
        "Step 2 root": ["#AK_Step2_v12"],
        "mixed case input": [t.upper() for t in queued[:3]],
    }
    for name, tags in cases.items():
        mine = idx.units_under(tags)
        anki = counts.today_units(col, counts.fresh_ids(col, tags, mode), mode)
        assert mine == anki, (mode, name, len(mine), len(anki))
        print(f"  {mode:9} {name:20} {len(mine):6} cards  ✓")
# suspended lookup used by complete/unsuspend
actions.request_index(lambda i: None)
actions._membership_dirty = False
for tags in (queued, later, ["#AK_Step1_v12::#Pathoma"]):
    assert sorted(actions.suspended_cards(tags)) == sorted(counts.suspended_ids(col, tags))
print("suspended lookup matches ✓")
print("INDEX SETS MATCH ANKI SEARCH")
