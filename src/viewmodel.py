# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""JSON-ready view data for the web UI.

A `View` snapshots the tag index, queue state and config for one bridge
request and turns them into plain dicts: tree nodes with their status and
progress, search results, the queue side panel, and card-count previews.
All the queue logic stays in Python; the web UI only renders it.
"""

from __future__ import annotations

from datetime import datetime

from aqt import mw

from . import actions, colorsync
from .config import get_config
from .counts import (
    TagIndex,
    fresh_ids,
    natural_key,
    prettify,
    resource_roots,
    root_label,
    root_matcher,
    short_path,
)
from .state import COMPLETED, QUEUED, SEP

GROUP_KEY = "__group__"
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
        self.roots = resource_roots(index, self.cfg["resource_roots"]) if index else []
        self.pinned = [p.lower() for p in self.cfg["pinned_resources"] if isinstance(p, str)]
        self.queued_l = [q.lower() for q in self.state.queued()]
        done = [c.lower() for c in self.state.completed()]
        done_set = set(done)
        # Completed tags with no completed ancestor, for leaf progress counts.
        self.top_done = [
            c for c in done
            if not any(SEP.join(c.split(SEP)[:i]) in done_set for i in range(1, c.count(SEP) + 1))
        ]
        self._queue_ids: set[int] | None = None

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

        resources = sorted(((c, r) for r in self.roots for c in idx.kids(r)),
                           key=lambda kr: (order(kr[0]), kr[1]))
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
        for key, root in resources:
            out.append({"value": key, "label": self.resource_label(key, root), "kind": "resource",
                        "pinned": key in self.pinned})
        for key in others:
            out.append({"value": key, "label": prettify(self.index.last(key)), "kind": "other",
                        "pinned": key in self.pinned})
        return out

    # --- tree nodes --------------------------------------------------------

    def node(self, key: str, label: str | None = None, top: bool = False) -> dict:
        idx = self.index
        name = idx.name(key)
        status, source = self.state.effective(name)
        inherited = status is not None and source.lower() != key
        nested = sum(1 for q in self.queued_l if q.startswith(key + SEP))
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
        return {
            "key": key,
            "tag": name,
            "label": label or prettify(idx.last(key)),
            "fresh": idx.fresh.get(key, 0),
            "total": idx.total.get(key, 0),
            "hasKids": bool(idx.kids(key)),
            "top": top,
            "pinned": top and key in self.pinned,
            "resource": self.is_resource(key),
            "check": check,
            "locked": locked,
            "status": status,
            "inherited": inherited,
            "source": prettify(source.rsplit(SEP, 1)[-1]) if inherited else None,
            "nestedQueued": nested,
            "progress": progress,
            "doneAt": fmt_day(self.state.completed_at(source)) if status == COMPLETED else None,
        }

    def nodes(self, keys: list[str]) -> list[dict]:
        if self.index is None:
            return []
        return [self.node(k) for k in dict.fromkeys(keys) if k in self.index.names]

    def children(self, key: str) -> list[dict]:
        if self.index is None:
            return []
        if key in ("", GROUP_KEY):
            return self.top_level(group_only=key == GROUP_KEY)
        return [self.node(c) for c in self.index.kids(key)]

    def top_level(self, group_only: bool = False) -> list[dict]:
        scope = self.scope_keys()
        resources, others = self.browse_entries()
        tops = [self.node(k, self.resource_label(k, r), top=True)
                for k, r in resources if self.in_scope(k, scope)]
        others = [k for k in others if self.in_scope(k, scope)]
        if group_only:
            return [self.node(k, top=True) for k in others]
        if others and self.roots and scope is None:
            tops.append({"key": GROUP_KEY, "label": "Other tags", "group": True,
                         "count": len(others), "hasKids": True})
        else:
            tops += [self.node(k, top=True) for k in others]
        return tops

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
        roots_out: list[str] = []
        for key in top:
            parts = key.split(SEP)
            start = 2 if parts[0] in roots else 1
            root = parts[0] if start == 2 else None
            parent = ""
            for i in range(start, len(parts) + 1):
                k = SEP.join(parts[:i])
                if k not in nodes:
                    label = self.resource_label(k, root) if i == start else None
                    nodes[k] = self.node(k, label, top=(i == start))
                    if parent:
                        children.setdefault(parent, []).append(k)
                    else:
                        roots_out.append(k)
                parent = k
        return {
            "nodes": list(nodes.values()),
            "children": children,
            "roots": roots_out,
            "matches": top,
            "truncated": truncated,
            "summary": self.match_summary(top, truncated),
        }

    # --- counts & previews -------------------------------------------------

    def queue_ids(self) -> set[int]:
        if self._queue_ids is None:
            q = self.state.queued()
            self._queue_ids = set(fresh_ids(mw.col, q, self.mode)) if q else set()
        return self._queue_ids

    def projection(self, tags: list[str]) -> tuple[int, int, int]:
        """(cards added, cards already queued via other topics, queue size after)."""
        ids = set(fresh_ids(mw.col, tags, self.mode)) if tags else set()
        queued = self.queue_ids()
        add = len(ids - queued)
        return add, len(ids) - add, len(queued) + add

    def match_candidates(self, keys: list[str]) -> tuple[list[str], int, int]:
        cands, queued, done = [], 0, 0
        for key in keys:
            if self.index is None or key not in self.index.names:
                continue
            name = self.index.name(key)
            status, _src = self.state.effective(name)
            if status == COMPLETED:
                done += 1
            elif status == QUEUED:
                queued += 1
            else:
                cands.append(name)
        return cands, queued, done

    def match_summary(self, keys: list[str], truncated: bool) -> dict:
        cands, queued, done = self.match_candidates(keys)
        add, _overlap, after = self.projection(cands) if cands and not truncated else (0, 0, 0)
        limit = self.cfg["card_limit"]
        return {
            "count": len(keys), "queued": queued, "done": done, "candidates": len(cands),
            "add": add, "after": after, "limit": limit, "over": after > limit,
            "truncated": truncated,
        }

    def details(self, key: str) -> dict | None:
        if self.index is None or key not in self.index.names:
            return None
        tag = self.index.name(key)
        status, source = self.state.effective(tag)
        out = {
            "key": key,
            "title": prettify(self.index.last(key)),
            "path": short_path(tag, root_matcher(self.cfg["resource_roots"]), True),
            "fresh": self.index.fresh.get(key, 0),
            "total": self.index.total.get(key, 0),
            "status": status,
            "via": None,
            "date": None,
            "limit": self.cfg["card_limit"],
        }
        if status == QUEUED and source.lower() != key:
            out["via"] = prettify(source.rsplit(SEP, 1)[-1])
        elif status == COMPLETED:
            out["date"] = fmt_day(self.state.completed_at(source))
        if status is None:
            add, overlap, after = self.projection([tag])
            out.update(add=add, overlap=overlap, after=after, over=after > self.cfg["card_limit"])
        return out

    # --- queue side panel --------------------------------------------------

    def side(self) -> dict:
        queued, done = self.state.queued(), self.state.completed()
        n, limit = len(self.queue_ids()), self.cfg["card_limit"]
        is_root = root_matcher(self.cfg["resource_roots"])
        with_root = len(self.roots) != 1
        names = self.index.names if self.index is not None else None

        def fresh(tag: str) -> int:
            if self.index is not None and self.index.mode == self.mode:
                return self.index.fresh.get(tag.lower(), 0)
            return len(fresh_ids(mw.col, [tag], self.mode))

        queue_rows = []
        for tag in queued:
            missing = names is not None and tag.lower() not in names
            queue_rows.append({
                "tag": tag, "key": tag.lower(), "title": prettify(tag.rsplit(SEP, 1)[-1]),
                "path": "Tag not found in this collection" if missing
                else short_path(tag, is_root, with_root),
                "fresh": fresh(tag), "missing": missing,
            })
        done_rows = [{
            "tag": tag, "key": tag.lower(), "title": prettify(tag.rsplit(SEP, 1)[-1]),
            "path": short_path(tag, is_root, with_root),
            "date": fmt_day(self.state.completed_at(tag)),
        } for tag in done]
        return {
            "count": n, "limit": limit, "over": n > limit,
            "unit": UNITS.get(self.mode, "cards"),
            "queued": queue_rows, "completed": done_rows,
        }

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
