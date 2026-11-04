# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""JSON-ready view data for the web UI.

A `View` snapshots the tag index, queue state and config for one bridge
request and turns them into plain dicts: tree nodes with their status and
progress, search results, the queue side panel, and card-count previews.
All the queue logic stays in Python; the web UI only renders it.

Resources are grouped under their root (AnKing's Step 1 / Step 2 / Step 3
decks): the tree and search results show a header per step, and every row
carries the step's label and index so the UI can colour-code it.
"""

from __future__ import annotations

from datetime import datetime

from . import actions, colorsync
from .config import get_config
from .counts import (
    TagIndex,
    natural_key,
    plan_fill,
    prettify,
    resource_roots,
    root_label,
    root_matcher,
    short_path,
)
from .state import COMPLETED, LATER, QUEUED, SEP

GROUP_KEY = "__group__"
ROOT_PREFIX = "__root__:"
MAX_MATCHES = 200
SCOPE_ALL = "all"
SCOPE_PINNED = "pinned"
UNITS = {"new": "new cards", "suspended": "suspended cards", "all": "cards"}


def fmt_day(ts: int) -> str:
    if not ts:
        return "imported"
    dt = datetime.fromtimestamp(ts)
    s = f"{dt:%b} {dt.day}"
    return s if dt.year == datetime.now().year else f"{s}, {dt.year}"


class View:
    def __init__(self, index: TagIndex | None):
        self.index = index
        self.cfg = get_config()
        self.state = actions.load_state()
        self.mode = self.cfg["count_mode"]
        self.is_root = root_matcher(self.cfg["resource_roots"])
        self.roots = resource_roots(index, self.cfg["resource_roots"]) if index else []
        self.pinned = [p.lower() for p in self.cfg["pinned_resources"] if isinstance(p, str)]
        self.queued_l = [q.lower() for q in self.state.queued()]
        self.later_l = [q.lower() for q in self.state.later()]
        done = [c.lower() for c in self.state.completed()]
        done_set = set(done)
        # Completed tags with no completed ancestor, for leaf progress counts.
        self.top_done = [
            c for c in done
            if not any(SEP.join(c.split(SEP)[:i]) in done_set for i in range(1, c.count(SEP) + 1))
        ]
        self._queue_ids: set[int] | None = None

    # --- steps (resource roots) --------------------------------------------

    def step_of(self, tag: str) -> tuple[str | None, int | None]:
        """("Step 1", 0) for any tag under a resource root, else (None, None)."""
        first = tag.split(SEP, 1)[0]
        if SEP not in tag or not self.is_root(first):
            return None, None
        key = first.lower()
        i = self.roots.index(key) if key in self.roots else 0
        return root_label(first), i

    def root_header(self, root: str, count: int) -> dict:
        idx = self.index
        leaves = idx.leaves.get(root, 1)
        done = sum(idx.leaves.get(c, 1) for c in self.top_done if c.startswith(root + SEP))
        return {
            "key": ROOT_PREFIX + root,
            "group": True,
            "kind": "root",
            "label": root_label(idx.name(root)),
            "sub": idx.name(root),
            "count": count,
            "hasKids": True,
            "fresh": idx.fresh.get(root, 0),
            "total": idx.total.get(root, 0),
            "progress": {"done": done, "total": leaves} if leaves > 1 and done else None,
            "stepIndex": self.roots.index(root),
        }

    # --- resources & scope -------------------------------------------------

    def is_resource(self, key: str) -> bool:
        parent = key.rsplit(SEP, 1)[0] if SEP in key else ""
        return parent in self.roots or (parent == "" and key not in self.roots)

    def resource_label(self, key: str, root: str | None) -> str:
        label = prettify(self.index.last(key))
        if root and len(self.roots) > 1:
            label += f" · {root_label(self.index.name(root))}"
        return label

    def browse_entries(self) -> tuple[list[tuple[str, str]], list[str]]:
        idx, pinned = self.index, self.pinned

        def order(key: str):
            return (key not in pinned, pinned.index(key) if key in pinned else 0,
                    natural_key(idx.last(key)))

        resources = [(c, r) for r in self.roots for c in sorted(idx.kids(r), key=order)]
        others = sorted((k for k in idx.kids("") if k not in self.roots), key=order)
        return resources, others

    def pinned_resources(self) -> list[str]:
        if self.index is None:
            return []
        return [p for p in self.pinned if p in self.index.names and self.is_resource(p)]

    def scope_value(self) -> str:
        v = self.cfg["search_scope"]
        v = v.lower() if isinstance(v, str) else SCOPE_ALL
        if v == SCOPE_PINNED:
            return v if self.pinned_resources() else SCOPE_ALL
        if v in self.roots:
            return v
        if v != SCOPE_ALL and self.index is not None and v in self.index.names and self.is_resource(v):
            return v
        return SCOPE_ALL

    def scope_keys(self) -> set[str] | None:
        v = self.scope_value()
        if v == SCOPE_ALL:
            return None
        if v == SCOPE_PINNED:
            return set(self.pinned_resources())
        return {v}

    @staticmethod
    def in_scope(key: str, scope: set[str] | None) -> bool:
        return scope is None or any(key == s or key.startswith(s + SEP) for s in scope)

    def scopes(self) -> list[dict]:
        out = [{"value": SCOPE_ALL, "label": "All resources", "kind": "all"}]
        if self.index is None:
            return out
        if self.pinned_resources():
            out.append({"value": SCOPE_PINNED, "label": "Pinned resources", "kind": "pinned"})
        resources, others = self.browse_entries()
        for i, root in enumerate(self.roots):
            step = root_label(self.index.name(root))
            out.append({"value": root, "label": f"All of {step}", "short": f"All of {step}",
                        "kind": "root", "group": step, "stepIndex": i})
            for key, r in resources:
                if r == root:
                    out.append({"value": key, "label": self.resource_label(key, root),
                                "short": prettify(self.index.last(key)), "kind": "resource",
                                "group": step, "stepIndex": i, "pinned": key in self.pinned})
        for key in others:
            name = prettify(self.index.last(key))
            out.append({"value": key, "label": name, "short": name, "kind": "other",
                        "group": "Other tags", "pinned": key in self.pinned})
        return out

    # --- tree nodes --------------------------------------------------------

    def node(self, key: str, label: str | None = None, top: bool = False) -> dict:
        idx = self.index
        name = idx.name(key)
        status, source = self.state.effective(name)
        inherited = status is not None and source.lower() != key
        nested = sum(1 for q in self.queued_l if q.startswith(key + SEP))
        nested_later = sum(1 for q in self.later_l if q.startswith(key + SEP))
        if status == QUEUED:
            check, locked = "on", inherited
        else:
            check, locked = ("partial" if nested else "off"), False
        leaves = idx.leaves.get(key, 1)
        progress = None
        if leaves > 1:
            done = leaves if status == COMPLETED else sum(
                idx.leaves.get(c, 1) for c in self.top_done if c.startswith(key + SEP))
            progress = {"done": done, "total": leaves}
        resource = self.is_resource(key)
        step, step_index = self.step_of(name) if resource else (None, None)
        return {
            "key": key,
            "tag": name,
            "label": label or prettify(idx.last(key)),
            "fresh": idx.fresh.get(key, 0),
            "total": idx.total.get(key, 0),
            "hasKids": bool(idx.kids(key)),
            "top": top,
            "pinned": top and key in self.pinned,
            "resource": resource,
            "step": step,
            "stepIndex": step_index,
            "check": check,
            "locked": locked,
            "status": status,
            "inherited": inherited,
            "source": prettify(source.rsplit(SEP, 1)[-1]) if inherited else None,
            "nestedQueued": nested,
            "nestedLater": nested_later,
            "progress": progress,
            "since": fmt_day(self.state.since(source)) if status else None,
        }

    def nodes(self, keys: list[str]) -> list[dict]:
        if self.index is None:
            return []
        return [self.node(k) for k in dict.fromkeys(keys) if k in self.index.names]

    def children(self, key: str) -> list[dict]:
        if self.index is None:
            return []
        if key == "":
            return self.top_level()
        scope = self.scope_keys()
        resources, others = self.browse_entries()
        if key.startswith(ROOT_PREFIX):
            root = key[len(ROOT_PREFIX):]
            return [self.node(k, top=True) for k, r in resources
                    if r == root and self.in_scope(k, scope)]
        if key == GROUP_KEY:
            return [self.node(k, top=True) for k in others if self.in_scope(k, scope)]
        return [self.node(c) for c in self.index.kids(key)]

    def top_level(self) -> list[dict]:
        """One header per step (Step 1, Step 2, ...) holding its resources,
        then "Other tags". A single resource in scope is shown directly."""
        scope = self.scope_keys()
        resources, others = self.browse_entries()
        res = [(k, r) for k, r in resources if self.in_scope(k, scope)]
        others = [k for k in others if self.in_scope(k, scope)]
        if len(res) + len(others) == 1:
            return [self.node(res[0][0] if res else others[0], top=True)]
        out = []
        for root in self.roots:
            n = sum(1 for _k, r in res if r == root)
            if n:
                out.append(self.root_header(root, n))
        if others and self.roots and scope is None:
            out.append({"key": GROUP_KEY, "group": True, "kind": "other", "label": "Other tags",
                        "count": len(others), "hasKids": True})
        else:
            out += [self.node(k, top=True) for k in others]
        return out

    def search(self, query: str) -> dict:
        idx = self.index
        words = query.lower().replace("_", " ").split()
        roots = set(self.roots)
        scope = self.scope_keys()
        matches = [
            k for k in idx.names
            if k not in roots
            and self.in_scope(k, scope)
            and all(w in k.replace("_", " ") for w in words)
        ]
        mset = set(matches)

        def has_matched_ancestor(k: str) -> bool:
            parts = k.split(SEP)
            return any(SEP.join(parts[:i]) in mset for i in range(1, len(parts)))

        top = sorted((k for k in matches if not has_matched_ancestor(k)),
                     key=lambda k: natural_key(idx.name(k)))
        truncated = len(top) > MAX_MATCHES
        top = top[:MAX_MATCHES]

        nodes: dict[str, dict] = {}
        children: dict[str, list[str]] = {}
        by_root: dict[str, list[str]] = {}
        other_tops: list[str] = []
        for key in top:
            parts = key.split(SEP)
            root = parts[0] if parts[0] in roots else None
            start = 2 if root else 1
            parent = ""
            for i in range(start, len(parts) + 1):
                k = SEP.join(parts[:i])
                if k not in nodes:
                    nodes[k] = self.node(k, top=(i == start))
                    if parent:
                        children.setdefault(parent, []).append(k)
                    elif root:
                        by_root.setdefault(root, []).append(k)
                    else:
                        other_tops.append(k)
                parent = k
        headers = []
        for root in self.roots:
            if root in by_root:
                h = self.root_header(root, len(by_root[root]))
                headers.append(h)
                children[h["key"]] = by_root[root]
        return {
            "nodes": headers + list(nodes.values()),
            "children": children,
            "roots": [h["key"] for h in headers] + other_tops,
            "matches": top,
            "truncated": truncated,
            "summary": self.match_summary(top, truncated),
        }

    # --- counts & previews -------------------------------------------------

    def queue_ids(self) -> set[int]:
        if self._queue_ids is None:
            self._queue_ids = actions.fresh_cards(self.state.queued())
        return self._queue_ids

    def projection(self, tags: list[str]) -> tuple[int, int, int]:
        """(cards added, cards already queued via other topics, queue size after)."""
        ids = actions.fresh_cards(tags)
        queued = self.queue_ids()
        add = len(ids - queued)
        return add, len(ids) - add, len(queued) + add

    def match_candidates(self, keys: list[str], for_later: bool = False) -> tuple[list[str], dict]:
        """Tags a bulk action applies to, plus counts by status. Queuing
        takes untouched and Later matches; saving for later takes only
        untouched ones. Completed and queued matches are never changed."""
        counts = {QUEUED: 0, COMPLETED: 0, LATER: 0}
        cands = []
        for key in keys:
            if self.index is None or key not in self.index.names:
                continue
            name = self.index.name(key)
            status, _src = self.state.effective(name)
            if status in counts:
                counts[status] += 1
            if status is None or (status == LATER and not for_later):
                cands.append(name)
        return cands, counts

    def match_summary(self, keys: list[str], truncated: bool) -> dict:
        cands, counts = self.match_candidates(keys)
        later_cands, _ = self.match_candidates(keys, for_later=True)
        add, _overlap, after = self.projection(cands) if cands and not truncated else (0, 0, 0)
        limit = self.cfg["card_limit"]
        return {
            "count": len(keys), "queued": counts[QUEUED], "done": counts[COMPLETED],
            "later": counts[LATER], "candidates": len(cands), "laterCandidates": len(later_cands),
            "add": add, "after": after, "limit": limit, "over": after > limit,
            "truncated": truncated,
        }

    def details(self, key: str) -> dict | None:
        if self.index is None or key not in self.index.names:
            return None
        tag = self.index.name(key)
        status, source = self.state.effective(tag)
        step, step_index = self.step_of(tag)
        out = {
            "key": key,
            "tag": tag,
            "title": prettify(self.index.last(key)),
            "path": short_path(tag, self.is_root, False),
            "step": step,
            "stepIndex": step_index,
            "fresh": self.index.fresh.get(key, 0),
            "total": self.index.total.get(key, 0),
            "status": status,
            "via": None,
            "date": None,
            "limit": self.cfg["card_limit"],
        }
        if status is not None and source.lower() != key:
            out["via"] = prettify(source.rsplit(SEP, 1)[-1])
        if status in (COMPLETED, LATER):
            out["date"] = fmt_day(self.state.since(source))
        if status in (None, LATER):
            add, overlap, after = self.projection([tag])
            out.update(add=add, overlap=overlap, after=after, over=after > self.cfg["card_limit"])
        return out

    # --- queue side panel --------------------------------------------------

    def _row(self, tag: str) -> dict:
        step, step_index = self.step_of(tag)
        return {
            "tag": tag, "key": tag.lower(), "title": prettify(tag.rsplit(SEP, 1)[-1]),
            "path": short_path(tag, self.is_root, False), "step": step, "stepIndex": step_index,
        }

    def _fresh(self, tag: str) -> int:
        if self.index is not None and self.index.mode == self.mode:
            return self.index.fresh.get(tag.lower(), 0)
        return len(actions.fresh_cards([tag]))

    def side(self) -> dict:
        queued, later, done = self.state.queued(), self.state.later(), self.state.completed()
        n, limit = len(self.queue_ids()), self.cfg["card_limit"]
        names = self.index.names if self.index is not None else None

        def missing(tag: str) -> bool:
            return names is not None and tag.lower() not in names

        def live(tag: str) -> dict:
            row = self._row(tag)
            row.update(fresh=self._fresh(tag), missing=missing(tag))
            if row["missing"]:
                row["path"] = "Tag not found in this collection"
            return row

        queue_rows = [live(t) for t in queued]
        later_rows = [dict(live(t), date=fmt_day(self.state.since(t))) for t in later]
        done_rows = [dict(self._row(t), date=fmt_day(self.state.since(t))) for t in done]
        return {
            "count": n, "limit": limit, "over": n > limit,
            "unit": UNITS.get(self.mode, "cards"),
            "queued": queue_rows, "later": later_rows, "completed": done_rows,
        }

    def later_plan(self) -> dict:
        """What "Fill queue from Later" would do right now."""
        later = self.state.later()
        if not later:
            return {"picked": 0, "add": 0, "after": len(self.queue_ids()), "skipped": 0}
        picked, add, skipped = plan_fill(
            actions.fresh_cards, later, self.state.queued(), self.cfg["card_limit"])
        return {"picked": len(picked), "add": add, "after": len(self.queue_ids()) + add,
                "skipped": len(skipped), "limit": self.cfg["card_limit"]}

    def options(self) -> dict:
        ud = colorsync.find_user_data()
        return {
            "unsuspendOnComplete": bool(self.cfg["unsuspend_on_complete"]),
            "showOnDeck": bool(self.cfg["show_on_deck_screen"]),
            "colorSync": bool(self.cfg["colorful_tags_sync"]),
            "colorSyncAvailable": ud is not None,
            "hideCompleted": bool(self.cfg["hide_completed"]),
            "banner": (not self.cfg["import_offered"] and ud is not None
                       and bool(colorsync.color_groups(ud))),
        }
