# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Undo and redo for changes made in the Stepwise window.

Each step keeps the queue's saved state just before and just after one
action, plus any cards that action unsuspended. Undoing puts back, tag by
tag, only what that action changed, so changes made since elsewhere (the
Browser sidebar, automatic Done) are left alone. Cards it unsuspended are
suspended again if they're still unstudied. History lives in memory for
the session and is cleared when the profile closes.
"""

from __future__ import annotations

import copy

from anki.utils import ids2str
from aqt import mw

from . import actions

LIMIT = 50

_undo: list[dict] = []
_redo: list[dict] = []


def snapshot() -> dict:
    return copy.deepcopy(actions.load_state().to_dict())


def record(label: str, before: dict, after: dict, unsuspended: list[int]) -> None:
    """Remember one action (a no-op leaves no step). A new action clears redo."""
    if before == after and not unsuspended:
        return
    _undo.append({"label": label, "before": before, "after": after, "cards": list(unsuspended)})
    del _undo[:-LIMIT]
    _redo.clear()


def reset() -> None:
    _undo.clear()
    _redo.clear()


def undo(parent=None) -> str | None:
    """Undo the last action; returns its label, or None if there's nothing."""
    if not _undo:
        return None
    step = _undo.pop()
    _apply(step["after"], step["before"])
    if step["cards"]:
        _set_suspended(step["cards"], True, parent)
    _redo.append(step)
    return step["label"]


def redo(parent=None) -> str | None:
    if not _redo:
        return None
    step = _redo.pop()
    _apply(step["before"], step["after"])
    if step["cards"]:
        _set_suspended(step["cards"], False, parent)
    _undo.append(step)
    return step["label"]


def _entries(saved: dict) -> dict[str, tuple[str, dict]]:
    return {name.lower(): (name, entry) for name, entry in (saved.get("tags") or {}).items()}


def _apply(src: dict, dst: dict) -> None:
    """Change the current state the way going from `src` to `dst` would,
    touching only the tags and session entries that differ between them."""
    state = actions.load_state()
    a, b = _entries(src), _entries(dst)
    changes: dict = {}
    for low in set(a) | set(b):
        if a.get(low, ("", None))[1] == b.get(low, ("", None))[1]:
            continue
        if low in b:
            name, entry = b[low]
            changes.update(state._set(name, entry["status"], entry["at"]))
        else:
            changes.update(state._drop(a[low][0]))
    was = {t.lower() for t in src.get("session") or []}
    now = dst.get("session") or []
    for tag in now:
        if tag.lower() not in was and tag.lower() not in {t.lower() for t in state.session}:
            state.session.append(tag)
    for low in was - {t.lower() for t in now}:
        state.leave_session(low)
    # No automatic tidy-up: that would immediately redo what's being undone.
    actions.commit(state, changes, tidy=False)


def _set_suspended(cids: list[int], suspend: bool, parent) -> None:
    col = mw.col
    if suspend:
        # Only cards still unstudied: anything reviewed since stays in play.
        ids = col.db.list(f"select id from cards where id in {ids2str(cids)} and type = 0 and queue != -1")
        if ids:
            actions.suspend_cards(parent=parent or mw, card_ids=ids).run_in_background()
    else:
        ids = col.db.list(f"select id from cards where id in {ids2str(cids)} and queue = -1")
        if ids:
            actions.unsuspend_cards(parent=parent or mw, card_ids=ids).run_in_background()
