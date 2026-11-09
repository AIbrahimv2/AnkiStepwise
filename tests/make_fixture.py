#!/usr/bin/env python3
"""Snapshot a real collection and its Colorful Tags data into tests/fixture/.

The tests run against this frozen copy, so what you do in Anki afterwards can't
change their results. It holds your cards, so it stays out of git. It's only
read from the profile, never written to. Run it again to test against newer data.

    python3 tests/make_fixture.py [profile]    (default: Default)

The tests expect an AnKing deck (#AK_Step1_v12 and friends) with Colorful Tags
installed. Close Anki first if you can: it's fine open, but a change it's halfway
through writing may not make it into the copy.
"""

import os
import shutil
import sys

ANKI = os.path.expanduser("~/Library/Application Support/Anki2")
COLORFUL_TAGS = os.path.join(ANKI, "addons21", "594329229", "user_files", "data.json")
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture")


def main() -> None:
    profile = sys.argv[1] if len(sys.argv) > 1 else "Default"
    source = os.path.join(ANKI, profile, "collection.anki2")
    if not os.path.exists(source):
        sys.exit(f"No collection at {source}")
    if not os.path.exists(COLORFUL_TAGS):
        sys.exit(f"No Colorful Tags data at {COLORFUL_TAGS}")

    os.makedirs(FIXTURE, exist_ok=True)
    wal = os.path.join(FIXTURE, "collection.anki2-wal")
    if os.path.exists(wal):
        os.unlink(wal)
    shutil.copy(source, FIXTURE)
    if os.path.exists(source + "-wal"):
        shutil.copy(source + "-wal", FIXTURE)
    shutil.copy(COLORFUL_TAGS, os.path.join(FIXTURE, "colorful_tags.json"))
    print(f"Snapshotted profile {profile!r} to {FIXTURE}")


if __name__ == "__main__":
    main()
