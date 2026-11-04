# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Operations shared by the Tag Queue window, the browser sidebar menu and
the deck-screen widget, plus the cached tag index."""

from __future__ import annotations

from typing import Callable

import aqt
from aqt import mw
from aqt.operations import QueryOp
from aqt.operations.scheduling import unsuspend_cards
from aqt.utils import tooltip

from . import colorsync
from .config import get_config
from .counts import TagIndex, build_index, suspended_ids, tags_search
from .state import QueueState

# --- state + listeners -------------------------------------------------------

_listeners: list[Callable[[], None]] = []


def subscribe(fn: Callable[[], None]) -> None:
    if fn not in _listeners:
        _listeners.append(fn)


def unsubscribe(fn: Callable[[], None]) -> None:
    if fn in _listeners:
        _listeners.remove(fn)


def load_state() -> QueueState:
    return QueueState.load(mw.col)


def commit(state: QueueState, changes: dict) -> None:
    state.save(mw.col)
    cfg = get_config()
    if changes and cfg["colorful_tags_sync"]:
        colorsync.apply(changes, cfg["queued_color"], cfg["completed_color"])
    notify()


def notify() -> None:
    for fn in list(_listeners):
        try:
            fn()
        except RuntimeError:
            # The listener's Qt object has been deleted.
            unsubscribe(fn)
    refresh_main_screen()


def refresh_main_screen() -> None:
    if mw.state == "deckBrowser":
        mw.deckBrowser.refresh()


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def say(message: str, parent=None) -> None:
    """Show a short confirmation. Windows that can display their own toasts
    (the web UI) expose `show_toast`; anything else gets Anki's tooltip."""
    show = getattr(parent, "show_toast", None)
    if callable(show):
        show(message)
    else:
        tooltip(message, parent=parent or mw)


# --- status changes ----------------------------------------------------------


def queue(tags: list[str]) -> None:
    state = load_state()
    changes: dict = {}
    for tag in tags:
        changes.update(state.queue(tag))
    commit(state, changes)


def unqueue(tags: list[str]) -> None:
    state = load_state()
    changes: dict = {}
    for tag in tags:
        changes.update(state.unqueue(tag))
    commit(state, changes)


def clear(tags: list[str]) -> None:
    state = load_state()
    changes: dict = {}
    for tag in tags:
        changes.update(state.clear(tag))
    commit(state, changes)


def complete(tags: list[str], parent=None) -> None:
    """Mark tags completed and (by default) unsuspend their cards."""
    if not tags:
        return
    parent = parent or mw
    cfg = get_config()
    cids = suspended_ids(mw.col, tags) if cfg["unsuspend_on_complete"] else []
    state = load_state()
    commit(state, state.complete(tags))
    done = f"Marked {_plural(len(tags), 'topic')} completed"
    if not cids:
        say(done, parent)
        return

    def on_success(_changes) -> None:
        say(f"{done} · unsuspended {_plural(len(cids), 'card')}", parent)

    unsuspend_cards(parent=parent, card_ids=cids).success(on_success).run_in_background()


def unsuspend(tags: list[str], parent=None) -> None:
    parent = parent or mw
    cids = suspended_ids(mw.col, tags)
    if not cids:
        say("No suspended cards in these topics.", parent)
        return

    def on_success(_changes) -> None:
        say(f"Unsuspended {_plural(len(cids), 'card')}", parent)

    unsuspend_cards(parent=parent, card_ids=cids).success(on_success).run_in_background()


def browse(tags: list[str]) -> None:
    if tags:
        aqt.dialogs.open("Browser", mw, search=(tags_search(mw.col, tags),))


# --- cached index ------------------------------------------------------------

_index: TagIndex | None = None
_index_dirty = True
_building = False
_waiters: list[Callable[[TagIndex], None]] = []


def mark_index_dirty() -> None:
    global _index_dirty
    _index_dirty = True


def cached_index() -> TagIndex | None:
    return _index


def request_index(callback: Callable[[TagIndex], None]) -> None:
    """Call `callback(index)` with an up-to-date index, rebuilding it in the
    background first if cards or tags have changed."""
    global _building
    mode = get_config()["count_mode"]
    if _index is not None and not _index_dirty and _index.mode == mode:
        callback(_index)
        return
    _waiters.append(callback)
    if _building:
        return
    _building = True
    _set_clean()

    def on_done(index: TagIndex) -> None:
        global _index, _building
        _index, _building = index, False
        waiters = list(_waiters)
        _waiters.clear()
        if _index_dirty:
            # Something changed while we were counting: count again.
            for fn in waiters:
                request_index(fn)
            return
        for fn in waiters:
            fn(index)

    def on_fail(exc: Exception) -> None:
        global _building
        _building = False
        _waiters.clear()
        raise exc

    QueryOp(parent=mw, op=lambda col: build_index(col, mode), success=on_done).failure(
        on_fail
    ).run_in_background()


def _set_clean() -> None:
    global _index_dirty
    _index_dirty = False


def reset() -> None:
    """Forget everything tied to the current collection (profile switch)."""
    global _index, _index_dirty, _building
    _index, _index_dirty, _building = None, True, False
    _waiters.clear()


def on_operation(changes, handler) -> None:
    if getattr(changes, "card", False) or getattr(changes, "tag", False) or getattr(
        changes, "note_text", False
    ):
        mark_index_dirty()
