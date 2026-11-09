"""The Stepwise name, with no mark anywhere: window title (no custom icon),
deck-screen meter, manifest, docs."""
import os

from harness import *  # noqa: F401,F403
from harness import SRC, mw, ui, widget

ui.restoreGeom = ui.saveGeom = lambda *a, **k: None
d = ui.QueueDialog(mw)
assert d.windowTitle() == "Stepwise"
assert not hasattr(ui, "ICONS") and not os.path.exists(os.path.join(SRC, "icons"))
print("window title set, no custom icon")

html = widget.build_widget()
assert '<span class="tq-label">Stepwise</span>' in html and 'title="Open Stepwise"' in html
assert "<svg" not in html and "tq-mark" not in html
assert "Tag queue" not in html and "Tag Queue" not in html
print("deck-screen meter: name only, no mark")

readme = open(os.path.join(SRC, "..", "README.md")).read()
assert readme.startswith("# Stepwise\n") and "stepwise.svg" not in readme
print("README header: name only")

import json
man = json.load(open(os.path.join(SRC, "manifest.json")))
assert man["name"] == "Stepwise" and man["package"] == "tag_queue", man
print("manifest: Stepwise, package folder unchanged")
print("BRAND TESTS PASSED")
