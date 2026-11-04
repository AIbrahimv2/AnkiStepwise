# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Optional bridge to the "Colorful Tags" add-on (AnkiWeb 594329229).

When Colorful Tags is installed, queued and completed tags are coloured in
the browser sidebar automatically, replacing the manual "recolour the tag"
step. We talk to its live in-memory `user_data` object (not just its JSON
file) so the two add-ons never overwrite each other's changes.
"""

from __future__ import annotations

import colorsys
import sys

from .state import COMPLETED, LATER, QUEUED


def find_user_data():
    """Colorful Tags' `user_data` object, or None if it isn't loaded."""
    for name, mod in list(sys.modules.items()):
        if mod is None or not name.endswith(".data"):
            continue
        ud = getattr(mod, "user_data", None)
        if (
            ud is not None
            and hasattr(mod, "UserData")
            and isinstance(getattr(ud, "tags", None), dict)
            and callable(getattr(ud, "save", None))
        ):
            return ud
    return None


def available() -> bool:
    return find_user_data() is not None


def apply(changes: dict, queued_color: str, completed_color: str, ud=None,
          later_color: str | None = None) -> bool:
    """Mirror status changes ({tag: status or None}) as sidebar colours.

    Clearing a status only removes the colour if it is one of ours, so
    colours you assigned by hand for other reasons are left alone.
    """
    ud = ud if ud is not None else find_user_data()
    if ud is None or not changes:
        return False
    ours = {queued_color.lower(), completed_color.lower()}
    if later_color:
        ours.add(later_color.lower())
    for tag, status in changes.items():
        entry = dict(ud.tags.get(tag) or {})
        if status == QUEUED:
            entry["color"] = queued_color
        elif status == COMPLETED:
            entry["color"] = completed_color
        elif status == LATER and later_color:
            entry["color"] = later_color
        elif str(entry.get("color", "")).lower() in ours:
            entry.pop("color", None)
        if entry:
            ud.tags[tag] = entry
        else:
            ud.tags.pop(tag, None)
    ud.save()
    refresh_browser_sidebar()
    return True


def refresh_browser_sidebar() -> None:
    try:
        import aqt

        browser = aqt.DialogManager._dialogs.get("Browser", [None, None])[1]
        if browser is not None:
            browser.sidebar.refresh()
    except Exception:
        pass


# --- one-time import ---------------------------------------------------------


def color_groups(ud) -> dict[str, list[str]]:
    """Coloured tags grouped by colour (lower-case hex), largest group first."""
    groups: dict[str, list[str]] = {}
    for tag, entry in ud.tags.items():
        color = entry.get("color") if isinstance(entry, dict) else None
        if color:
            groups.setdefault(str(color).lower(), []).append(tag)
    return dict(sorted(groups.items(), key=lambda kv: -len(kv[1])))


def pinned_tags(ud) -> list[str]:
    return [t for t, e in ud.tags.items() if isinstance(e, dict) and e.get("pin")]


def looks_green(hex_color: str) -> bool:
    """Best guess at "this colour means done" for the import defaults."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    except Exception:
        return False
    hue, light, sat = colorsys.rgb_to_hls(r, g, b)
    return 75 <= hue * 360 <= 165 and sat > 0.35 and 0.2 < light < 0.85
