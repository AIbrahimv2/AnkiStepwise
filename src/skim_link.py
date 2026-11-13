# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Show a topic's cards in Skim, a separate add-on (a fast card browser with
vim keys), when it's installed.

Skim publishes its API as `aqt.mw.skim`. `b` (or `p`) on a topic opens Skim
on its cards; while Skim still shows Stepwise's cards, every topic you move
to shows its cards there too. The cards come from the index, so Skim never
runs Anki's tag search (which reads every note).

Skim also reads each card's tags against the topic: which resources it's in
(your pinned ones first), which other systems it comes up in, and whether
to unsuspend it now or wait. For that it asks Stepwise, through `Plan`, for
the pinned resources, the resource roots and each tag's status, and hears
when they change. Without Skim, nothing here does anything.
"""

from __future__ import annotations

from aqt import mw

from . import actions
from .counts import TagIndex, short_name, tags_search
from .state import SEP


SOURCE = "Stepwise"


def _skim():
    return getattr(mw, "skim", None)


def available() -> bool:
    return _skim() is not None


class Plan:
    """What Skim asks Stepwise about (see Skim's api.set_context): a
    snapshot, made when Skim starts reading a new set of cards."""

    def __init__(self) -> None:
        from .viewmodel import View

        self.view = View(actions.cached_index())

    def pinned(self) -> list[str]:
        """Pinned resources in the order the tree lists them."""
        view, idx = self.view, self.view.index
        if idx is None:
            return []
        resources, others = view.browse_entries()
        order = [key for key, _root in resources] + others
        pins = set(view.pinned_resources())
        return [idx.name(k) for k in order if k in pins]

    def roots(self) -> list[str]:
        idx = self.view.index
        return [idx.name(r) for r in self.view.roots] if idx is not None else []

    def status(self, tag: str) -> str | None:
        return self.view.status_of(tag.lower())[0]


def _connect(skim) -> None:
    """Tell Skim where to ask (Skim 2 and later)."""
    if hasattr(skim, "set_context"):
        skim.set_context(Plan)


def plan_changed() -> None:
    """Something was queued, saved for later or done: Skim reads statuses
    again (only while it's open)."""
    skim = _skim()
    if skim is not None and hasattr(skim, "context_changed") and skim.is_open():
        skim.context_changed()


actions.subscribe(plan_changed)


def _cards(index: TagIndex | None, keys: list[str], title: str | None) -> dict:
    """Topics' search, their cards (when the index has them), a name, and
    the topics themselves, for Skim to read the cards' tags against."""
    keys = [k.lower() for k in keys]
    tags = [index.name(k) if index is not None else k for k in keys]
    ids = None
    if index is not None and all(k in index.names for k in keys):
        ids = [index.card_ids[p] for p in index.cards_under(keys)]
    if title is None:
        title = short_name(tags[0].rsplit(SEP, 1)[-1]) if len(tags) == 1 else f"{len(tags)} topics"
    return {"search": tags_search(mw.col, tags), "card_ids": ids, "title": title, "topic": tags}


def _args(skim, cards: dict) -> dict:
    """Skim 1 doesn't take a topic."""
    if getattr(skim, "VERSION", 1) < 2:
        cards = {k: v for k, v in cards.items() if k != "topic"}
    return cards


def preview(index: TagIndex | None, keys: list[str], title: str | None = None) -> bool:
    """Open Skim on these topics' cards and give it the keys."""
    skim = _skim()
    keys = [k for k in keys if k]
    if skim is None or not keys:
        return False
    _connect(skim)
    skim.open(source=SOURCE, **_args(skim, _cards(index, keys, title)))
    return True


def follow(index: TagIndex | None, keys: list[str], title: str | None = None) -> None:
    """The selection moved: if Skim is showing Stepwise's cards, show these
    topics' instead. Costs nothing while it isn't."""
    skim = _skim()
    keys = [k for k in keys if k]
    if skim is not None and keys and skim.following(SOURCE):
        skim.follow(source=SOURCE, **_args(skim, _cards(index, keys, title)))
