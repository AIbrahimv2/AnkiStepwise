# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Per-tag queue status (queued / completed).

Stored in the *collection* config rather than the add-on config, so each
profile has its own queue and it travels with the collection when it syncs.
Pure Python with no Qt imports, so it can be tested outside Anki.
"""

from __future__ import annotations

import time

CONFIG_KEY = "tagQueue"
QUEUED = "queued"
COMPLETED = "completed"
LATER = "later"  # found it, but it doesn't fit this session: park it
STATUSES = (QUEUED, COMPLETED, LATER)
SEP = "::"


def is_under(tag: str, ancestor: str) -> bool:
    """True if `tag` is `ancestor` itself or nested below it (case-insensitive)."""
    t, a = tag.lower(), ancestor.lower()
    return t == a or t.startswith(a + SEP)


class QueueState:
    """Status of each tag. A tag's status also covers everything nested under
    it, so queuing `B&B::16_Neuro` queues every Neuro video's cards."""

    def __init__(self, data: dict | None = None):
        self.tags: dict[str, dict] = {}
        raw = (data or {}).get("tags")
        if isinstance(raw, dict):
            for name, entry in raw.items():
                if isinstance(entry, dict) and entry.get("status") in STATUSES:
                    self.tags[str(name)] = {
                        "status": entry["status"],
                        "at": int(entry.get("at") or 0),
                    }
        self._reindex()

    # --- persistence -----------------------------------------------------

    @classmethod
    def load(cls, col) -> "QueueState":
        return cls(col.get_config(CONFIG_KEY, None))

    def save(self, col) -> None:
        col.set_config(CONFIG_KEY, self.to_dict())

    def to_dict(self) -> dict:
        return {"v": 1, "tags": self.tags}

    # --- lookups ---------------------------------------------------------

    def _reindex(self) -> None:
        self._lower = {k.lower(): k for k in self.tags}

    def _key(self, tag: str) -> str | None:
        return self._lower.get(tag.lower())

    def status(self, tag: str) -> str | None:
        """The tag's own status, ignoring ancestors."""
        k = self._key(tag)
        return self.tags[k]["status"] if k else None

    def since(self, tag: str) -> int:
        """When the tag got its current status."""
        return self.completed_at(tag)

    def completed_at(self, tag: str) -> int:
        k = self._key(tag)
        return self.tags[k]["at"] if k else 0

    def effective(self, tag: str) -> tuple[str | None, str | None]:
        """(status, tag it comes from). The tag's own status wins; otherwise
        the nearest ancestor's applies."""
        parts = tag.split(SEP)
        for i in range(len(parts), 0, -1):
            k = self._key(SEP.join(parts[:i]))
            if k:
                return self.tags[k]["status"], k
        return None, None

    def _with_status(self, status: str, newest_first: bool) -> list[str]:
        rows = [(e["at"], k.lower(), k) for k, e in self.tags.items() if e["status"] == status]
        rows.sort(reverse=newest_first)
        return [k for _, _, k in rows]

    def queued(self) -> list[str]:
        """Queued tags in the order they were added."""
        return self._with_status(QUEUED, newest_first=False)

    def completed(self) -> list[str]:
        """Completed tags, most recently completed first."""
        return self._with_status(COMPLETED, newest_first=True)

    def later(self) -> list[str]:
        """Tags saved for later, oldest first (the order they get queued)."""
        return self._with_status(LATER, newest_first=False)

    # --- changes ---------------------------------------------------------
    # Each mutator returns {tag: new status or None} so callers can mirror
    # the change elsewhere (e.g. Colorful Tags sidebar colours).

    def _set(self, tag: str, status: str, at: int | None = None) -> dict:
        old = self._key(tag)
        if old is not None and old != tag:
            del self.tags[old]
        self.tags[tag] = {"status": status, "at": int(time.time()) if at is None else int(at)}
        self._reindex()
        return {tag: status}

    def _drop(self, tag: str) -> dict:
        k = self._key(tag)
        if k is None:
            return {}
        del self.tags[k]
        self._reindex()
        return {k: None}

    def _fold(self, tag: str, statuses: tuple[str, ...]) -> dict:
        """Drop own statuses of tags nested under `tag` (they're covered)."""
        changes: dict = {}
        for k in [k for k, e in self.tags.items() if e["status"] in statuses]:
            if is_under(k, tag) and k.lower() != tag.lower():
                changes.update(self._drop(k))
        return changes

    def queue(self, tag: str) -> dict:
        """Queue a tag (also takes it off the Later list). Queued or Later
        tags nested under it are folded into it, so the queue never lists
        the same cards twice."""
        changes = self._fold(tag, (QUEUED, LATER))
        changes.update(self._set(tag, QUEUED))
        return changes

    def unqueue(self, tag: str) -> dict:
        return self._drop(tag) if self.status(tag) == QUEUED else {}

    def save_later(self, tag: str) -> dict:
        """Park a tag for a later session (moving it out of the queue if it
        was queued). Later tags nested under it fold into it."""
        changes = self._fold(tag, (LATER,))
        changes.update(self._set(tag, LATER))
        return changes

    def unlater(self, tag: str) -> dict:
        return self._drop(tag) if self.status(tag) == LATER else {}

    def complete(self, tags: list[str], at: int | None = None) -> dict:
        """Mark tags completed, along with any queued or Later tags nested
        under them."""
        now = int(time.time()) if at is None else int(at)
        changes: dict = {}
        for tag in tags:
            for k in [k for k, e in self.tags.items() if e["status"] in (QUEUED, LATER)]:
                if is_under(k, tag) and k.lower() != tag.lower():
                    changes.update(self._set(k, COMPLETED, now))
            changes.update(self._set(tag, COMPLETED, now))
        return changes

    def clear(self, tag: str) -> dict:
        return self._drop(tag)

    def import_status(self, tag: str, status: str, at: int) -> dict:
        return self._set(tag, status, at)
