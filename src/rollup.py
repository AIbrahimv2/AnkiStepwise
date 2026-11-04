# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Which tags are finished, and how far a "done" reaches up the tree.

A tag is *done* when any of these holds:
- you marked it completed;
- every one of its cards has been studied: none still suspended and none
  still new (an unsuspended card you haven't studied yet, or a buried one,
  keeps it open);
- every tag nested under it is done and no card carries the tag itself
  while still suspended.

From that, a completed topic "rolls up": if its parent is done too, the
parent is what gets marked complete (and so on up to the resource), so
the Done list shows "16 Neuro" rather than each of its videos.

No Qt imports, so this runs against a collection outside Anki for tests.
"""

from __future__ import annotations

from collections.abc import Iterable

from .counts import TagIndex
from .state import COMPLETED, SEP, QueueState


def done_tags(idx: TagIndex, completed: Iterable[str]) -> tuple[set[str], dict[str, int]]:
    """(done tag keys, number of done leaf topics under each tag).
    One pass over the tree, children before parents."""
    explicit = {t.lower() for t in completed}
    suspended = idx.suspended
    waiting = idx.waiting
    children = idx.children
    leaves = idx.leaves
    tag_cards = idx.tag_cards
    smask = idx.suspended_mask
    # Everything under a completed tag is covered by it (parents first).
    covered: set[str] = set()
    if explicit:
        for key in reversed(idx.post_order):
            cut = key.rfind(SEP)
            if key in explicit or (cut > 0 and key[:cut] in covered):
                covered.add(key)
    done: set[str] = set()
    done_leaves: dict[str, int] = {}
    for key in idx.post_order:
        kids = children.get(key)
        if key in covered or not (suspended.get(key, 0) or waiting.get(key, 0)):
            done.add(key)
            done_leaves[key] = leaves.get(key, 1)
        elif kids and all(c in done for c in kids) and not any(
                smask[i] for i in tag_cards.get(key, ())):
            done.add(key)
            done_leaves[key] = leaves.get(key, 1)
        else:
            done_leaves[key] = sum(done_leaves[c] for c in kids) if kids else 0
    return done, done_leaves


def roll_up(completed: Iterable[str], done: set[str], stop: set[str]) -> dict[str, list[str]]:
    """{highest done ancestor: completed tags it covers} for completed tags
    whose parent is also done. Climbing stops below `stop` (the resource
    roots, e.g. #AK_Step1_v12: a whole step is never marked complete).
    Tops nested under another top are merged into it."""
    tops: dict[str, list[str]] = {}
    for tag in completed:
        top = tag.lower()
        while SEP in top:
            parent = top.rsplit(SEP, 1)[0]
            if parent in stop or parent not in done:
                break
            top = parent
        if top != tag.lower():
            tops.setdefault(top, []).append(tag)
    # A top nested under another top is covered by it.
    for top in sorted(tops, key=lambda k: k.count(SEP)):
        if top not in tops:
            continue
        for other in [o for o in tops if o != top and o.startswith(top + SEP)]:
            tops[top] += tops.pop(other)
    return tops


def studied(idx: TagIndex, key: str) -> bool:
    """Every card under the tag has been studied: none still suspended, none
    still new (unsuspended or buried)."""
    return bool(idx.total.get(key, 0)) and not idx.suspended.get(key, 0) and not idx.waiting.get(key, 0)


def sweep(idx: TagIndex, state: QueueState, roots: set[str]) -> list[str]:
    """Tags to mark completed because every card under them is studied,
    even though they were never queued or coloured.

    Only in resources you use (ones holding any queued, Later or completed
    entry), and no deeper than the deepest entry you have in that resource:
    AnKing cards carry many tags, so studying one resource finishes stray
    question IDs and sub-sub-headings in others, and those would bury the
    Done list. Within that, only the highest finished tag in each branch.
    Returns lower-case keys, parents before children never both."""
    limits: dict[str, int] = {}
    for tag in state.tags:
        parts = tag.lower().split(SEP)
        if len(parts) >= 2 and parts[0] in roots:
            res = SEP.join(parts[:2])
            limits[res] = max(limits.get(res, 0), len(parts))
    tops: list[str] = []
    for res, limit in limits.items():
        if res not in idx.names:
            continue
        stack = [res]
        while stack:
            key = stack.pop()
            if state.status(idx.name(key)) == COMPLETED:
                continue  # already done, and it covers everything below
            depth = key.count(SEP) + 1
            if studied(idx, key):
                tops.append(key)
                continue
            if depth < limit:
                stack.extend(idx.children.get(key, ()))
    return tops
