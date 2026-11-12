# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Show a topic's cards in Skim, a separate add-on (a fast card browser with
vim keys), when it's installed.

Skim publishes its API as `aqt.mw.skim`. `p` on a topic opens Skim on its
cards; while Skim still shows Stepwise's cards, every topic you move to
shows its cards there too. The cards come from the index, so Skim never
runs Anki's tag search (which reads every note). Without Skim, nothing
here does anything.
"""

from __future__ import annotations

from aqt import mw

from .counts import TagIndex, short_name, tags_search
from .state import SEP

SOURCE = "Stepwise"


def _skim():
    return getattr(mw, "skim", None)


def available() -> bool:
    return _skim() is not None


def _topic(index: TagIndex | None, key: str) -> dict:
    """A topic's search, its cards (when the index has them) and its name."""
    key = key.lower()
    tag = index.name(key) if index is not None else key
    ids = None
    if index is not None and key in index.names:
        ids = [index.card_ids[p] for p in index.cards_under([key])]
    return {
        "search": tags_search(mw.col, [tag]),
        "card_ids": ids,
        "title": short_name(tag.rsplit(SEP, 1)[-1]),
    }


def preview(index: TagIndex | None, key: str) -> bool:
    """Open Skim on the topic's cards and give it the keys."""
    skim = _skim()
    if skim is None or not key:
        return False
    skim.open(source=SOURCE, **_topic(index, key))
    return True


def follow(index: TagIndex | None, key: str) -> None:
    """The selection moved: if Skim is showing Stepwise's cards, show this
    topic's instead. Costs nothing while it isn't."""
    skim = _skim()
    if skim is not None and key and skim.following(SOURCE):
        skim.follow(source=SOURCE, **_topic(index, key))
