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


def _cards(index: TagIndex | None, keys: list[str], title: str | None) -> dict:
    """Topics' search, their cards (when the index has them) and a name."""
    keys = [k.lower() for k in keys]
    tags = [index.name(k) if index is not None else k for k in keys]
    ids = None
    if index is not None and all(k in index.names for k in keys):
        ids = [index.card_ids[p] for p in index.cards_under(keys)]
    if title is None:
        title = short_name(tags[0].rsplit(SEP, 1)[-1]) if len(tags) == 1 else f"{len(tags)} topics"
    return {"search": tags_search(mw.col, tags), "card_ids": ids, "title": title}


def preview(index: TagIndex | None, keys: list[str], title: str | None = None) -> bool:
    """Open Skim on these topics' cards and give it the keys."""
    skim = _skim()
    keys = [k for k in keys if k]
    if skim is None or not keys:
        return False
    skim.open(source=SOURCE, **_cards(index, keys, title))
    return True


def follow(index: TagIndex | None, keys: list[str], title: str | None = None) -> None:
    """The selection moved: if Skim is showing Stepwise's cards, show these
    topics' instead. Costs nothing while it isn't."""
    skim = _skim()
    keys = [k for k in keys if k]
    if skim is not None and keys and skim.following(SOURCE):
        skim.follow(source=SOURCE, **_cards(index, keys, title))
