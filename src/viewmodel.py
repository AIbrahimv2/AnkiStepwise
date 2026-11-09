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
from .config import DEFAULTS, get_config
from .counts import (
    TagIndex,
    natural_key,
    plan_fill,
    prettify,
    resource_roots,
    root_label,
    root_matcher,
    short_name,
    short_path,
)
from .state import COMPLETED, LATER, QUEUED, SEP

GROUP_KEY = "__group__"
ROOT_PREFIX = "__root__:"
MAX_MATCHES = 200
SCOPE_ALL = "all"
SCOPE_PINNED = "pinned"
UNITS = {"new": "new cards", "suspended": "to unsuspend", "all": "cards"}


def fmt_day(ts: int) -> str:
    if not ts:
        return "imported"
    dt = datetime.fromtimestamp(ts)
    s = f"{dt:%b} {dt.day}"
    return s if dt.year == datetime.now().year else f"{s}, {dt.year}"


DONE_PAGE = 100  # Done rows sent with every reply; the tab pages in the rest


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
        # Done = completed, or nothing left to unsuspend (see rollup.py).
        self.done, self.done_leaves = actions.done_info() if index else (set(), {})
        self._queue_ids: set[int] | None = None

    def status_of(self, key: str) -> tuple[str | None, str | None, bool]:
        """(status, tag it comes from, automatic). A tag with no status of
        its own (or inherited) is "completed" automatically when it's done:
        all its cards are unsuspended."""
        status, source = self.state.effective(self.index.name(key) if self.index else key)
        if status is None and key in self.done:
            return COMPLETED, None, True
        return status, source, False

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
        done = self.done_leaves.get(root, 0)
        return {
            "key": ROOT_PREFIX + root,
            "group": True,
            "kind": "root",
            "label": root_label(idx.name(root)),
            "sub": idx.name(root),
            "count": count,
            "hasKids": True,
            "fresh": idx.fresh.get(root, 0),
            "suspended": idx.suspended.get(root, 0),
            "waiting": idx.waiting.get(root, 0),
            "buried": idx.buried.get(root, 0),
            "total": idx.total.get(root, 0),
            "progress": {"done": done, "total": leaves} if leaves > 1 and done else None,
            "stepIndex": self.roots.index(root),
        }

    # --- resources & scope -------------------------------------------------

    def is_resource(self, key: str) -> bool:
        parent = key.rsplit(SEP, 1)[0] if SEP in key else ""
        return parent in self.roots or (parent == "" and key not in self.roots)

    def browse_entries(self) -> tuple[list[tuple[str, str]], list[str]]:
        idx, pinned = self.index, self.pinned

        def order(key: str):
            return (key not in pinned, natural_key(idx.last(key)))

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
                    # The picker shows the step beside the name, so the
                    # label stays just the resource.
                    name = prettify(self.index.last(key))
                    out.append({"value": key, "label": name, "short": name, "kind": "resource",
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
        status, source, auto = self.status_of(key)
        inherited = status is not None and not auto and source.lower() != key
        nested = any(q.startswith(key + SEP) for q in self.queued_l)
        if status == QUEUED:
            check, locked = "on", inherited
        else:
            check, locked = ("partial" if nested else "off"), False
        leaves = idx.leaves.get(key, 1)
        progress = None
        if leaves > 1:
            done = leaves if status == COMPLETED else self.done_leaves.get(key, 0)
            progress = {"done": done, "total": leaves}
        resource = self.is_resource(key)
        step, step_index = self.step_of(name) if resource else (None, None)
        return {
            "key": key,
            "tag": name,
            "label": label or prettify(idx.last(key)),
            "fresh": idx.fresh.get(key, 0),
            "suspended": idx.suspended.get(key, 0),
            "waiting": idx.waiting.get(key, 0),
            "buried": idx.buried.get(key, 0),
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
            "source": short_name(source.rsplit(SEP, 1)[-1]) if inherited else None,
            "progress": progress,
            "since": fmt_day(self.state.since(source)) if status and not auto else None,
            # Done only because nothing under it is suspended any more.
            "auto": auto,
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

    def children_page(self, key: str, offset: int = 0,
                      limit: int | None = None) -> tuple[list[dict], int]:
        """One page of a folder's children plus how many it has in total.
        Some folders (UWorld question IDs) hold thousands of tags; sending
        them all at once would stall both Python and the page."""
        if self.index is None:
            return [], 0
        if key == "" or key.startswith(ROOT_PREFIX) or key == GROUP_KEY:
            nodes = self.children(key)
            return nodes, len(nodes)
        kids = self.index.kids(key)
        end = len(kids) if limit is None else offset + limit
        return [self.node(c) for c in kids[offset:end]], len(kids)

    def locate(self, key: str) -> dict:
        """How to show `key` in the browse tree: the rows to expand, top
        down (step section or "Other tags", resource, parent folders), how
        many children each folder must load to include the next one, and
        whether the current resource filter hides it."""
        idx = self.index
        if idx is None or key not in idx.names:
            return {"exists": False}
        parts = key.split(SEP)
        chain: list[str] = []
        limits: dict[str, int] = {}
        if len(parts) > 1 and parts[0] in self.roots:
            chain.append(ROOT_PREFIX + parts[0])
            start = 2
        else:
            if self.roots:
                chain.append(GROUP_KEY)
            start = 1
        for i in range(start, len(parts)):
            folder, child = SEP.join(parts[:i]), SEP.join(parts[:i + 1])
            chain.append(folder)
            kids = idx.kids(folder)
            if child in kids:
                limits[folder] = kids.index(child) + 1
        status, _src = self.state.effective(idx.name(key))
        return {
            "exists": True,
            "open": chain,
            "limits": limits,
            "inScope": self.in_scope(key, self.scope_keys()),
            "status": status,
        }

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
        """Cards counted for the current session: everything queued plus the
        topics already watched this session."""
        if self._queue_ids is None:
            self._queue_ids = actions.fresh_cards(self.state.session_tags())
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
            status, _src, _auto = self.status_of(key)
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
        status, source, auto = self.status_of(key)
        step, step_index = self.step_of(tag)
        out = {
            "key": key,
            "tag": tag,
            "title": short_name(tag.rsplit(SEP, 1)[-1]),
            "path": short_path(tag, self.is_root, False),
            "step": step,
            "stepIndex": step_index,
            "fresh": self.index.fresh.get(key, 0),
            "suspended": self.index.suspended.get(key, 0),
            "waiting": self.index.waiting.get(key, 0),
            "buried": self.index.buried.get(key, 0),
            "total": self.index.total.get(key, 0),
            "mode": self.mode,
            "status": status,
            "via": None,
            "date": None,
            "limit": self.cfg["card_limit"],
            "auto": auto,
        }
        if status is not None and not auto and source.lower() != key:
            out["via"] = short_name(source.rsplit(SEP, 1)[-1])
        if status in (COMPLETED, LATER) and not auto:
            out["date"] = fmt_day(self.state.since(source))
        if status in (None, LATER):
            add, overlap, after = self.projection([tag])
            out.update(add=add, overlap=overlap, after=after, over=after > self.cfg["card_limit"])
        return out

    # --- queue side panel --------------------------------------------------

    def _row(self, tag: str) -> dict:
        step, step_index = self.step_of(tag)
        return {
            "tag": tag, "key": tag.lower(), "title": short_name(tag.rsplit(SEP, 1)[-1]),
            "path": short_path(tag, self.is_root, False), "step": step, "stepIndex": step_index,
        }

    def _fresh(self, tag: str) -> int:
        if self.index is not None and self.index.mode == self.mode:
            return self.index.fresh.get(tag.lower(), 0)
        return len(actions.fresh_cards([tag]))

    def grouped(self, rows: list[dict]) -> list[dict]:
        """Rows grouped by resource (B&B, Pixorize, ...), each group sorted
        by tag path so topics sharing a parent folder sit together. Every
        row gets `parent` (its parent tag) and `sub` (that folder's path
        inside the resource) so the page can cluster siblings."""
        groups: dict[str, dict] = {}
        for row in rows:
            tag = row["tag"]
            parts = tag.split(SEP)
            n = 2 if len(parts) > 1 and self.is_root(parts[0]) else 1
            resource = SEP.join(parts[:n])
            group = groups.get(resource.lower())
            if group is None:
                step, step_index = self.step_of(tag) if n == 2 else (None, None)
                group = groups[resource.lower()] = {
                    "key": resource.lower(), "tag": resource, "label": short_name(parts[n - 1]),
                    "step": step, "stepIndex": step_index, "rows": [],
                }
            group["rows"].append(dict(
                row, parent=SEP.join(parts[:-1]).lower(),
                sub=" › ".join(short_name(p) for p in parts[n:-1])))
        for group in groups.values():
            group["rows"].sort(key=lambda r: natural_key(r["tag"]))
            tags = [r["tag"] for r in group["rows"]]
            group["count"] = len(tags)
            group["watched"] = sum(1 for r in group["rows"] if r.get("watched"))
            group["fresh"] = len(actions.fresh_cards(tags))  # unique within the group
        return sorted(groups.values(), key=lambda g: (
            g["stepIndex"] if g["stepIndex"] is not None else 99, natural_key(g["label"])))

    def done_rows(self, offset: int = 0, limit: int = DONE_PAGE) -> list[dict]:
        """A page of the Done list, newest first."""
        done = self.state.completed()[offset:offset + limit]
        return [dict(self._row(t), date=fmt_day(self.state.since(t))) for t in done]

    def side(self) -> dict:
        queued, later = self.state.queued(), self.state.later()
        n, limit = len(self.queue_ids()), self.cfg["card_limit"]
        names = self.index.names if self.index is not None else None

        def missing(tag: str) -> bool:
            return names is not None and tag.lower() not in names

        def live(tag: str, watched: bool = False) -> dict:
            row = self._row(tag)
            idx, low = self.index, tag.lower()
            row.update(fresh=self._fresh(tag), missing=missing(tag), watched=watched,
                       suspended=idx.suspended.get(low, 0) if idx else 0,
                       waiting=idx.waiting.get(low, 0) if idx else 0,
                       buried=idx.buried.get(low, 0) if idx else 0)
            # New cards Anki holds back today (siblings buried, or one of
            # theirs due): they count from the day they can show.
            if self.mode == "new" and idx is not None and idx.mode == self.mode:
                row["afterToday"] = max(0, idx.new.get(low, 0) - row["fresh"])
            if row["missing"]:
                row["path"] = "Tag not found in this collection"
            return row

        watched = [t for t in self.state.watched() if t.lower() not in {q.lower() for q in queued}]
        queue_rows = [live(t) for t in queued] + [live(t, watched=True) for t in watched]
        later_rows = [dict(live(t), date=fmt_day(self.state.since(t))) for t in later]
        return {
            "count": n, "limit": limit, "over": n > limit, "mode": self.mode,
            "watched": len(watched), "toWatch": len(queued),
            "unit": UNITS.get(self.mode, "cards"),
            # Done can hold thousands of topics once fully studied ones are
            # swept in; replies carry the newest page and the tab loads more.
            "queued": queue_rows, "later": later_rows, "completed": self.done_rows(),
            "doneTotal": len(self.state.completed()),
            "queueGroups": self.grouped(queue_rows), "laterGroups": self.grouped(later_rows),
        }

    def later_plan(self) -> dict:
        """What "Fill queue from Later" would do right now."""
        later = self.state.later()
        if not later:
            return {"picked": 0, "add": 0, "after": len(self.queue_ids()), "skipped": 0}
        picked, add, skipped = plan_fill(
            actions.fresh_cards, later, self.state.session_tags(), self.cfg["card_limit"])
        return {"picked": len(picked), "add": add, "after": len(self.queue_ids()) + add,
                "skipped": len(skipped), "limit": self.cfg["card_limit"]}

    def settings(self) -> dict:
        """Everything the Settings dialog edits, plus its defaults."""
        cfg = self.cfg

        def shape(c: dict) -> dict:
            return {
                "cardLimit": c["card_limit"],
                "countMode": c["count_mode"],
                "unsuspendOnComplete": bool(c["unsuspend_on_complete"]),
                "resourceRoots": [str(p) for p in c["resource_roots"]],
                "showOnDeck": bool(c["show_on_deck_screen"]),
                "colorSync": bool(c["colorful_tags_sync"]),
                "colors": {"queued": c["queued_color"], "completed": c["completed_color"],
                           "later": c["later_color"]},
                "shortcut": c["shortcut"],
            }

        pinned = []
        for tag in cfg["pinned_resources"]:
            if not isinstance(tag, str):
                continue
            parts = tag.split(SEP)
            root = parts[0] if len(parts) > 1 and self.is_root(parts[0]) else None
            key = root.lower() if root else None
            pinned.append({"tag": tag, "label": prettify(parts[-1]),
                           "step": root_label(root) if root else None,
                           "stepIndex": self.roots.index(key) if key in self.roots else None})
        # Same order as the tree: by step, then by name; other tags last.
        pinned.sort(key=lambda p: (p["stepIndex"] is None, p["stepIndex"] or 0,
                                   natural_key(p["tag"].rsplit(SEP, 1)[-1])))
        return {
            **shape(cfg),
            "pinned": pinned,
            "defaults": shape(DEFAULTS),
            "colorSyncAvailable": colorsync.find_user_data() is not None,
        }

    def root_matches(self, patterns: list[str]) -> list[list[str] | None]:
        """For each resource-folder pattern, the top-level tags it matches
        (None until cards are counted)."""
        if self.index is None:
            return [None for _ in patterns]
        return [[self.index.name(k) for k in resource_roots(self.index, [p])] if p.strip() else []
                for p in patterns]

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
