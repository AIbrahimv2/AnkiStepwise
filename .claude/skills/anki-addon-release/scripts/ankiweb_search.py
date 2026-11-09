#!/usr/bin/env python3
"""Where an add-on shows up in AnkiWeb's add-on search. Read-only.

    ankiweb_search.py --id 1949793886 "unsuspend" "study planner" "usmle"

For each query: how many add-ons match, the add-on's rank (or "absent"), and
how many of the results have any ratings (results are sorted by ratings).
AnkiWeb answers HTTP 429 when asked too quickly, so this waits between
queries and retries.

The endpoint returns protobuf; this decodes just enough of it: each result
is field 1, holding id (1), title (2), thumbs up (3) and thumbs down (4).
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://ankiweb.net/svc/shared/list-addons?search="


def parse(b: bytes) -> list[tuple[int, object]]:
    out, i = [], 0

    def varint() -> int:
        nonlocal i
        v = s = 0
        while True:
            x = b[i]
            i += 1
            v |= (x & 127) << s
            s += 7
            if not x & 128:
                return v

    while i < len(b):
        key = varint()
        field, wire = key >> 3, key & 7
        if wire == 2:
            n = varint()
            out.append((field, bytes(b[i:i + n])))
            i += n
        elif wire == 0:
            out.append((field, varint()))
        elif wire == 5:
            i += 4
        elif wire == 1:
            i += 8
        else:
            break
    return out


def search(query: str) -> list[dict]:
    req = urllib.request.Request(URL + urllib.parse.quote(query), headers={"User-Agent": "addon-listing-check"})
    data = urllib.request.urlopen(req, timeout=30).read()
    rows = []
    for field, value in parse(data):
        if field == 1 and isinstance(value, bytes):
            m = dict(parse(value))
            title = m.get(2, b"")
            rows.append({"id": m.get(1), "title": title.decode("utf8", "replace") if isinstance(title, bytes) else "",
                         "up": m.get(3, 0), "down": m.get(4, 0)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", type=int, required=True, help="the add-on's AnkiWeb ID")
    ap.add_argument("--pause", type=float, default=5.0, help="seconds between queries")
    ap.add_argument("--top", type=int, default=0, help="also list the first N results")
    ap.add_argument("queries", nargs="+")
    args = ap.parse_args()
    for n, q in enumerate(args.queries):
        if n:
            time.sleep(args.pause)
        rows = None
        for attempt in range(4):
            try:
                rows = search(q)
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or attempt == 3:
                    print(f"{q:28} HTTP {e.code}")
                    break
                time.sleep(int(e.headers.get("Retry-After") or 45))
        if rows is None:
            continue
        rank = next((i + 1 for i, r in enumerate(rows) if r["id"] == args.id), None)
        rated = sum(1 for r in rows if r["up"] or r["down"])
        print(f"{q:28} {len(rows):5} results  {('#' + str(rank)) if rank else 'absent':>7}  {rated} rated", flush=True)
        for r in rows[: args.top]:
            print(f"{'':30}{r['up']:>4}/{r['down']:<3} {r['title'][:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
