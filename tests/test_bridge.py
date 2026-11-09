"""Drive the web UI's Python bridge the way the page does (JSON in, JSON out)."""
import json

from harness import *  # noqa: F401,F403
from harness import UNSUSPENDED, actions, counts, col, load_colorful_tags_copy, mw

from tq.bridge import Bridge
from aqt.qt import QWidget

ud = load_colorful_tags_copy()


class Host(QWidget):
    index = None
    pushes = []

    def request_index(self):
        actions.request_index(self._set)

    def reload_index(self, force=False):
        if force:
            actions.mark_index_dirty()
        self.request_index()

    def _set(self, i):
        self.index = i

    def push(self, e):
        self.pushes.append(e)

    def show_toast(self, m):
        bridge.toast(m)


host = Host()
bridge = Bridge(host)


def call(cmd, **args):
    r = bridge.handle(json.dumps({"cmd": cmd, **args}))
    json.dumps(r)  # must be JSON-serialisable
    assert "error" not in r, r
    return r


n = 0


def check(cond, msg):
    global n
    assert cond, msg
    n += 1


check(bridge.handle("domDone") is None, "ignores Anki's own messages")
check("error" in bridge.handle('{"cmd": "nope"}'), "unknown command reported")

boot = call("boot")
check(boot["ready"] and boot["options"]["banner"], "boot ready, banner offered")
check(boot["scopes"][0]["value"] == "all", "scopes")

info = call("import_info")
greens = [g for g in info["groups"] if g["suggested"] == "completed"]
check(len(greens) == 1 and greens[0]["count"] >= 100 and info["pins"] == 12, info)
r = call("import_colors", choices={"#00f900": "completed"}, pins=True)
check(not r["options"]["banner"] and any(f"{greens[0]['count']:,} completed" in t for t in r["toasts"]), r["toasts"])
check(r["scopes"][1]["value"] == "pinned", "pinned scope appears after importing pins")

top = call("children", key="")["nodes"]
check([t["label"] for t in top[:2]] == ["Step 1", "Step 2"] and top[0]["kind"] == "root", [t["label"] for t in top])
check(top[0]["stepIndex"] == 0 and top[1]["stepIndex"] == 1 and top[0]["count"] > 10, top[0])
check(top[-1].get("group") and top[-1]["label"] == "Other tags", "other tags group")
step1 = call("children", key=top[0]["key"])["nodes"]
check(step1[0]["label"] == "B&B" and step1[0]["pinned"] and step1[0]["step"] == "Step 1", step1[0])
PINS_A_Z = ["B&B", "Bootcamp", "FirstAid", "Pathoma", "Pixorize", "SketchyImmunology", "SketchyMicro", "SketchyPharm", "^Systems"]
tree_pins = [n["label"] for n in step1 if n["pinned"]]
check(tree_pins == PINS_A_Z, f"pinned resources sort A-Z in the tree: {tree_pins}")
check(not any(n["pinned"] for n in step1[len(tree_pins):]), "pins stay above unpinned resources")
picker_pins = [s["label"] for s in r["scopes"] if s.get("pinned") and s.get("stepIndex") == 0]
check(picker_pins == PINS_A_Z, f"pinned resources sort A-Z in the picker: {picker_pins}")
set_pins = [p["label"] for p in call("settings")["settings"]["pinned"] if p["stepIndex"] == 0]
check(set_pins == PINS_A_Z, f"pinned resources sort A-Z in Settings: {set_pins}")
check(all(n["step"] == "Step 1" for n in step1), "all step 1")
step2 = call("children", key=top[1]["key"])["nodes"]
check(step2 and all(n["step"] == "Step 2" and n["stepIndex"] == 1 for n in step2), "step 2 resources")
group = call("children", key="__group__")["nodes"]
check(group and all(not g.get("group") for g in group), "group children")
sc = call("scopes")["scopes"]
check(any(x["kind"] == "root" and x["label"] == "All of Step 2" for x in sc), "root scopes")
check(all(x.get("group") for x in sc if x["kind"] == "resource"), "resources grouped by step")



def find_topics():
    """Whatever's still unstudied in B&B: a chapter with two free sections beside
    one holding three topics with suspended cards (fully unsuspended ones go
    straight to Done)."""
    for top in call("children", key="#ak_step1_v12::#b&b")["nodes"]:
        if top["status"]:
            continue
        kids = call("children", key=top["key"])["nodes"]
        free = [x for x in kids if x["fresh"] > 0 and x["status"] is None]
        if len(free) < 3:
            continue
        for sub in free:
            topics = [n for n in call("children", key=sub["key"])["nodes"] if n["suspended"] and n["status"] is None]
            if len(topics) >= 3:
                return top, kids, sub, topics[:3]
    raise AssertionError("need a B&B section with three topics with suspended cards")


chapter, sections, ans, leaves = find_topics()
visible = [x["key"] for x in sections + leaves]

b = call("queue", tags=[x["tag"] for x in leaves], visible=visible, selected=ans["key"])
nodes = {x["key"]: x for x in b["nodes"]}
check(nodes[ans["key"]]["check"] == "partial", "parent partial")
check(all(nodes[x["key"]]["status"] == "queued" for x in leaves), "leaves queued")
check(b["details"]["add"] is not None and b["side"]["count"] == len(counts.today_units(col, counts.fresh_ids(col, [x["tag"] for x in leaves], "new"), "new")), b["side"]["count"])

b = call("queue", tags=[ans["tag"]], visible=visible)
nodes = {x["key"]: x for x in b["nodes"]}
check([q["tag"] for q in b["side"]["queued"]] == [ans["tag"]], "parent folds children")
check(nodes[leaves[0]["key"]]["locked"] and nodes[leaves[0]["key"]]["inherited"], "children locked/inherited")

# --- later ---------------------------------------------------------------
lat = [x for x in sections if x["fresh"] > 0 and x["status"] is None and x["key"] != ans["key"]][:2]
b = call("later", tags=[x["tag"] for x in lat], visible=visible)
check([r["tag"] for r in b["side"]["later"]] == [x["tag"] for x in lat], b["side"]["later"])
check(b["side"]["count"] == len(counts.today_units(col, counts.fresh_ids(col, [ans["tag"]], "new"), "new")), "later doesn't count toward the meter")
nodes = {x["key"]: x for x in b["nodes"]}
check(nodes[lat[0]["key"]]["status"] == "later" and nodes[lat[0]["key"]]["check"] == "off", "later node")
check(b["side"]["later"][0]["step"] == "Step 1", "later row step")
check(ud.tags[lat[0]["tag"]]["color"] == "#af52de", "later colour synced")
d = call("details", key=lat[0]["key"])["details"]
check(d["status"] == "later" and d["add"] is not None and d["step"] == "Step 1", d)
# queue the parent: later children fold into it
b = call("queue", tags=[chapter["tag"]], visible=visible)
check(not b["side"]["later"] and b["side"]["queued"][0]["tag"] == chapter["tag"], "fold later into queued parent")
call("unqueue", tags=[chapter["tag"]])
# fill from later respects the limit
call("set_limit", value=25)
call("later", tags=[x["tag"] for x in lat])
plan = call("later_plan")["plan"]
check(plan["after"] <= 25 and plan["picked"] + plan["skipped"] == len(lat), plan)
b = call("fill_from_later")
check(b["side"]["count"] <= 25 and len(b["side"]["later"]) == plan["skipped"], (b["side"]["count"], b["toasts"]))
check(not plan["picked"] or any("from Later" in t for t in b["toasts"]), b["toasts"])
call("set_limit", value=150)
for t in [r["tag"] for r in b["side"]["later"]] + [r["tag"] for r in b["side"]["queued"]]:
    call("clear", tags=[t])
call("queue", tags=[ans["tag"]])

# search + scope + queue all
call("set_scope", value="pinned")
s = call("search", query="pituitary")
check(s["matches"] and s["summary"]["candidates"] > 0 and s["roots"], s["summary"])
check(all(any(m.startswith(p) for p in ("#ak_step1_v12::#b&b", "#ak_step1_v12::#bootcamp", "#ak_step1_v12::#firstaid", "#ak_step1_v12::#pathoma", "#ak_step1_v12::#pixorize", "#ak_step1_v12::#sketch", "#ak_step1_v12::^systems", "#ak_step2_v12::#subjects")) for m in s["matches"]), "pinned scope respected")
call("set_scope", value="#ak_step1_v12::#bootcamp")
s = call("search", query="pituitary")
summary = s["summary"]
b = call("queue_matches", matches=s["matches"], truncated=s["truncated"], visible=[x["key"] for x in s["nodes"]])
check(b["summary"]["candidates"] == 0 and b["summary"]["queued"] == summary["candidates"], b["summary"])
check(any("Queued" in t for t in b["toasts"]), b["toasts"])
call("set_scope", value="#ak_step2_v12")
s2 = call("search", query="pituitary")
check(s2["roots"] == ["__root__:#ak_step2_v12"] and all(m.startswith("#ak_step2_v12") for m in s2["matches"]), s2["roots"])
lb = call("later_matches", matches=s2["matches"], truncated=s2["truncated"])
check(len(lb["side"]["later"]) == s2["summary"]["laterCandidates"], "later all matches")
s2 = call("search", query="pituitary")
check(s2["summary"]["laterCandidates"] == 0 and s2["summary"]["later"] > 0, s2["summary"])
call("set_scope", value="#ak_step1_v12::#bootcamp")
check(len(call("search", query="zzzzqqq")["matches"]) == 0, "no matches")

# limit
b = call("set_limit", value=20)
check(b["side"]["limit"] == 20 and b["side"]["over"], "limit + over")
call("set_limit", value=150)

# complete everything queued -> unsuspends
queued = actions.load_state().queued()
sus = len(counts.suspended_ids(col, queued))
b = call("complete", tags=[])
check(all(r["watched"] for r in b["side"]["queued"]) and len(UNSUSPENDED) == sus, (len(UNSUSPENDED), sus))
check(any("unsuspended" in t.lower() for t in b["toasts"]) or sus == 0, b["toasts"])

# requeue / clear from Completed list, pin toggling, options
done = b["side"]["completed"][0]["tag"]
check(call("queue", tags=[done])["side"]["queued"][0]["tag"] == done, "requeue")
check(all(r["tag"] != done for r in call("clear", tags=[done])["side"]["queued"]), "clear")
r = call("toggle_pin", tag="#AK_Step1_v12::#B&B")
check(not any(x["value"] == "#ak_step1_v12::#b&b" and x["pinned"] for x in r["scopes"]), "unpinned")
b = call("set_option", key="hideCompleted", value=True)
check(b["options"]["hideCompleted"] and mw.addonManager.cfg["hide_completed"], "option saved")
check(call("scopes")["scope"] == "#ak_step1_v12::#bootcamp", "scope persisted, read-only call")

print(f"\nBRIDGE TEST PASSED ({n} checks)")
