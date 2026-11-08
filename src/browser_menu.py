# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Right-click a tag in the Browser sidebar -> Stepwise -> Add to queue /
Mark completed. Works on several selected tags at once."""

from __future__ import annotations

from . import actions
from .state import COMPLETED, LATER, QUEUED


def _selected_tags(sidebar, item) -> list[str]:
    try:
        tags = list(sidebar._selected_tags())
    except Exception:
        tags = []
    if item.full_name not in tags:
        tags = [item.full_name]
    return tags


def on_sidebar_menu(sidebar, menu, item, index) -> None:
    from aqt.browser import SidebarItemType

    if getattr(item, "item_type", None) != SidebarItemType.TAG:
        return
    tags = _selected_tags(sidebar, item)
    state = actions.load_state()
    statuses = {state.status(t) for t in tags}
    parent = getattr(sidebar, "browser", None)

    menu.addSeparator()
    sub = menu.addMenu("Stepwise")
    if statuses != {QUEUED}:
        sub.addAction("Add to queue", lambda: actions.queue(tags))
    if QUEUED in statuses:
        sub.addAction("Remove from queue", lambda: actions.unqueue(tags))
    if statuses != {LATER}:
        sub.addAction("Save for later", lambda: actions.save_later(tags))
    if LATER in statuses:
        sub.addAction("Remove from Later", lambda: actions.unlater(tags))
    if statuses != {COMPLETED}:
        sub.addAction("Mark completed", lambda: actions.complete(tags, parent))
    if statuses - {None}:
        sub.addAction("Clear status", lambda: actions.clear(tags))
    sub.addSeparator()

    def open_window() -> None:
        from .ui import open_dialog

        open_dialog()

    sub.addAction("Open Stepwise…", open_window)
