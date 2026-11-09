import json
from harness import *  # noqa
from harness import actions, load_colorful_tags_copy
from tq.bridge import Bridge
from aqt.qt import QWidget
ud = load_colorful_tags_copy()
class Host(QWidget):
    index = None
    def request_index(self): actions.request_index(self._set)
    def reload_index(self, force=False): self.request_index()
    def _set(self, i): self.index = i
    def push(self, e): pass
host = Host(); b = Bridge(host)
call = lambda cmd, **a: b.handle(json.dumps({"cmd": cmd, **a}))
call("boot")
info = call("import_info")
print({g["color"]: g["count"] for g in info["groups"]})
other = next(g["color"] for g in info["groups"] if g["color"] != "#00f900")
r = call("import_colors", choices={other: "later", "#00f900": "completed"}, pins=False)
print(r["toasts"])
st = actions.load_state()
print("later:", len(st.later()), "completed:", len(st.completed()), "queued:", len(st.queued()))
assert len(st.later()) > 0 and not st.queued()
assert all(ud.tags[t]["color"] == "#af52de" for t in st.later()), "later tags recoloured purple"
print("IMPORT-AS-LATER OK")
