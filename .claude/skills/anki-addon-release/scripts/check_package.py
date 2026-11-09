#!/usr/bin/env python3
"""Check a built .ankiaddon before it's published.

    check_package.py dist/<name>.ankiaddon [src]

Fails (exit 1) if the zip has a parent folder, holds anything that mustn't
ship (__pycache__, .pyc, meta.json with the user's settings, user_files/,
.DS_Store), misses or changes a file git tracks in src/, or has a manifest
without package, name and a homepage on GitHub that exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

FORBIDDEN = ("__pycache__/", ".pyc", ".DS_Store")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pkg = Path(sys.argv[1])
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("src")
    problems: list[str] = []
    with zipfile.ZipFile(pkg) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        data = {n: z.read(n) for n in names}

    # Layout: the add-on's files at the top, no parent folder.
    if "manifest.json" not in data and "__init__.py" not in data:
        tops = sorted({n.split("/")[0] for n in names})
        problems.append(f"no manifest.json or __init__.py at the top (a parent folder?): {tops[:5]}")
    for n in names:
        if any(f in n for f in FORBIDDEN) or n == "meta.json" or n.endswith("/meta.json") or n.startswith("user_files/"):
            problems.append(f"shouldn't ship: {n}")

    # Every file git tracks in src/ is in the package, unchanged.
    tracked = subprocess.run(["git", "ls-files"], cwd=src, capture_output=True, text=True)
    if tracked.returncode == 0:
        for rel in tracked.stdout.split():
            if rel == "meta.json" or rel.startswith("user_files/"):
                continue
            if rel not in data:
                problems.append(f"missing from the package: {rel}")
            elif data[rel] != (src / rel).read_bytes():
                problems.append(f"differs from src/ (rebuild?): {rel}")
    else:
        print("note: src/ isn't in a git repo; skipped the file comparison")

    # Manifest.
    manifest = {}
    try:
        manifest = json.loads(data.get("manifest.json", b"{}"))
    except ValueError as e:
        problems.append(f"manifest.json isn't valid JSON: {e}")
    for field in ("package", "name", "homepage"):
        if not manifest.get(field):
            problems.append(f"manifest.json has no {field}")
    home = str(manifest.get("homepage", ""))
    if home.startswith("https://github.com/"):
        repo = "/".join(home.removeprefix("https://github.com/").split("/")[:2])
        r = subprocess.run(["gh", "repo", "view", repo, "--json", "visibility", "--jq", ".visibility"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            problems.append(f"homepage repo {repo} doesn't exist (or gh can't see it)")
        elif r.stdout.strip() != "PUBLIC":
            problems.append(f"homepage repo {repo} is {r.stdout.strip().lower()}, so the link won't open for users")

    size = pkg.stat().st_size
    print(f"{pkg}: {len(names)} files, {size:,} bytes, manifest {manifest.get('name')!r} ({manifest.get('package')})")
    for p in problems:
        print(f"  PROBLEM: {p}")
    if problems:
        return 1
    print("  OK: layout, contents, src/ match and manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
