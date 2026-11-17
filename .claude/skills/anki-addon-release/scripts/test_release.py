"""Tests for the release scripts' pure parts. Run: python3 test_release.py
(from this folder), or python3 -m unittest discover <this folder>."""

from __future__ import annotations

import unittest
from pathlib import Path

from addons import Addon, next_version, record_upload, release_changelog, release_notes, version_key

CHANGELOG = """# Changelog

## [Unreleased]

### Changed

- **A wider window.** It reads better.

## [1.2.0] - 2026-11-17

### Added

- Something.
"""


def unreleased(*titles: str) -> dict:
    return {"version": None, "date": None, "sections": [{"title": t, "items": ["x"]} for t in titles]}


class Versions(unittest.TestCase):
    def test_features_bump_minor(self):
        self.assertEqual(next_version("1.2.0", unreleased("Added")), "1.3.0")
        self.assertEqual(next_version("1.2.3", unreleased("Changed", "Fixed")), "1.3.0")
        self.assertEqual(next_version("1.2.0", unreleased("")), "1.3.0")  # bullets with no heading

    def test_fixes_alone_bump_patch(self):
        self.assertEqual(next_version("1.2.0", unreleased("Fixed")), "1.2.1")
        self.assertEqual(next_version("1.1.1", unreleased("Fixed", "Security")), "1.1.2")

    def test_first_release(self):
        self.assertEqual(next_version(None, unreleased("Added")), "1.0.0")

    def test_order(self):
        self.assertLess(version_key("1.9.2"), version_key("1.10.0"))


class Changelog(unittest.TestCase):
    def test_bracketed(self):
        out = release_changelog(CHANGELOG, "1.3.0", "2026-11-20")
        self.assertIn("## [1.3.0] - 2026-11-20\n\n### Changed", out)
        self.assertNotIn("Unreleased", out)
        self.assertIn("## [1.2.0] - 2026-11-17", out)

    def test_plain(self):
        text = "# Changelog\n\n## Unreleased\n\n### Fixed\n- A fix.\n\n## 1.2.0 - 2026-11-17\n"
        self.assertIn("## 1.2.1 - 2026-11-20\n", release_changelog(text, "1.2.1", "2026-11-20"))

    def test_needs_unreleased(self):
        with self.assertRaises(ValueError):
            release_changelog("## [1.2.0] - 2026-11-17\n", "1.3.0", "2026-11-20")


def addon(ankiweb: int | None) -> Addon:
    return Addon(Path("."), "x", "X", "", "AIbrahimv2/X", ankiweb, "dist/x.ankiaddon")


class Notes(unittest.TestCase):
    release = {"version": None, "date": None, "sections": [
        {"title": "Added", "items": ["**New.** Thing."]},
        {"title": "Fixed", "items": []},
    ]}

    def test_sections_and_install(self):
        notes = release_notes(addon(123), self.release)
        self.assertIn("### Added\n\n- **New.** Thing.\n", notes)
        self.assertNotIn("Fixed", notes)  # empty sections are left out
        self.assertIn("[AnkiWeb](https://ankiweb.net/shared/info/123) with the code 123.", notes)

    def test_not_on_ankiweb(self):
        notes = release_notes(addon(None), self.release)
        self.assertIn("download `x.ankiaddon` below and double-click it.", notes)
        self.assertNotIn("AnkiWeb", notes)


class Record(unittest.TestCase):
    listing = "# AnkiWeb listing\n\nWhat's live.\n\n## Title\n\nX\n"

    def test_added_before_the_first_section(self):
        out = record_upload(self.listing, "1.2.0", "2026-11-17")
        self.assertTrue(out.startswith("# AnkiWeb listing\n\nWhat's live.\n\n## Package on AnkiWeb\n\nVersion 1.2.0, uploaded 2026-11-17."))
        self.assertIn("\n## Title\n", out)

    def test_updated_in_place(self):
        once = record_upload(self.listing, "1.2.0", "2026-11-17")
        twice = record_upload(once, "1.3.0", "2026-11-20")
        self.assertIn("Version 1.3.0, uploaded 2026-11-20. The release script", twice)
        self.assertNotIn("1.2.0", twice)
        self.assertEqual(twice.count("## Package on AnkiWeb"), 1)


if __name__ == "__main__":
    unittest.main()
