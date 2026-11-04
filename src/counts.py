# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Card counting and tag-tree indexing.

Counts are always *unique cards*: a card tagged with several queued topics
(common in AnKing, where one card carries B&B, Bootcamp and Pixorize tags)
is counted once. No Qt imports, so this runs against a collection outside
Anki for testing.
"""

from __future__ import annotations

import fnmatch
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .state import SEP

# How the "new cards" number is counted (config: count_mode).
#   new        cards you haven't started: still suspended, or never studied
#   suspended  only cards that are still suspended
#   all        every card under the tag
COUNT_MODES = ("new", "suspended", "all")

_FRESH_SEARCH = {
    "new": "(is:suspended OR is:new)",
    "suspended": "is:suspended",
    "all": "",
}


def fresh_search(mode: str) -> str:
    return _FRESH_SEARCH.get(mode, _FRESH_SEARCH["new"])


def _is_fresh(mode: str, queue: int, ctype: int) -> bool:
    if mode == "all":
        return True
    if mode == "suspended":
        return queue == -1
    return queue == -1 or ctype == 0


# --- searches ----------------------------------------------------------------


def tags_search(col, tags: list[str], extra: str = "") -> str:
    """A search string matching cards under any of `tags`, plus `extra`.
    SearchNode(tag=...) escapes `_`/`*`, which AnKing tags are full of."""
    from anki.collection import SearchNode

    nodes = [SearchNode(tag=t) for t in tags]
    if not nodes:
        return ""
    group = nodes[0] if len(nodes) == 1 else col.group_searches(*nodes, joiner="OR")
    if extra:
        return col.build_search_string(group, SearchNode(parsable_text=extra))
    return col.build_search_string(group)


def card_ids(col, tags: list[str], extra: str = "") -> list[int]:
    if not tags:
        return []
    return list(col.find_cards(tags_search(col, tags, extra)))


def fresh_ids(col, tags: list[str], mode: str) -> list[int]:
    return card_ids(col, tags, fresh_search(mode))


def suspended_ids(col, tags: list[str]) -> list[int]:
    return card_ids(col, tags, "is:suspended")


# --- labels ------------------------------------------------------------------


def prettify(component: str) -> str:
    """`05_Ethanol_Metabolism:_Pathway` -> `05 Ethanol Metabolism: Pathway`,
    `#B&B` -> `B&B`."""
    s = component.lstrip("#").replace("_", " ").strip()
    return s or component


def root_label(root: str) -> str:
    """Short name for a resource root: `#AK_Step1_v12` -> `Step 1`."""
    s = root.lstrip("#")
    s = re.sub(r"^AK_", "", s, flags=re.I)
    s = re.sub(r"_v\d+$", "", s, flags=re.I)
    s = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s)
    return prettify(s)


_NUM = re.compile(r"(\d+)")


def natural_key(s: str):
    return [int(p) if p.isdigit() else p for p in _NUM.split(s.lower())]


# --- index -------------------------------------------------------------------


@dataclass
class TagIndex:
    """The whole tag tree with per-tag unique card counts.

    Keys are lower-cased full tag names; `names` maps them back to the
    collection's spelling. Parents that exist only implicitly (because a
    child tag exists) are included.
    """

    mode: str
    names: dict[str, str] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)
    total: Counter = field(default_factory=Counter)
    fresh: Counter = field(default_factory=Counter)
    leaves: dict[str, int] = field(default_factory=dict)

    def name(self, key: str) -> str:
        return self.names.get(key, key)

    def kids(self, key: str) -> list[str]:
        return self.children.get(key, [])

    def last(self, key: str) -> str:
        return self.name(key).rsplit(SEP, 1)[-1]


def build_index(col, mode: str) -> TagIndex:
    """Build the tag tree and count cards under every tag in one pass over
    the cards table (about a second for a full AnKing collection — run it in
    the background)."""
    idx = TagIndex(mode=mode)

    for tag in col.tags.all():
        parts = tag.split(SEP)
        for i in range(1, len(parts) + 1):
            full = SEP.join(parts[:i])
            idx.names.setdefault(full.lower(), full)

    children: dict[str, list[str]] = defaultdict(list)
    for low in idx.names:
        cut = low.rfind(SEP)
        children[low[:cut] if cut >= 0 else ""].append(low)
    for kids in children.values():
        kids.sort(key=lambda k: natural_key(idx.names[k].rsplit(SEP, 1)[-1]))
    idx.children = dict(children)

    # Leaf-topic counts, deepest tags first so children are done before parents.
    for low in sorted(idx.names, key=lambda k: k.count(SEP), reverse=True):
        kids = idx.children.get(low)
        idx.leaves[low] = sum(idx.leaves[c] for c in kids) if kids else 1

    # Unique card counts: each card adds 1 to every tag it sits under, once.
    total, fresh = idx.total, idx.fresh
    last_tags, last_prefixes = None, ()
    rows = col.db.all(
        "select n.tags, c.queue, c.type from cards c join notes n on n.id = c.nid order by c.nid"
    )
    for tags, queue, ctype in rows:
        if tags != last_tags:
            prefixes = set()
            for tag in tags.split():
                parts = tag.lower().split(SEP)
                for i in range(1, len(parts) + 1):
                    prefixes.add(SEP.join(parts[:i]))
            last_tags, last_prefixes = tags, prefixes
        is_fresh = _is_fresh(mode, queue, ctype)
        for p in last_prefixes:
            total[p] += 1
            if is_fresh:
                fresh[p] += 1
    return idx


def root_matcher(patterns: list[str]):
    """Predicate for "is this top-level tag a resource root?" from the
    configured patterns (e.g. `#AK_Step*`). Case-insensitive."""
    pats = [p.lower() for p in patterns if isinstance(p, str) and p.strip()]
    return lambda tag: any(fnmatch.fnmatchcase(tag.lower(), p) for p in pats)


def resource_roots(idx: TagIndex, patterns: list[str]) -> list[str]:
    """Top-level tags (lower-case keys) whose children are shown as resources."""
    is_root = root_matcher(patterns)
    return [k for k in idx.kids("") if is_root(k)]


def display_parts(tag: str, is_root) -> tuple[str | None, list[str]]:
    """Split a tag for display: (resource root or None, remaining components).
    `#AK_Step1_v12::#B&B::16_Neuro` -> ('#AK_Step1_v12', ['#B&B', '16_Neuro'])."""
    parts = tag.split(SEP)
    if len(parts) > 1 and is_root(parts[0]):
        return parts[0], parts[1:]
    return None, parts


def short_path(tag: str, is_root, with_root: bool) -> str:
    """Breadcrumb for a tag's *parents*, e.g. `Step 1 · B&B › 16 Neuro`."""
    root, parts = display_parts(tag, is_root)
    crumbs = " › ".join(prettify(p) for p in parts[:-1])
    if root and with_root:
        return f"{root_label(root)} · {crumbs}" if crumbs else root_label(root)
    return crumbs
