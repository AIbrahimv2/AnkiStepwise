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

from . import colorsync, rollup
from .config import get_config
from .counts import (
    TagIndex,
    build_index,
    fresh_ids,
    plan_fill,
    resource_roots,
    short_name,
    suspended_ids,
    tags_search,
)
from .state import COMPLETED, QUEUED, QueueState

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


def commit(state: QueueState, changes: dict, tidy: bool = True) -> None:
    state.save(mw.col)
    if tidy:
        changes = dict(changes)
        changes.update(_consolidate(state)[0])
    cfg = get_config()
    if changes and cfg["colorful_tags_sync"]:
        colorsync.apply(changes, cfg["queued_color"], cfg["completed_color"],
                        later_color=cfg["later_color"])
    notify()


# --- automatic "done" ---------------------------------------------------------

_announcer: Callable[[str], None] | None = None


def set_announcer(fn: Callable[[str], None] | None) -> None:
    """Where automatic changes are reported (the Tag Queue window's toasts)."""
    global _announcer
    _announcer = fn


def _announce(message: str) -> None:
    if _announcer is not None:
        _announcer(message)


_done_cache: tuple | None = None


def done_info() -> tuple[set[str], dict[str, int]]:
    """Done tags and done-leaf counts for the current index and completions
    (see rollup.py), cached until either changes."""
    global _done_cache
    idx = _index
    if idx is None:
        return set(), {}
    completed = frozenset(t.lower() for t in load_state().completed())
    if _done_cache is None or _done_cache[0] is not idx or _done_cache[1] != completed:
        _done_cache = (idx, completed, rollup.done_tags(idx, completed))
    return _done_cache[2]


def _consolidate(state: QueueState) -> tuple[dict, bool]:
    """Tidy statuses against the cards' actual state, saving if anything
    changed. Returns (status changes, whether anything changed at all).

    - A topic in the plan (queued, watched, or Later) whose every card has
      been studied (none suspended, none still new) is done and leaves the
      queue. Cards that are only unsuspended keep it in the plan: they're
      still new cards due, and checking a topic off means you watched it.
    - Completions roll up to the highest parent that's fully done.
    """
    idx = _index
    if idx is None:
        return {}, False
    changes: dict = {}
    session_before = list(state.session)

    def studied(tag: str) -> bool:
        k = tag.lower()
        return bool(idx.total.get(k, 0)) and not idx.suspended.get(k, 0) and not idx.waiting.get(k, 0)

    finished = [t for t in state.queued() + state.watched() + state.later() if studied(t)]
    not_done = [t for t in finished if state.effective(t)[0] != COMPLETED]
    if not_done:
        changes.update(state.complete(not_done))
    for t in finished:
        state.leave_session(t)
    done, _leaves = rollup.done_tags(idx, state.completed())
    roots = set(resource_roots(idx, get_config()["resource_roots"]))
    tops = rollup.roll_up(state.completed(), done, roots)
    # Parents that weren't complete yet (vs. just tidying entries under one).
    newly = [t for t in tops if state.status(idx.name(t)) != COMPLETED]
    for top, covered in tops.items():
        at = max(state.since(t) for t in covered) if covered else 0
        changes.update(state.complete_rollup(idx.name(top), at))
    if not changes and state.session == session_before:
        return {}, False
    state.save(mw.col)
    if len(finished) == 1:
        _announce(f"Every card in {short_name(finished[0].rsplit('::', 1)[-1])} is studied — "
                  "moved it to Done")
    elif finished:
        _announce(f"{_plural(len(finished), 'topic')} fully studied — moved to Done")
    if 0 < len(newly) <= 2:
        for top in newly:
            _announce(f"Everything in {short_name(idx.last(top))} is done — marked it complete")
    elif newly:
        _announce(f"Marked {_plural(len(newly), 'parent topic')} complete — everything under "
                  "them is done")
    return changes, True


def consolidate() -> None:
    """Run the automatic tidy-up now (e.g. after card counts were rebuilt)."""
    state = load_state()
    changes, touched = _consolidate(state)
    if touched:
        commit(state, changes, tidy=False)


def notify() -> None:
    for fn in list(_listeners):
        try:
            fn()
        except RuntimeError:
            # The listener's Qt object has been deleted.
            unsubscribe(fn)
    refresh_main_screen()


def refresh_main_screen(full: bool = False) -> None:
    """Update the deck screen's queue meter. Re-rendering the whole deck
    list is slow (every add-on redraws its panel), so normally the meter is
    patched in place; `full` is only for adding/removing the widget."""
    if mw.state != "deckBrowser":
        return
    if full:
        mw.deckBrowser.refresh()
        return
    from .widget import update_in_place

    update_in_place()


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


def save_later(tags: list[str]) -> None:
    """Park tags for a later session (taking them out of the queue)."""
    state = load_state()
    changes: dict = {}
    for tag in tags:
        changes.update(state.save_later(tag))
    commit(state, changes)


def unlater(tags: list[str]) -> None:
    state = load_state()
    changes: dict = {}
    for tag in tags:
        changes.update(state.unlater(tag))
    commit(state, changes)


def fill_from_later() -> tuple[list[str], int, list[str]]:
    """Queue Later topics, oldest first, as long as the session stays under
    the card limit. Returns (queued tags, cards added, tags that didn't fit)."""
    cfg = get_config()
    state = load_state()
    picked, added, skipped = plan_fill(
        fresh_cards, state.later(), state.session_tags(), cfg["card_limit"])
    if picked:
        queue(picked)
    return picked, added, skipped


def unwatch(tags: list[str]) -> None:
    """Undo checks: back to the queue (cards stay unsuspended)."""
    state = load_state()
    changes: dict = {}
    for tag in tags:
        changes.update(state.unwatch(tag))
    commit(state, changes)


def finish_session() -> list[str]:
    """Clear watched topics from the queue now (they stay done). They also
    leave on their own once every card in them is studied."""
    state = load_state()
    finished = state.finish_session()
    commit(state, {})
    return finished


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
    cids = suspended_cards(tags) if cfg["unsuspend_on_complete"] else []
    state = load_state()
    in_queue = all(state.status(t) == QUEUED for t in tags)
    commit(state, state.complete(tags))
    done = (f"Checked off {_plural(len(tags), 'topic')}" if in_queue
            else f"Marked {_plural(len(tags), 'topic')} done")
    if not cids:
        say(done, parent)
        return

    def on_success(_changes) -> None:
        say(f"{done} · unsuspended {_plural(len(cids), 'card')}", parent)

    unsuspend_cards(parent=parent, card_ids=cids).success(on_success).run_in_background()


def unsuspend(tags: list[str], parent=None) -> None:
    parent = parent or mw
    cids = suspended_cards(tags)
    if not cids:
        say("No suspended cards in these topics.", parent)
        return

    def on_success(_changes) -> None:
        say(f"Unsuspended {_plural(len(cids), 'card')}", parent)

    unsuspend_cards(parent=parent, card_ids=cids).success(on_success).run_in_background()


def browse(tags: list[str]) -> None:
    if tags:
        aqt.dialogs.open("Browser", mw, search=(tags_search(mw.col, tags),))


# --- card counts -------------------------------------------------------------
# Counting through Anki's search is slow (a regex over every note per tag), so
# these use the in-memory index and only fall back to searching before the
# first index exists.


def usable_index() -> TagIndex | None:
    """The cached index if it counts the configured way. It may be a few
    seconds stale after reviews; a rebuild is then already on its way."""
    mode = get_config()["count_mode"]
    return _index if _index is not None and _index.mode == mode else None


def fresh_cards(tags: list[str]) -> set[int]:
    """Ids of the unique cards under `tags` that count toward the limit."""
    if not tags:
        return set()
    idx = usable_index()
    if idx is not None:
        return set(idx.ids(idx.fresh_under(tags)))
    return set(fresh_ids(mw.col, tags, get_config()["count_mode"]))


def suspended_cards(tags: list[str]) -> list[int]:
    """Ids of the currently suspended cards under `tags`. Which cards sit
    under a tag comes from the index (unless tags were edited since it was
    built); whether they're suspended is checked live."""
    if not tags:
        return []
    idx = _index
    if idx is None or _membership_dirty:
        return suspended_ids(mw.col, tags)
    cids = idx.ids(idx.cards_under(tags))
    if not cids:
        return []
    return mw.col.db.list(
        f"select id from cards where queue = -1 and id in ({','.join(map(str, cids))})")


# --- cached index ------------------------------------------------------------

_index: TagIndex | None = None
_index_dirty = True
_membership_dirty = True  # tags edited since the index was built
_building = False
_waiters: list[Callable[[TagIndex], None]] = []
_index_listeners: list[Callable[[TagIndex], None]] = []


def mark_index_dirty(membership: bool = False) -> None:
    global _index_dirty, _membership_dirty
    _index_dirty = True
    if membership:
        _membership_dirty = True


def cached_index() -> TagIndex | None:
    return _index


def on_index_built(fn: Callable[[TagIndex], None]) -> None:
    if fn not in _index_listeners:
        _index_listeners.append(fn)


def off_index_built(fn: Callable[[TagIndex], None]) -> None:
    if fn in _index_listeners:
        _index_listeners.remove(fn)


def request_index(callback: Callable[[TagIndex], None] | None = None) -> None:
    """Make sure an up-to-date index exists, rebuilding it in the background
    if cards or tags changed. `callback(index)` runs once it's current;
    listeners from on_index_built() hear about every rebuild."""
    global _building, _index_dirty
    mode = get_config()["count_mode"]
    if _index is not None and not _index_dirty and _index.mode == mode:
        if callback:
            callback(_index)
        return
    if callback:
        _waiters.append(callback)
    if _building:
        return
    _building = True
    _index_dirty = False
    membership_was_dirty = _membership_dirty

    def on_done(index: TagIndex) -> None:
        global _index, _building, _membership_dirty
        _index, _building = index, False
        if membership_was_dirty and not _index_dirty:
            _membership_dirty = False
        consolidate()  # card states changed: re-check what's done
        for fn in list(_index_listeners):
            try:
                fn(index)
            except RuntimeError:  # listener's Qt object is gone
                off_index_built(fn)
        if _index_dirty:
            # Something changed while we were counting: count again.
            request_index()
            return
        waiters = list(_waiters)
        _waiters.clear()
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


def reset() -> None:
    """Forget everything tied to the current collection (profile switch)."""
    global _index, _index_dirty, _membership_dirty, _building
    _index, _index_dirty, _membership_dirty, _building = None, True, True, False
    _waiters.clear()


def on_operation(changes, handler) -> None:
    tags = getattr(changes, "tag", False) or getattr(changes, "note_text", False)
    if tags or getattr(changes, "card", False):
        mark_index_dirty(membership=bool(tags))
