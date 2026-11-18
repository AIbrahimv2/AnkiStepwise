#!/usr/bin/env python3
"""Make the screenshot for the README and the AnkiWeb listing.

    python3 tools/screenshots.py [--collection PATH] [--capture-wallpaper | --wallpaper PATH]

Writes docs/screenshot.png: the Stepwise window at its default size, the
tag tree with B&B open and today's queue, from a copy of a collection
(tests/fixture/collection.anki2 unless --collection names another) served
by tools/devserver.py with Anki's own Python (ANKI_PYTHON, or the
launcher's). The collection itself is never touched.

It's made with the add-ons' shared screenshot tools, in the kit's checkout
next to this one (../anki-addon-kit/screenshots/shots.py, or set
ANKI_ADDON_KIT), which describe how they look and what they need.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FIXTURE = os.path.join(ROOT, "tests", "fixture")
KIT = os.environ.get("ANKI_ADDON_KIT", os.path.join(os.path.dirname(ROOT), "anki-addon-kit"))
sys.path.insert(0, os.path.join(KIT, "screenshots"))
import shots  # noqa: E402

SIZE = (1140, 760)  # the window's default size (src/ui.py)
SETUP = """(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let row;
  for (let i = 0; i < 100 && !row; i++) {
    row = [...document.querySelectorAll('.row.top')].find((r) => r.querySelector('.label')?.textContent.trim() === 'B&B');
    if (!row) await sleep(100);
  }
  if (!row) throw new Error('no B&B row in the tag tree');
  // The offer to import Colorful Tags' colours: answered once, in the copy.
  const notNow = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Not now');
  if (notNow) { notNow.click(); await sleep(300); }
  row.querySelector('.chev').click();
  await sleep(400);
  if (row.getAttribute('aria-expanded') !== 'true') throw new Error("B&B didn't open");
  return true;
})()"""


def anki_python() -> str:
    found = os.environ.get("ANKI_PYTHON") or "".join(sorted(glob.glob(os.path.expanduser(
        "~/Library/Application Support/AnkiProgramFiles/python/*/bin/python3")))[-1:])
    if not found:
        raise SystemExit("Anki's Python wasn't found: set ANKI_PYTHON")
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", default=os.path.join(FIXTURE, "collection.anki2"))
    ap.add_argument("--colorful-tags", default=os.path.join(FIXTURE, "colorful_tags.json"),
                    help="Colorful Tags data to simulate the add-on with, if the file exists")
    shots.add_wallpaper_args(ap)
    args = ap.parse_args()
    if not os.path.isfile(args.collection):
        raise SystemExit(f"no collection at {args.collection}: pass --collection")
    with shots.Session() as s:
        port = shots.free_port()
        cmd = [anki_python(), os.path.join(ROOT, "tools", "devserver.py"), "--collection", args.collection,
               "--port", str(port)]
        if os.path.isfile(args.colorful_tags):
            cmd += ["--colorful-tags", args.colorful_tags]
        dev = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            shots.wait_for(f"http://127.0.0.1:{port}/", timeout=60)
            s.capture([{"url": f"http://127.0.0.1:{port}/?theme=dark", "width": SIZE[0], "height": SIZE[1],
                        "setup": SETUP, "wait": 800, "out": "stepwise.png"}])
        finally:
            dev.terminate()
        written = s.frames([{"image": "stepwise.png", "size": SIZE, "title": "Stepwise", "out": "screenshot.png"}],
                           shots.wallpaper_for(args, s), DOCS)
    for out in written:
        print("wrote", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
