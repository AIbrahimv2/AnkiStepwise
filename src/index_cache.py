# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""The tag index, saved between sessions.

Building the index reads every card (about 0.7 s on a full AnKing
collection, twice that while Anki is starting up). So it's saved, in the
add-on's user_files folder (never packaged, kept across updates), and read
back when the profile opens, in about 40 ms. A saved index is a session old,
so Stepwise treats it as out of date: it's shown straight away and rebuilt
in the background later, never during startup.

The file holds the index's plain data (dicts, lists, arrays), not the class,
so it doesn't depend on the add-on's folder name; FORMAT guards changes to
the index itself. One file per collection.

It's a pickle, but read back with an unpickler that builds only the plain
types an index holds (Counter, array, bytearray and the built-in
containers), so even a tampered file can't run anything. (Stepwise writes
it to its own folder, which holds its code anyway.)
"""

from __future__ import annotations

import hashlib
import os
import pickle
from dataclasses import fields

from .counts import TagIndex

FORMAT = 1
USER_FILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_files")


def path_for(collection_path: str) -> str:
    key = hashlib.sha1(os.path.abspath(collection_path).encode()).hexdigest()[:12]
    return os.path.join(USER_FILES, f"index-{key}.pickle")


def save(collection_path: str, index: TagIndex) -> None:
    """Write the index (atomically: a half-written file is never read)."""
    target = path_for(collection_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    data = {"format": FORMAT, "fields": {f.name: getattr(index, f.name) for f in fields(TagIndex)}}
    tmp = target + ".tmp"
    with open(tmp, "wb") as fh:
        pickle.dump(data, fh, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, target)


# What an index's data is made of, and nothing else.
_ALLOWED = {
    ("collections", "Counter"),
    ("array", "array"),
    ("array", "_array_reconstructor"),
    ("builtins", "bytearray"),
}


class _PlainUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str):
        if (module, name) not in _ALLOWED:
            raise pickle.UnpicklingError(f"not part of a tag index: {module}.{name}")
        return super().find_class(module, name)


def load(collection_path: str, mode: str) -> TagIndex | None:
    """The saved index, if there is one for this collection, counted the
    way the settings now say. Anything unreadable is ignored."""
    try:
        with open(path_for(collection_path), "rb") as fh:
            data = _PlainUnpickler(fh).load()
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            return None
        index = TagIndex(**data["fields"])
    except Exception:  # missing, from another version, or damaged
        return None
    return index if index.mode == mode else None
