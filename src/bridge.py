# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Command handler for the web UI.

The page calls `pycmd(JSON.stringify({cmd, ...args}), callback)`; Anki hands
the string to `Bridge.handle`, and whatever it returns is JSON-encoded back
to the callback. Mutating commands answer with a refresh "bundle" (queue
panel, the statuses of the rows the page is showing, the search summary), so
one round trip updates the whole screen.

The host is the Tag Queue window in Anki, or tools/devserver.py during
frontend development. It provides `index`, `request_index()`,
`reload_index()`, `push(event)` and is the parent widget for operations.
"""

from __future__ import annotations

import json
import time
import traceback

from aqt import mw

from . import actions, colorsync
from .config import get_config, update_config
from .state import COMPLETED, QUEUED
from .viewmodel import View

OPTION_KEYS = {
    "unsuspendOnComplete": "unsuspend_on_complete",
    "showOnDeck": "show_on_deck_screen",
    "colorSync": "colorful_tags_sync",
    "hideCompleted": "hide_completed",
}


class Bridge:
    def __init__(self, host):
        self.host = host
        self._toasts: list[str] | None = None

    # --- plumbing ----------------------------------------------------------

    def handle(self, raw: str):
        if not isinstance(raw, str) or not raw.startswith("{"):
            return None  # e.g. Anki's own "domDone"
        try:
            msg = json.loads(raw)
            fn = getattr(self, "cmd_" + str(msg.get("cmd")), None)
            if fn is None:
                return {"error": f"Unknown command: {msg.get('cmd')}"}
            self._toasts = []
            result = fn(msg) or {}
            result["toasts"] = self._toasts
            return result
        except Exception as exc:  # report to the page instead of a Qt error dialog
            traceback.print_exc()
            return {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            self._toasts = None

    @property
    def busy(self) -> bool:
        """True while answering a request (changes then travel in the reply)."""
        return self._toasts is not None

    def toast(self, message: str) -> None:
        if self._toasts is not None:
            self._toasts.append(message)
        else:
            self.host.push({"type": "toast", "message": message})

    def view(self) -> View:
        return View(self.host.index)

    def bundle(self, msg: dict) -> dict:
        view = self.view()
        out: dict = {"side": view.side(), "options": view.options()}
        if view.index is not None:
            out["nodes"] = view.nodes(msg.get("visible") or [])
            matches = msg.get("matches")
            if matches is not None:
                out["summary"] = view.match_summary(matches, bool(msg.get("truncated")))
            if msg.get("selected"):
                out["details"] = view.details(msg["selected"])
        return out

    @staticmethod
    def _tags(msg: dict) -> list[str]:
        return [t for t in msg.get("tags") or [] if isinstance(t, str) and t]

    # --- reads -------------------------------------------------------------

    def cmd_boot(self, msg: dict) -> dict:
        self.host.request_index()
        view = self.view()
        cfg = view.cfg
        return {
            "ready": view.index is not None,
            "side": view.side(),
            "scopes": view.scopes(),
            "scope": view.scope_value(),
            "options": view.options(),
            "colors": {"queued": cfg["queued_color"], "completed": cfg["completed_color"]},
        }

    def cmd_scopes(self, msg: dict) -> dict:
        view = self.view()
        return {"scopes": view.scopes(), "scope": view.scope_value()}

    def cmd_children(self, msg: dict) -> dict:
        return {"key": msg.get("key", ""), "nodes": self.view().children(msg.get("key", ""))}

    def cmd_search(self, msg: dict) -> dict:
        view = self.view()
        if view.index is None:
            return {"nodes": [], "children": {}, "roots": [], "matches": [], "truncated": False}
        return view.search(str(msg.get("query", "")))

    def cmd_details(self, msg: dict) -> dict:
        return {"details": self.view().details(str(msg.get("key", "")))}

    def cmd_sync(self, msg: dict) -> dict:
        return self.bundle(msg)

    def cmd_import_info(self, msg: dict) -> dict:
        ud = colorsync.find_user_data()
        if ud is None:
            return {"groups": [], "pins": 0}
        from .counts import prettify

        groups = []
        for color, tags in colorsync.color_groups(ud).items():
            sample = ", ".join(prettify(t.rsplit("::", 1)[-1]) for t in tags[:3])
            groups.append({
                "color": color, "count": len(tags),
                "sample": sample + (", …" if len(tags) > 3 else ""),
                "suggested": COMPLETED if colorsync.looks_green(color) else None,
            })
        return {"groups": groups, "pins": len(colorsync.pinned_tags(ud))}

    # --- status changes ----------------------------------------------------

    def cmd_queue(self, msg: dict) -> dict:
        actions.queue(self._tags(msg))
        return self.bundle(msg)

    def cmd_unqueue(self, msg: dict) -> dict:
        actions.unqueue(self._tags(msg))
        return self.bundle(msg)

    def cmd_clear(self, msg: dict) -> dict:
        actions.clear(self._tags(msg))
        return self.bundle(msg)

    def cmd_complete(self, msg: dict) -> dict:
        tags = self._tags(msg) or actions.load_state().queued()
        actions.complete(tags, self.host)
        return self.bundle(msg)

    def cmd_unsuspend(self, msg: dict) -> dict:
        tags = self._tags(msg) or actions.load_state().queued()
        actions.unsuspend(tags, self.host)
        return self.bundle(msg)

    def cmd_browse(self, msg: dict) -> dict:
        actions.browse(self._tags(msg) or actions.load_state().queued())
        return {}

    def cmd_queue_matches(self, msg: dict) -> dict:
        view = self.view()
        cands, _q, _d = view.match_candidates(msg.get("matches") or [])
        if cands and not msg.get("truncated"):
            add, _overlap, _after = view.projection(cands)
            actions.queue(cands)
            n = len(cands)
            self.toast(f"Queued {n:,} topic{'s' if n != 1 else ''} · +{add:,} new cards")
        return self.bundle(msg)

    # --- settings ----------------------------------------------------------

    def cmd_set_limit(self, msg: dict) -> dict:
        try:
            value = max(1, min(5000, int(msg.get("value"))))
        except (TypeError, ValueError):
            value = get_config()["card_limit"]
        update_config(card_limit=value)
        actions.refresh_main_screen()
        return self.bundle(msg)

    def cmd_set_scope(self, msg: dict) -> dict:
        update_config(search_scope=str(msg.get("value") or "all"))
        view = self.view()
        return {"scopes": view.scopes(), "scope": view.scope_value()}

    def cmd_set_option(self, msg: dict) -> dict:
        key = OPTION_KEYS.get(str(msg.get("key")))
        if key:
            update_config(**{key: bool(msg.get("value"))})
            if key == "show_on_deck_screen":
                actions.refresh_main_screen()
        return self.bundle(msg)

    def cmd_toggle_pin(self, msg: dict) -> dict:
        tag = str(msg.get("tag", ""))
        pins = [p for p in get_config()["pinned_resources"] if isinstance(p, str)]
        rest = [p for p in pins if p.lower() != tag.lower()]
        update_config(pinned_resources=rest if len(rest) != len(pins) else pins + [tag])
        view = self.view()
        return {"scopes": view.scopes(), "scope": view.scope_value()}

    def cmd_refresh(self, msg: dict) -> dict:
        self.host.reload_index(force=True)
        return {}

    def cmd_edit_config(self, msg: dict) -> dict:
        import aqt

        aqt.dialogs.open("AddonsDialog", mw)
        return {}

    def cmd_dismiss_banner(self, msg: dict) -> dict:
        update_config(import_offered=True)
        return {"options": self.view().options()}

    def cmd_import_colors(self, msg: dict) -> dict:
        """Map Colorful Tags colours to statuses: {"choices": {"#00f900":
        "completed", ...}, "pins": true}."""
        ud = colorsync.find_user_data()
        if ud is None:
            return {"error": "Colorful Tags isn't installed or is disabled."}
        choices = msg.get("choices") or {}
        index = self.host.index
        names = index.names if index is not None else None
        state = actions.load_state()
        now = int(time.time())
        changes: dict = {}
        counts = {QUEUED: 0, COMPLETED: 0}
        skipped = 0
        for color, tags in colorsync.color_groups(ud).items():
            status = choices.get(color)
            if status not in (QUEUED, COMPLETED):
                continue
            for tag in tags:
                if names is not None:
                    if tag.lower() not in names:
                        skipped += 1
                        continue
                    tag = names[tag.lower()]
                changes.update(state.import_status(tag, status, 0 if status == COMPLETED else now))
                counts[status] += 1
        if msg.get("pins"):
            pins = [p for p in get_config()["pinned_resources"] if isinstance(p, str)]
            have = {p.lower() for p in pins}
            pins += [t for t in colorsync.pinned_tags(ud) if t.lower() not in have]
            update_config(pinned_resources=pins)
        update_config(import_offered=True)
        actions.commit(state, changes)
        text = (f"Imported {counts[QUEUED]:,} queued and {counts[COMPLETED]:,} completed topics")
        if skipped:
            text += f" · skipped {skipped:,} tags that no longer exist"
        self.toast(text)
        view = self.view()
        return {"scopes": view.scopes(), "scope": view.scope_value(), "options": view.options()}
