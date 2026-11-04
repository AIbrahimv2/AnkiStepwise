# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Which tags are finished, and how far a "done" reaches up the tree.

A tag is *done* when any of these holds:
- you marked it completed;
- none of its cards are suspended any more (everything was unsuspended,
  whether through Tag Queue or not);
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
from .state import SEP


def done_tags(idx: TagIndex, completed: Iterable[str]) -> tuple[set[str], dict[str, int]]:
    """(done tag keys, number of done leaf topics under each tag).
    One pass over the tree, children before parents."""
    explicit = {t.lower() for t in completed}
    suspended = idx.suspended
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
        if key in covered or not suspended.get(key, 0):
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
