# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Read an add-on's CHANGELOG.md (Keep a Changelog) into releases.

Plain Python with no Anki imports, so tests can run it. Takes headings like
`## [1.2.0] - 2026-11-09`, `## 1.2.0 - 2026-11-09`, `## 1.0.0` and
`## [Unreleased]`, `### Added`-style sections (or bullets straight under the
version), and bullets that run on over indented lines.

Don't edit a vendored copy (src/kit/ in an add-on): change it in
anki-addon-kit and run its sync.py.
"""

from __future__ import annotations

import re

_VERSION = re.compile(
    r"^##\s+\[?(?P<version>[^\]\s]+)\]?(?:\s+[-–]\s+(?P<date>\d{4}-\d{2}-\d{2}))?\s*$"
)
_SECTION = re.compile(r"^###\s+(?P<title>.+?)\s*$")
_BULLET = re.compile(r"^(?P<indent>\s*)[-*]\s+(?P<text>.*)$")


def parse(text: str) -> list[dict]:
    """Releases, newest first, as {version, date, sections: [{title, items}]}.
    `version` is None for the Unreleased heading."""
    releases: list[dict] = []
    release: dict | None = None
    section: dict | None = None
    item: list[str] | None = None

    def close_item() -> None:
        nonlocal item
        if item is not None and section is not None:
            section["items"].append(" ".join(item).strip())
        item = None

    for line in text.splitlines():
        m = _VERSION.match(line)
        if m:
            close_item()
            version = m.group("version")
            release = {
                "version": None if version.lower() == "unreleased" else version,
                "date": m.group("date"),
                "sections": [],
            }
            releases.append(release)
            section = None
            continue
        if release is None:
            continue  # the title and introduction
        m = _SECTION.match(line)
        if m:
            close_item()
            section = {"title": m.group("title"), "items": []}
            release["sections"].append(section)
            continue
        m = _BULLET.match(line)
        if m and len(m.group("indent")) < 2:
            close_item()
            if section is None:
                section = {"title": "", "items": []}
                release["sections"].append(section)
            item = [m.group("text").strip()]
            continue
        if item is not None and line.strip():
            # A line that runs on, or a nested bullet: part of the same item.
            nested = _BULLET.match(line)
            item.append(nested.group("text").strip() if nested else line.strip())
        elif not line.strip():
            continue
    close_item()
    return releases


def latest_version(releases: list[dict]) -> str | None:
    """The newest released version (Unreleased doesn't count)."""
    for r in releases:
        if r["version"]:
            return r["version"]
    return None


def version_key(version: str | None) -> tuple:
    """Sorts "1.10.0" after "1.9.2"; anything unparseable sorts first."""
    if not version:
        return ()
    parts = []
    for p in re.split(r"[.\-+]", version):
        parts.append((0, int(p), "") if p.isdigit() else (1, 0, p))
    return tuple(parts)


def newer(a: str | None, b: str | None) -> bool:
    """True if version a is newer than version b."""
    return bool(a) and version_key(a) > version_key(b)
