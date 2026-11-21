#!/usr/bin/env python3
"""Make the screenshot for the README and the AnkiWeb listing.

    python3 tools/screenshots.py [--collection PATH] [--plain] [--capture-wallpaper | --wallpaper PATH]

Writes docs/screenshot.png: the Stepwise window at its default width, drawn
at 120% (ZOOM, as Cmd+= draws it) so it reads at the listing's width: the
tag tree on your pinned resources (PINS: a few in each of Step 1, 2 and 3,
each with its logo), one of them open (OPEN) with its first topic selected,
and today's queue. It's on AnkiGlass's glass, as AnkiGlass gives an add-on's
window (--plain for none). From a copy of a collection
(tests/fixture/collection.anki2 unless --collection names another) served
by tools/devserver.py with Anki's own Python (ANKI_PYTHON, or the
launcher's). The collection itself is never touched; the pins and the scope
are set in the dev server's config, which it keeps in memory.

It's made with the add-ons' shared screenshot tools, in the kit's checkout
next to this one (../anki-addon-kit/screenshots/shots.py, or set
ANKI_ADDON_KIT), which describe how they look and what they need.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
FIXTURE = os.path.join(ROOT, "tests", "fixture")
KIT = os.environ.get("ANKI_ADDON_KIT", os.path.join(os.path.dirname(ROOT), "anki-addon-kit"))
sys.path.insert(0, os.path.join(KIT, "screenshots"))
import shots  # noqa: E402

SIZE = (1140, 800)  # the window's default width (src/ui.py), a little taller for the pinned resources
ZOOM = 1.2  # how big it draws in that size (the kit's zoom.py, Cmd+=)
# Pinned, so the tree shows Steps 1, 2 and 3 in one window, a few resources
# each (and their logos).
PINS = ["#AK_Step1_v12::#B&B", "#AK_Step1_v12::#Bootcamp", "#AK_Step1_v12::#FirstAid", "#AK_Step1_v12::#Pathoma",
        "#AK_Step2_v12::#AMBOSS", "#AK_Step2_v12::#SketchyFM", "#AK_Step2_v12::#UWorld",
        "#AK_Step3_v12::#NBME", "#AK_Step3_v12::#OME", "#AK_Step3_v12::#UWorld"]
OPEN = (3, "NBME")  # the resource shown open (Step 3's): two forms, the first small enough to fit the day
SETUP = """(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const tops = () => [...document.querySelectorAll('.row.top')];
  for (let i = 0; i < 100 && !tops().length; i++) await sleep(100);
  if (!tops().length) throw new Error('no resources in the tag tree');
  // The offer to import Colorful Tags' colours: answered once, in the copy.
  const notNow = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Not now');
  if (notNow) { notNow.click(); await sleep(300); }
  for (const open of document.querySelectorAll('.row.top[aria-expanded="true"]')) {
    open.querySelector('.chev').click();
    await sleep(200);
  }
  // The steps' rows in order: OPEN is the one under its step's header.
  const rows = () => [...document.querySelectorAll('.tree .row')];
  const find = () => {
    let step = null;
    for (const r of rows()) {
      // A step's header is classed by its index: step-0 for Step 1.
      if (r.classList.contains('section')) step = [...r.classList].find((c) => c.startsWith('step-'));
      else if (step === %(step)s && r.classList.contains('top') && r.querySelector('.label')?.textContent.trim() === %(name)s) return r;
    }
    return null;
  };
  const row = find();
  if (!row) throw new Error('no ' + %(name)s + ' under ' + %(step)s);
  row.querySelector('.chev').click();
  for (let i = 0; i < 30 && row.getAttribute('aria-expanded') !== 'true'; i++) await sleep(100);
  await sleep(400);
  // Its first topic selected, so the bar under the tree says what it adds.
  const all = rows();
  const topic = all[all.indexOf(find()) + 1];
  if (!topic || topic.classList.contains('top')) throw new Error(%(name)s + ' has no topics showing');
  topic.click();
  await sleep(500);
  return [...document.querySelectorAll('.tree .row')].map((r) => r.querySelector('.label')?.textContent.trim()).join(', ');
})()""" % {"step": json.dumps(f"step-{OPEN[0] - 1}"), "name": json.dumps(OPEN[1])}


def bridge(port: int, cmd: str, **args) -> dict:
    """One of the page's commands, sent to the dev server's bridge."""
    req = urllib.request.Request(f"http://127.0.0.1:{port}/bridge", data=json.dumps({"cmd": cmd, **args}).encode(),
                                 method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


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
    ap.add_argument("--plain", action="store_true", help="without AnkiGlass")
    shots.add_wallpaper_args(ap)
    args = ap.parse_args()
    if not os.path.isfile(args.collection):
        raise SystemExit(f"no collection at {args.collection}: pass --collection")
    glass = None if args.plain else shots.load_glass()
    with shots.Session() as s:
        port = shots.free_port()
        cmd = [anki_python(), os.path.join(ROOT, "tools", "devserver.py"), "--collection", args.collection,
               "--port", str(port)]
        if os.path.isfile(args.colorful_tags):
            cmd += ["--colorful-tags", args.colorful_tags]
        dev = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            shots.wait_for(f"http://127.0.0.1:{port}/", timeout=60)
            for tag in PINS:
                bridge(port, "toggle_pin", tag=tag)
            bridge(port, "set_scope", value="pinned")
            s.capture([{"url": f"http://127.0.0.1:{port}/?theme=dark", "width": SIZE[0], "height": SIZE[1],
                        "setup": SETUP, "zoom": ZOOM, "wait": 800, "out": "stepwise.png",
                        "result": s.path("rows.json"),
                        **({"preload": glass["window"], "transparent": True} if glass else {})}])
        finally:
            dev.terminate()
        with open(s.path("rows.json")) as f:
            print("tree:", json.load(f))
        written = s.frames([{"image": "stepwise.png", "size": SIZE, "title": "Stepwise", "out": "screenshot.png",
                            "tint": glass and glass["tint"]}],
                           shots.wallpaper_for(args, s), DOCS)
    for out in written:
        print("wrote", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    main()
