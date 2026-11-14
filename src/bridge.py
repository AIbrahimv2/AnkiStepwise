# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Command handler for the web UI.

The page calls `pycmd(JSON.stringify({cmd, ...args}), callback)`; Anki hands
the string to `Bridge.handle`, and whatever it returns is JSON-encoded back
to the callback. Mutating commands answer with a refresh "bundle" (queue
panel, the statuses of the rows the page is showing, the search summary), so
one round trip updates the whole screen.

The host is the Stepwise window in Anki, or tools/devserver.py during
frontend development. It provides `index`, `request_index()`,
`reload_index()`, `push(event)` and is the parent widget for operations.
"""

from __future__ import annotations

import json
import time
import traceback

from aqt import mw

from . import actions, colorsync, history, kit, skim_link
from .config import check_settings, get_config, update_config
from .state import COMPLETED, LATER, QUEUED
from .viewmodel import View

OPTION_KEYS = {
    "unsuspendOnComplete": "unsuspend_on_complete",
    "showOnDeck": "show_on_deck_screen",
    "colorSync": "colorful_tags_sync",
    "hideCompleted": "hide_completed",
}


# Commands that change the queue (or unsuspend cards): each becomes one
# undo step.
UNDOABLE = {
    "queue", "unqueue", "clear", "complete", "unsuspend", "unwatch", "finish_session",
    "queue_matches", "later", "unlater", "later_matches", "fill_from_later", "import_colors",
}


# Which tree folders are open (and which step sections you closed), kept in
# the Anki profile: per profile, not synced, like window sizes.
TREE_KEY = "tagQueue.tree"
_tree_fallback: dict = {}  # outside Anki (tests, dev server)


def _tree_store() -> dict:
    profile = getattr(getattr(mw, "pm", None), "profile", None)
    return profile if isinstance(profile, dict) else _tree_fallback


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}" + ("" if n == 1 else "s")


class Bridge:
    def __init__(self, host):
        self.host = host
        self._toasts: list[str] | None = None
        # Anki's Config button can ask for Settings before the page has
        # loaded; the page opens them when it boots.
        self.booted = False
        self.settings_on_boot = False

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
            cmd = str(msg.get("cmd"))
            if cmd in UNDOABLE:
                before = history.snapshot()
                actions.take_unsuspended()
            result = fn(msg) or {}
            if cmd in UNDOABLE:
                history.record(self._undo_label(cmd, msg), before, history.snapshot(),
                               actions.take_unsuspended())
            result["toasts"] = self._toasts
            return result
        except Exception as exc:  # report to the page instead of a Qt error dialog
            traceback.print_exc()
            return {"error": f"{type(exc).__name__}: {exc}"}
        finally:
            self._toasts = None

    def _undo_label(self, cmd: str, msg: dict) -> str:
        """What an undo step did, for the "Undone" toast."""
        from .counts import short_name

        tags = self._tags(msg)
        what = (short_name(tags[0].rsplit("::", 1)[-1]) if len(tags) == 1
                else _plural(len(tags), "topic"))
        return {
            "queue": f"Queued {what}",
            "unqueue": f"Removed {what} from the queue",
            "clear": f"Cleared {what}",
            "complete": f"Checked off {what}",
            "unsuspend": f"Unsuspended {what}",
            "unwatch": f"Unchecked {what}",
            "finish_session": "Cleared checked-off topics",
            "queue_matches": "Queued the search matches",
            "later": f"Saved {what} for later",
            "unlater": f"Took {what} off Later",
            "later_matches": "Saved the search matches for later",
            "fill_from_later": "Filled the queue from Later",
            "import_colors": "Imported Colorful Tags colours",
        }[cmd]

    @property
    def busy(self) -> bool:
        """True while answering a request (changes then travel in the reply)."""
        return self._toasts is not None

    def toast(self, message: str) -> None:
        """Show a toast in the page. The first line is the headline; any
        further lines are details, laid out side by side under it."""
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
        self.booted = True
        open_settings, self.settings_on_boot = self.settings_on_boot, False
        return {
            "openSettings": open_settings,
            "tree": self._tree_memory(view),
            "ready": view.index is not None,
            "side": view.side(),
            "scopes": view.scopes(),
            "scope": view.scope_value(),
            "options": view.options(),
            "colors": {"queued": cfg["queued_color"], "completed": cfg["completed_color"],
                       "later": cfg["later_color"]},
            "skim": skim_link.available(),
            # The index on screen is being rebuilt (the window says "Syncing").
            "syncing": actions.building(),
        }

    def cmd_done_page(self, msg: dict) -> dict:
        view = self.view()
        offset = max(0, int(msg.get("offset") or 0))
        limit = max(1, min(1000, int(msg.get("limit") or 200)))
        return {"rows": view.done_rows(offset, limit), "total": len(view.state.completed())}

    def cmd_undo(self, msg: dict) -> dict:
        label = history.undo(self.host)
        self.toast(f"Undone\n{label}" if label else "Nothing to undo")
        return self.bundle(msg)

    def cmd_redo(self, msg: dict) -> dict:
        label = history.redo(self.host)
        self.toast(f"Redone\n{label}" if label else "Nothing to redo")
        return self.bundle(msg)

    def _tree_memory(self, view: View) -> dict:
        saved = _tree_store().get(TREE_KEY) or {}
        keys = lambda name: [str(k) for k in saved.get(name) or [] if isinstance(k, str)]  # noqa: E731
        opened, closed = keys("open"), keys("closed")
        if view.index is not None:  # forget folders that no longer exist
            names = view.index.names
            opened = [k for k in opened if k in names or k.startswith("__")]
        return {"open": opened, "closed": closed}

    def cmd_save_tree(self, msg: dict) -> dict:
        _tree_store()[TREE_KEY] = {
            "open": [str(k) for k in msg.get("open") or []][:2000],
            "closed": [str(k) for k in msg.get("closed") or []][:200],
        }
        return {}

    def cmd_scopes(self, msg: dict) -> dict:
        view = self.view()
        return {"scopes": view.scopes(), "scope": view.scope_value()}

    def cmd_children(self, msg: dict) -> dict:
        key = str(msg.get("key", ""))
        offset = max(0, int(msg.get("offset") or 0))
        limit = msg.get("limit")
        nodes, total = self.view().children_page(
            key, offset, None if limit is None else max(1, int(limit)))
        return {"key": key, "nodes": nodes, "total": total, "offset": offset}

    def cmd_locate(self, msg: dict) -> dict:
        return self.view().locate(str(msg.get("key", "")).lower())

    def cmd_search(self, msg: dict) -> dict:
        view = self.view()
        if view.index is None:
            return {"nodes": [], "children": {}, "roots": [], "matches": [], "truncated": False}
        return view.search(str(msg.get("query", "")))

    def cmd_details(self, msg: dict) -> dict:
        key = str(msg.get("key", ""))
        # The page asks for these whenever the selection moves, so Skim
        # follows from here (only while it shows Stepwise's cards).
        skim_link.follow(self.host.index, [key])
        return {"details": self.view().details(key)}

    def _skim_args(self, msg: dict) -> tuple[list[str], str | None]:
        keys = self._tags(msg) or [str(msg.get("key") or "")]
        title = msg.get("title")
        return keys, title if isinstance(title, str) and title else None

    def cmd_preview(self, msg: dict) -> dict:
        """p on a topic (or a resource's topics): their cards in Skim."""
        if not skim_link.preview(self.host.index, *self._skim_args(msg)):
            return {"error": "Skim isn't installed."}
        return {}

    def cmd_follow(self, msg: dict) -> dict:
        """The queue panel's cursor moved (the tree's follows via details)."""
        skim_link.follow(self.host.index, *self._skim_args(msg))
        return {}

    def cmd_sync(self, msg: dict) -> dict:
        return self.bundle(msg)

    def cmd_import_info(self, msg: dict) -> dict:
        ud = colorsync.find_user_data()
        if ud is None:
            return {"groups": [], "pins": 0}
        from .counts import short_name

        groups = []
        for color, tags in colorsync.color_groups(ud).items():
            sample = ", ".join(short_name(t.rsplit("::", 1)[-1]) for t in tags[:3])
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

    def cmd_unwatch(self, msg: dict) -> dict:
        actions.unwatch(self._tags(msg))
        return self.bundle(msg)

    def cmd_finish_session(self, msg: dict) -> dict:
        finished = actions.finish_session()
        self.toast(f"Cleared {_plural(len(finished), 'checked-off topic')} from the queue")
        return self.bundle(msg)

    def cmd_browse(self, msg: dict) -> dict:
        """Topics' cards in Anki's browser; with "skim", in Skim instead
        when it's installed (b; B always means Anki's browser)."""
        tags = self._tags(msg)
        if tags and msg.get("skim") and skim_link.preview(self.host.index, *self._skim_args(msg)):
            return {}
        actions.browse(tags or actions.load_state().queued())
        return {}

    def cmd_queue_matches(self, msg: dict) -> dict:
        view = self.view()
        cands, _counts = view.match_candidates(msg.get("matches") or [])
        if cands and not msg.get("truncated"):
            add, _overlap, _after = view.projection(cands)
            actions.queue(cands)
            self.toast(f"Queued {_plural(len(cands), 'topic')}\n+{add:,} cards")
        return self.bundle(msg)

    # --- later ---------------------------------------------------------------

    def cmd_later(self, msg: dict) -> dict:
        tags = self._tags(msg)
        actions.save_later(tags)
        if msg.get("announce", True):
            self.toast(f"Saved {_plural(len(tags), 'topic')} for later")
        return self.bundle(msg)

    def cmd_unlater(self, msg: dict) -> dict:
        actions.unlater(self._tags(msg))
        return self.bundle(msg)

    def cmd_later_matches(self, msg: dict) -> dict:
        cands, _counts = self.view().match_candidates(msg.get("matches") or [], for_later=True)
        if cands and not msg.get("truncated"):
            actions.save_later(cands)
            self.toast(f"Saved {_plural(len(cands), 'topic')} for later")
        return self.bundle(msg)

    def cmd_later_plan(self, msg: dict) -> dict:
        return {"plan": self.view().later_plan()}

    def cmd_fill_from_later(self, msg: dict) -> dict:
        picked, added, skipped = actions.fill_from_later()
        if picked:
            text = f"Queued {_plural(len(picked), 'topic')} from Later\n+{added:,} cards"
            if skipped:
                text += f"\n{len(skipped):,} didn't fit"
            self.toast(text)
        elif skipped:
            self.toast("Nothing from Later fits under your limit right now")
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
                actions.refresh_main_screen(full=True)
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

    # --- settings ----------------------------------------------------------

    def cmd_kit(self, msg: dict) -> dict:
        """What's new, About and the other add-ons (the shared add-on kit)."""
        return kit.command(msg)

    def cmd_settings(self, msg: dict) -> dict:
        return {"settings": self.view().settings()}

    def cmd_root_matches(self, msg: dict) -> dict:
        patterns = [str(p) for p in msg.get("patterns") or []]
        return {"matches": self.view().root_matches(patterns)}

    def cmd_save_settings(self, msg: dict) -> dict:
        """Check and save the Settings dialog, then update whatever depends
        on what changed. Problems come back by field and nothing is saved."""
        old = get_config()
        changes, problems = check_settings(msg.get("settings") or {}, old)
        if problems:
            return {"problems": problems}
        changed = {k for k, v in changes.items() if old.get(k) != v}
        cfg = update_config(**changes) if changed else old
        recount = bool(changed & {"count_mode", "resource_roots"})
        if recount:
            self.host.reload_index(force=True)
        if changed & {"card_limit", "count_mode", "show_on_deck_screen"}:
            actions.refresh_main_screen(full="show_on_deck_screen" in changed)
        colors = {"queued_color", "completed_color", "later_color"}
        if cfg["colorful_tags_sync"] and (changed & colors or "colorful_tags_sync" in changed):
            actions.recolor_all()
        if "shortcut" in changed:
            actions.set_shortcut(cfg["shortcut"])
        if changed:
            actions.notify()
            self.toast("Settings saved")
        view = self.view()
        return {
            "settings": view.settings(),
            "options": view.options(),
            "colors": {"queued": cfg["queued_color"], "completed": cfg["completed_color"],
                       "later": cfg["later_color"]},
            "side": view.side(),
            "scopes": view.scopes(),
            "scope": view.scope_value(),
            "recount": recount,
        }

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
        counts = {QUEUED: 0, COMPLETED: 0, LATER: 0}
        skipped = 0
        for color, tags in colorsync.color_groups(ud).items():
            status = choices.get(color)
            if status not in (QUEUED, COMPLETED, LATER):
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
        parts = [f"{counts[k]:,} {k}" for k in (QUEUED, LATER, COMPLETED) if counts[k]]
        text = "Imported " + (", ".join(parts) if parts else "nothing")
        if skipped:
            text += f"\nSkipped {skipped:,} tags that no longer exist"
        self.toast(text)
        view = self.view()
        return {"scopes": view.scopes(), "scope": view.scope_value(), "options": view.options()}
