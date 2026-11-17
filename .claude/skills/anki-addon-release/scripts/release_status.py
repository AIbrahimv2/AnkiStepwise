#!/usr/bin/env python3
"""What's waiting to be released, for every add-on.

    release_status.py              # all the add-ons beside the kit
    release_status.py -v           # and list each change and commit
    release_status.py --fetch      # look at origin first (otherwise as last fetched)
    release_status.py --offline    # skip asking GitHub about releases

For each add-on: its newest version, the version AnkiWeb has (as recorded in
docs/ankiweb-listing.md), the changes under Unreleased in CHANGELOG.md, and
what needs doing: commits since the last release that the changelog doesn't
mention, work not committed or pushed, a kit copy that's behind, a version
missing its GitHub release, or AnkiWeb behind GitHub. Nothing here goes to
AnkiWeb.
"""

from __future__ import annotations

import argparse
import sys
import unicodedata

from addons import KIT, Addon, all_addons, ankiweb_record, git, next_version, run, version_key

SHIPPED = ["src", "web", "build.sh"]  # paths whose changes reach users


def changes_since(addon: Addon, version: str) -> list[str]:
    """Commits since v<version> that change what ships."""
    if not addon.tag_exists(version):
        return []
    out = git(addon.path, "log", "--format=%h %s", f"v{version}..HEAD", "--", *SHIPPED)
    return [line for line in out.splitlines() if line]


def github_release_missing(addon: Addon, version: str) -> bool:
    if not addon.github:
        return False
    r = run(["gh", "release", "view", f"v{version}", "-R", addon.github, "--json", "tagName"], addon.path, check=False)
    return r.returncode != 0


def status(addon: Addon, args) -> dict:
    latest = addon.latest
    record = ankiweb_record(addon)
    items = addon.unreleased_items
    notes: list[str] = []

    dirty = [line for line in git(addon.path, "status", "--porcelain").splitlines() if line]
    if dirty:
        notes.append(f"{len(dirty)} uncommitted {'file' if len(dirty) == 1 else 'files'}")
    counts = git(addon.path, "rev-list", "--left-right", "--count", "@{u}...HEAD", check=False).split()
    if len(counts) == 2:
        behind, ahead = map(int, counts)
        if ahead:
            notes.append(f"{ahead} {'commit' if ahead == 1 else 'commits'} not pushed")
        if behind:
            notes.append(f"{behind} behind origin")
    if (addon.path / "src" / "kit").exists() and KIT.exists():
        if run([sys.executable, str(KIT / "sync.py"), "--check", str(addon.path)], KIT, check=False).returncode:
            notes.append("kit copy behind")

    since = changes_since(addon, latest) if latest else []
    if latest and not addon.tag_exists(latest):
        notes.append(f"{latest} isn't tagged")
    elif since and not items:
        notes.append(f"{len(since)} {'commit' if len(since) == 1 else 'commits'} since v{latest} with nothing under Unreleased")
    if latest and addon.tag_exists(latest) and not args.offline and github_release_missing(addon, latest):
        notes.append(f"no GitHub release for v{latest}")
    if addon.ankiweb and latest and (not record or version_key(record[0]) < version_key(latest)):
        notes.append(f"AnkiWeb needs {latest}" + (f" (has {record[0]})" if record else " (not recorded)"))

    return {
        "addon": addon,
        "latest": latest or "none",
        "ankiweb": record[0] if record else ("not listed" if not addon.ankiweb else "?"),
        "waiting": f"{len(items)} → {next_version(latest, addon.unreleased)}" if items else "nothing",
        "notes": notes,
        "items": items,
        "since": since,
    }


def width(text: str) -> int:
    """Columns on a terminal: emoji and wide characters take two."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 0 if unicodedata.combining(c) or c == "\ufe0f" else 1 for c in text)


def table(rows: list[list[str]]) -> str:
    widths = [max(width(r[i]) for r in rows) for i in range(len(rows[0]) - 1)]
    return "\n".join(
        "  ".join(cell + " " * (w - width(cell)) for cell, w in zip(r, widths)) + "  " + r[-1] for r in rows
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true", help="list the changes and commits")
    p.add_argument("--fetch", action="store_true", help="git fetch each repo first")
    p.add_argument("--offline", action="store_true", help="don't ask GitHub about releases")
    args = p.parse_args()

    addons = all_addons()
    if args.fetch:
        for a in addons:
            git(a.path, "fetch", "--quiet", "origin", check=False)
    found = [status(a, args) for a in addons]

    rows = [["Add-on", "Released", "AnkiWeb", "Unreleased", "To do"]]
    for s in found:
        a = s["addon"]
        rows.append([f"{a.emoji} {a.name}".strip(), s["latest"], s["ankiweb"], s["waiting"], "; ".join(s["notes"]) or "-"])
    print(table(rows))

    if args.verbose:
        for s in found:
            if not (s["items"] or s["since"]):
                continue
            print(f"\n{s['addon'].name}")
            for title, item in s["items"]:
                print(f"  [{title or 'Unreleased'}] {item[:110]}{'…' if len(item) > 110 else ''}")
            if s["since"]:
                print(f"  Commits since v{s['latest']} that change what ships:")
                for line in s["since"]:
                    print(f"    {line}")

    ready = [s for s in found if s["items"]]
    if ready:
        print("\nReady to release: " + ", ".join(f"{s['addon'].name} {s['waiting'].split('→ ')[1]}" for s in ready))
        print("Each one: release.py <repo> (a dry run), then release.py <repo> --publish.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
