import time

from harness import *  # noqa: F401,F403
from harness import actions, col, colorsync, counts, state, widget, load_colorful_tags_copy, mw, TOOLTIPS, UNSUSPENDED

SEP = "::"
ok = 0


def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1


# --- state ---------------------------------------------------------------
st = state.QueueState()
a = "#AK_Step1_v12::#B&B::16_Neuro"
b = "#AK_Step1_v12::#B&B::16_Neuro::02_Nervous_System_Structures::04_Brainstem"
c = "#AK_Step1_v12::#Bootcamp::Neurology::05_Brainstem_Anatomy"
st.queue(b)
st.queue(c)
check(st.queued() == [b, c] or set(st.queued()) == {b, c}, "queue order")
ch = st.queue(a)  # folds b
check(set(st.queued()) == {a, c} and ch.get(b, 1) is None, f"fold nested {st.queued()} {ch}")
check(st.effective(b) == ("queued", a), "inherited queued")
check(st.effective(b.upper()) == ("queued", a), "case-insensitive")
ch = st.complete([a, c])
check(set(st.completed()) == {a, c} and not st.queued(), "complete")
st.queue(b)
check(st.effective(b)[0] == "queued" and st.effective(b + "::x")[0] == "queued", "own beats ancestor")
check(st.unqueue(b) == {b: None} and st.effective(b) == ("completed", a), "unqueue")
check(st.clear(a) == {a: None} and st.effective(b) == (None, None), "clear")
rt = state.QueueState(st.to_dict())
check(rt.to_dict() == st.to_dict(), "round trip")
check(state.QueueState({"tags": {"x": {"status": "bogus"}, "y": 3}}).tags == {}, "bad data ignored")

# --- counts / index ------------------------------------------------------
t0 = time.time()
idx = counts.build_index(col, "new")
print(f"index built in {time.time() - t0:.2f}s, {len(idx.names)} tags")
roots = counts.resource_roots(idx, ["#AK_Step*"])
print("roots:", roots)
check("#ak_step1_v12" in roots and "#ak_step2_v12" in roots, "roots match")
bb = "#ak_step1_v12::#b&b"
check(idx.name(bb) == "#AK_Step1_v12::#B&B", "canonical name")
# compare index counts with backend searches for several tags
for key in [bb, b.lower(), c.lower(), "#ak_step1_v12::#sketchypharm",
            "#ak_step1_v12::#sketchypharm::05_gi_&_endocrine::03_thyroid,_parathyroid,_adrenal::02_bisphosphonates,_raloxifene,_denosumab,_calcitonin",
            "#ak_step1_v12::#sketchymicro::03_viruses::01_rna_(+)_sense::02_poliovirus_(picornaviridae)"]:
    name = idx.name(key)
    tot = len(counts.card_ids(col, [name]))
    fr = len(counts.today_units(col, counts.fresh_ids(col, [name], "new"), "new"))
    check(idx.total[key] == tot and idx.fresh[key] == fr,
          f"count mismatch {name}: idx {idx.total[key]}/{idx.fresh[key]} vs search {tot}/{fr}")
    print(f"  {counts.prettify(idx.last(key))[:40]:40} total {tot:5} new {fr:5} leaves {idx.leaves[key]}")
check(idx.leaves[bb] > 50, "leaves")
check(counts.prettify("05_Ethanol_Metabolism:_Pathway") == "05 Ethanol Metabolism: Pathway", "prettify")
check(counts.root_label("#AK_Step1_v12") == "Step 1", counts.root_label("#AK_Step1_v12"))
is_root = counts.root_matcher(["#AK_Step*"])
check(counts.short_path(b, is_root, True) == "Step 1 › B&B › Neuro › Nervous System Structures",
      counts.short_path(b, is_root, True))
check(counts.short_name("12_Rabies") == "Rabies" and counts.short_name("19314") == "19314"
      and counts.prettify("12_Rabies") == "12 Rabies", "number prefixes only dropped outside the tree")

# unique counting across overlapping tags
q = [b, c]
uniq = len(counts.fresh_ids(col, q, "new"))
summed = sum(len(counts.fresh_ids(col, [t], "new")) for t in q)
print(f"overlap: unique {uniq} vs summed {summed}")
check(uniq <= summed, "unique <= sum")

# --- Colorful Tags sync ---------------------------------------------------
# (start from the morning's colour state for these checks)

ud = load_colorful_tags_copy()
check(colorsync.find_user_data() is ud, "find colorful tags")
groups = colorsync.color_groups(ud)
print("colour groups:", {k: len(v) for k, v in groups.items()})
check(colorsync.looks_green("#00f900") and not colorsync.looks_green("#ff9300")
      and not colorsync.looks_green("#ff40ff") and not colorsync.looks_green("#00fdff"), "green guess")
magenta = "BlueLink::Lungs+VentilationPathway"
colorsync.apply({b: "queued", magenta: None, c: "completed"}, "#ff9300", "#00f900", ud=ud)
check(ud.tags[b]["color"] == "#ff9300", "queued colour")
check(ud.tags[magenta]["color"] == "#ff40ff", "foreign colour untouched on clear")
check(ud.tags[c]["color"] == "#00f900", "completed colour")
colorsync.apply({b: None}, "#ff9300", "#00f900", ud=ud)
check(b not in ud.tags, "our colour removed on clear")
pinned_before = ud.tags["#AK_Step1_v12::#B&B"].copy()
colorsync.apply({"#AK_Step1_v12::#B&B": "queued"}, "#ff9300", "#00f900", ud=ud)
colorsync.apply({"#AK_Step1_v12::#B&B": None}, "#ff9300", "#00f900", ud=ud)
check(ud.tags["#AK_Step1_v12::#B&B"].get("pin") is True, "pin survives")

from tq.config import get_config  # noqa: E402
# --- actions round trip on the collection --------------------------------
# (topics with suspended cards: fully unsuspended ones go straight to Done)
b = "#AK_Step1_v12::#B&B::09_Endocrinology::05_Other::01_Pituitary_Anatomy_and_Physiology"
c = "#AK_Step1_v12::#Bootcamp::Endocrinology::03_Anterior_and_Posterior_Pituitary"
mode = get_config()["count_mode"]
uniq = len(counts.today_units(col, counts.fresh_ids(col, [b, c], mode), mode))
actions.queue([b, c])
s2 = actions.load_state()
check(set(s2.queued()) == {b, c}, "persisted in collection config")
check(col.get_config("tagQueue")["v"] == 1, "config key")
check(ud.tags[b]["color"] == "#ff9300", "sync via actions")
sus_before = len(counts.suspended_ids(col, [b, c]))
html = widget.build_widget()
check("tq-widget" in html and f"<b>{uniq:,}</b>" in html, "widget count")
actions.complete([b, c])
s3 = actions.load_state()
check(all(s3.effective(t)[0] == "completed" for t in (b, c)) and not s3.queued(), "completed via actions")
check(len(counts.suspended_ids(col, [b, c])) == 0 and len(UNSUSPENDED) == sus_before,
      f"unsuspended {len(UNSUSPENDED)} of {sus_before}")
print("tooltips:", TOOLTIPS)
check(ud.tags[c]["color"] == "#00f900", "completed colour via actions")
html = widget.build_widget()
check("2/2 checked off" in html, "checked-off topics stay in the day's plan")

# config defaults are filled in when keys are missing/mistyped
mw.addonManager.cfg = {"card_limit": "lots", "resource_roots": "nope"}
from tq.config import get_config
cfg = get_config()
check(cfg["card_limit"] == 150 and cfg["resource_roots"] == ["#AK_Step*"], "config defaults")

print(f"\nALL {ok} CHECKS PASSED")
