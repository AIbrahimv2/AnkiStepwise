# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Card counting and tag-tree indexing.

Counts are always unique: a card tagged with several queued topics (common
in AnKing, where one card carries B&B, Bootcamp and Pixorize tags) is
counted once, and in "new" mode so is a note whose deck buries new siblings
(see shown_today). No Qt imports, so this runs against a collection outside
Anki for testing.

Performance note: Anki's `tag:` search runs a regex over every note per
tag (~130 ms per tag on a full AnKing collection), so counting a 20-tag
queue that way takes seconds. Interactive counts therefore come from the
in-memory `TagIndex` (card lists per tag, built once in the background);
the search helpers below are only fallbacks and for opening the Browser.
"""

from __future__ import annotations

import fnmatch
import re
from array import array
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from itertools import groupby

from .state import SEP

# What counts toward the session limit (config: count_mode).
#   new        the new cards Anki will show you today, still suspended or not.
#              Default: the day's plan, which doesn't shrink when you check a
#              topic off and unsuspend its cards, only as you study. It
#              follows the decks' "Bury new siblings" option (see shown_today).
#   suspended  only cards that are still suspended
#   all        every card under the tag
COUNT_MODES = ("new", "suspended", "all")

BURIED = (-2, -3)  # buried by hand, or by sibling burying


# --- what Anki shows today -----------------------------------------------------
# With "Bury new siblings" on (deck options), Anki shows at most one new card
# of a note a day: answering one buries the rest until tomorrow, and when the
# day's queue is built a new card is left out if a sibling is already in it
# (a review or learning card due today, or another new card). Counting every
# new card would plan more than Anki will actually show.


def bury_new_decks(col) -> dict[int, bool]:
    """Deck id -> whether its options bury new siblings."""
    out = {}
    for d in col.decks.all_names_and_ids():
        try:
            out[d.id] = bool(col.decks.config_dict_for_deck_id(d.id)["new"].get("bury"))
        except Exception:  # a filtered deck's own entry; its cards use their home deck
            out[d.id] = False
    return out


def due_today(queue: int, due: int, today: int, cutoff: int) -> bool:
    """A studied card Anki will show today: a review or day-learning card due
    by today (`due` in days), or a learning card (`due` a timestamp)."""
    return (queue in (2, 3) and due <= today) or (queue == 1 and due < cutoff)


def shown_today(news: list[tuple[int, int]], sibling_due: bool, nid: int,
                bury: dict[int, bool]) -> list[tuple[int, int]]:
    """Of one note's new, unburied cards `news` [(card id, deck id)], the ones
    Anki will show today, each paired with what it counts as: the card id,
    or -nid for a card whose deck buries new siblings (the note then counts
    once). In such a deck none show while a sibling is due today."""
    out = []
    for cid, deck in news:
        if bury.get(deck):
            if not sibling_due:
                out.append((cid, -nid))
        else:
            out.append((cid, cid))
    return out


def today_units(col, cids: Iterable[int], mode: str) -> set[int]:
    """What the cards `cids` (those counting in `mode`) add up to toward the
    limit, without the index: in "new" mode the units of shown_today(), else
    the cards themselves."""
    cids = list(cids)
    if mode != "new" or not cids:
        return set(cids)
    from anki.utils import ids2str

    wanted = set(cids)
    bury = bury_new_decks(col)
    today, cutoff = col.sched.today, col.sched.day_cutoff  # unburies on a new day: before reading
    rows = col.db.all(
        "select id, nid, queue, type, did, odid, due from cards where nid in"
        f" (select nid from cards where id in {ids2str(cids)}) order by nid"
    )
    out: set[int] = set()
    for nid, cards in groupby(rows, key=lambda r: r[1]):
        news, sibling_due = [], False
        for cid, _nid, queue, ctype, did, odid, due in cards:
            if ctype == 0:
                if cid in wanted and queue not in BURIED:
                    news.append((cid, odid or did))
            elif due_today(queue, due, today, cutoff):
                sibling_due = True
        out.update(u for _cid, u in shown_today(news, sibling_due, nid, bury))
    return out

_FRESH_SEARCH = {
    "new": "is:new",
    "suspended": "is:suspended",
    "all": "",
}


def fresh_search(mode: str) -> str:
    return _FRESH_SEARCH.get(mode, _FRESH_SEARCH["new"])


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


def plan_fill(fresh_of: Callable[[list[str]], set], later: list[str], queued: list[str],
              limit: int):
    """Which Later topics fit in the queue: walk them oldest first and take
    each one whose *new* unique cards still fit under `limit` (a big topic
    that doesn't fit is skipped, so smaller ones behind it can still go in).
    `fresh_of(tags)` returns the set of fresh cards under those tags.
    Returns (picked tags, cards added, skipped tags)."""
    have = set(fresh_of(queued)) if queued else set()
    start = len(have)
    picked: list[str] = []
    skipped: list[str] = []
    for tag in later:
        new = fresh_of([tag]) - have
        if len(have) + len(new) <= limit:
            picked.append(tag)
            have |= new
        else:
            skipped.append(tag)
    return picked, len(have) - start, skipped


# --- labels ------------------------------------------------------------------


def prettify(component: str) -> str:
    """`05_Ethanol_Metabolism:_Pathway` -> `05 Ethanol Metabolism: Pathway`,
    `#B&B` -> `B&B`."""
    s = component.lstrip("#").replace("_", " ").strip()
    return s or component


_ORDER_PREFIX = re.compile(r"^\d+\s+(?=\S)")


def short_name(component: str) -> str:
    """Name for compact places (side panel, breadcrumbs, toasts): prettified
    and without the course-order number, `03_Pharmacology` ->
    `Pharmacology`. A name that is only a number (a UWorld question ID) is
    kept. The main tree uses prettify() and keeps the numbers."""
    return _ORDER_PREFIX.sub("", prettify(component))


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
    """The whole tag tree with per-tag unique card counts, plus which cards
    sit under which tag so any set of tags can be counted in memory.

    Keys are lower-cased full tag names; `names` maps them back to the
    collection's spelling. Parents that exist only implicitly (because a
    child tag exists) are included. Cards are referred to by their position
    in `card_ids`.
    """

    mode: str
    names: dict[str, str] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)
    total: Counter = field(default_factory=Counter)
    # Per tag: what counts toward the limit in `mode` (in "new" mode, the new
    # cards Anki shows today: see shown_today), and the breakdown.
    fresh: Counter = field(default_factory=Counter)
    suspended: Counter = field(default_factory=Counter)
    # Unsuspended but never studied (new cards in Anki's queue, or buried).
    waiting: Counter = field(default_factory=Counter)
    # The buried part of `waiting` (sibling burying or buried by hand); these
    # come back by themselves, there's nothing to unsuspend.
    buried: Counter = field(default_factory=Counter)
    # Never studied, suspended or not (what "new" mode counts).
    new: Counter = field(default_factory=Counter)
    leaves: dict[str, int] = field(default_factory=dict)
    # tag actually on a note (lower-case) -> positions of that note's cards
    tag_cards: dict[str, list[int]] = field(default_factory=dict)
    card_ids: list[int] = field(default_factory=list)
    # Per card: whether it counts toward the limit, and as what (its card id,
    # or -note id when its note counts once).
    fresh_mask: bytearray = field(default_factory=bytearray)
    unit: array = field(default_factory=lambda: array("q"))
    suspended_mask: bytearray = field(default_factory=bytearray)
    # Every tag, deepest first: children always come before their parent.
    post_order: list[str] = field(default_factory=list)

    def name(self, key: str) -> str:
        return self.names.get(key, key)

    def kids(self, key: str) -> list[str]:
        return self.children.get(key, [])

    def last(self, key: str) -> str:
        return self.name(key).rsplit(SEP, 1)[-1]

    def subtree(self, key: str) -> Iterator[str]:
        """`key` and every tag nested under it."""
        stack = [key]
        children = self.children
        while stack:
            k = stack.pop()
            yield k
            kids = children.get(k)
            if kids:
                stack.extend(kids)

    def cards_under(self, tags: Iterable[str]) -> set[int]:
        """Positions of every card under any of `tags` (unique)."""
        out: set[int] = set()
        tag_cards = self.tag_cards
        for t in tags:
            for k in self.subtree(t.lower()):
                cards = tag_cards.get(k)
                if cards:
                    out.update(cards)
        return out

    def units_under(self, tags: Iterable[str]) -> set[int]:
        """What the cards under `tags` add up to toward the limit: its size
        is the count (a note whose siblings are buried counts once)."""
        mask, unit = self.fresh_mask, self.unit
        return {unit[i] for i in self.cards_under(tags) if mask[i]}

    def ids(self, positions: Iterable[int]) -> list[int]:
        card_ids = self.card_ids
        return [card_ids[i] for i in positions]


def build_index(col, mode: str) -> TagIndex:
    """Build the tag tree, count cards under every tag, and record which
    cards each tag holds, in one pass over the cards table (a few hundred
    ms for a full AnKing collection; still run it in the background)."""
    idx = TagIndex(mode=mode)
    names = idx.names
    tag_cards: dict[str, list[int]] = {}
    # raw tag string -> (its key and all parent keys, its card list). Built
    # once per distinct tag; the hot loop below then only does lookups.
    info: dict[str, tuple[tuple[str, ...], list[int]]] = {}

    def learn(tag: str) -> tuple[tuple[str, ...], list[int]]:
        low = tag.lower()
        parts, orig = low.split(SEP), tag.split(SEP)
        keys = []
        for i in range(1, len(parts) + 1):
            k = SEP.join(parts[:i])
            keys.append(k)
            if k not in names:
                names[k] = SEP.join(orig[:i])
        cards = tag_cards.setdefault(low, [])
        found = info[tag] = (tuple(keys), cards)
        return found

    for tag in col.tags.all():
        learn(tag)

    count_all, only_suspended = mode == "all", mode == "suspended"
    count_new = not count_all and not only_suspended
    bury = bury_new_decks(col) if count_new else {}
    # Before reading the cards: on a new day this is what unburies
    # yesterday's buried cards.
    today, cutoff = (col.sched.today, col.sched.day_cutoff) if count_new else (0, 0)
    rows = col.db.all(
        "select c.id, c.nid, n.tags, c.queue, c.type, c.did, c.odid, c.due"
        " from cards c join notes n on n.id = c.nid order by c.nid"
    )
    total, suspended, waiting, buried, new = idx.total, idx.suspended, idx.waiting, idx.buried, idx.new
    card_ids = idx.card_ids
    mask = idx.fresh_mask = bytearray(len(rows))
    smask = idx.suspended_mask = bytearray(len(rows))
    unit = idx.unit = array("q", (r[0] for r in rows))
    plan: Counter = Counter()  # "new" mode: what Anki shows today, per tag
    pos: dict[int, int] = {}  # card id -> position, for the note being read

    def settle(nid: int, news: list, sibling_due: bool, under: set[str]) -> None:
        """Count a finished note's new cards that Anki shows today."""
        units = set()
        for cid, u in shown_today(news, sibling_due, nid, bury):
            i = pos[cid]
            mask[i] = 1
            unit[i] = u
            units.add(u)
        for _ in units:
            plan.update(under)

    get = info.get
    last_tags = None
    under: set[str] = set()
    lists: list[list[int]] = []
    last_nid = None
    news: list[tuple[int, int]] = []
    sibling_due = False
    for i, (cid, nid, tags, queue, ctype, did, odid, due) in enumerate(rows):
        if nid != last_nid:  # cards of one note are adjacent
            if news:
                settle(last_nid, news, sibling_due, under)
            last_nid, news, sibling_due = nid, [], False
            pos.clear()
        if tags != last_tags:
            last_tags = tags
            found = [get(t) or learn(t) for t in tags.split()]
            under = set().union(*[f[0] for f in found])
            lists = [f[1] for f in found]
        card_ids.append(cid)
        for cards in lists:
            cards.append(i)
        total.update(under)  # Counter.update counts in C
        if ctype == 0:
            new.update(under)
        if queue == -1:
            smask[i] = 1
            suspended.update(under)
        elif ctype == 0:
            waiting.update(under)
            if queue in BURIED:
                buried.update(under)
        if count_new:
            if ctype == 0:
                if queue not in BURIED:
                    pos[cid] = i
                    news.append((cid, odid or did))
            elif due_today(queue, due, today, cutoff):
                sibling_due = True
        elif count_all or queue == -1:
            mask[i] = 1
    if news:
        settle(last_nid, news, sibling_due, under)
    idx.tag_cards = {k: v for k, v in tag_cards.items() if v}
    idx.fresh = total if count_all else suspended if only_suspended else plan

    children: dict[str, list[str]] = defaultdict(list)
    for low in names:
        cut = low.rfind(SEP)
        children[low[:cut] if cut >= 0 else ""].append(low)
    for kids in children.values():
        kids.sort(key=lambda k: natural_key(names[k].rsplit(SEP, 1)[-1]))
    idx.children = dict(children)

    # Leaf-topic counts, deepest tags first so children are done before parents.
    idx.post_order = sorted(names, key=lambda k: k.count(SEP), reverse=True)
    for low in idx.post_order:
        kids = idx.children.get(low)
        idx.leaves[low] = sum(idx.leaves[c] for c in kids) if kids else 1
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
    """Breadcrumb for a tag's *parents*, e.g. `Step 1 › B&B › 16 Neuro`."""
    root, parts = display_parts(tag, is_root)
    crumbs = " › ".join(short_name(p) for p in parts[:-1])
    if root and with_root:
        return f"{root_label(root)} › {crumbs}" if crumbs else root_label(root)
    return crumbs
