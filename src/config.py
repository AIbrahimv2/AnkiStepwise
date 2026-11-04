# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Add-on settings. They're edited in the Tag Queue window (⋯ → Settings…),
which Anki's own Config button for the add-on also opens."""

from __future__ import annotations

import re

from aqt import mw
from aqt.qt import QKeySequence

ADDON = __name__.split(".")[0]

DEFAULTS: dict = {
    "card_limit": 150,
    "count_mode": "new",
    "unsuspend_on_complete": True,
    "resource_roots": ["#AK_Step*"],
    "pinned_resources": [],
    "hide_completed": False,
    "search_scope": "all",
    "show_on_deck_screen": True,
    "colorful_tags_sync": True,
    "queued_color": "#ff9300",
    "completed_color": "#00f900",
    "later_color": "#af52de",
    "shortcut": "Ctrl+Alt+Q",
    "import_offered": False,
    "config_version": 3,
}


COUNT_MODES = ("new", "suspended", "all")
LIMIT_RANGE = (1, 5000)
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def check_settings(values: dict, cfg: dict) -> tuple[dict, dict]:
    """Validate settings sent from the Settings dialog. Returns (config
    changes, problems by field); only fields that were sent are checked."""
    changes: dict = {}
    problems: dict = {}
    if "cardLimit" in values:
        try:
            limit = int(values["cardLimit"])
            if not LIMIT_RANGE[0] <= limit <= LIMIT_RANGE[1]:
                raise ValueError
            changes["card_limit"] = limit
        except (TypeError, ValueError):
            problems["cardLimit"] = f"Enter a number from {LIMIT_RANGE[0]} to {LIMIT_RANGE[1]:,}."
    if "countMode" in values:
        if values["countMode"] in COUNT_MODES:
            changes["count_mode"] = values["countMode"]
        else:
            problems["countMode"] = "Pick one of the options."
    for key, name in (("unsuspendOnComplete", "unsuspend_on_complete"),
                      ("showOnDeck", "show_on_deck_screen"), ("colorSync", "colorful_tags_sync")):
        if key in values:
            changes[name] = bool(values[key])
    if "resourceRoots" in values:
        roots, seen = [], set()
        for p in values["resourceRoots"] or []:
            p = str(p).strip()
            if p and p.lower() not in seen:
                seen.add(p.lower())
                roots.append(p)
        changes["resource_roots"] = roots
    if "pinned" in values:
        changes["pinned_resources"] = [str(t) for t in values["pinned"] or [] if str(t).strip()]
    for key, name in (("queued", "queued_color"), ("completed", "completed_color"),
                      ("later", "later_color")):
        color = (values.get("colors") or {}).get(key)
        if color is None:
            continue
        if isinstance(color, str) and _HEX.match(color):
            changes[name] = color.lower()
        else:
            problems["colors." + key] = "Use a colour like #ff9300."
    if "shortcut" in values:
        text = str(values["shortcut"] or "").strip()
        # Qt parses anything; unknown keys come back as "" when written out.
        seq = QKeySequence(text)
        normal = seq.toString(QKeySequence.SequenceFormat.PortableText)
        if text and (not normal or seq.count() != 1):
            problems["shortcut"] = "Anki can't use that shortcut."
        else:
            changes["shortcut"] = normal if text else ""
    return changes, problems


def _migrate(cfg: dict) -> dict:
    """v3: the session meter counts new cards again (still suspended plus
    unsuspended but not yet studied), so checking a watched topic doesn't
    shrink it. v2 had switched it to "suspended" automatically; undo that
    once. A count_mode chosen afterwards sticks."""
    version = cfg.get("config_version", 1)
    if version < 3:
        if version == 2 and cfg.get("count_mode") == "suspended":
            cfg["count_mode"] = "new"
        cfg["config_version"] = 3
        mw.addonManager.writeConfig(ADDON, cfg)
    return cfg


def get_config() -> dict:
    cfg = _migrate(dict(mw.addonManager.getConfig(ADDON) or {}))
    for key, value in DEFAULTS.items():
        if not isinstance(cfg.get(key), type(value)):
            cfg[key] = list(value) if isinstance(value, list) else value
    cfg["card_limit"] = max(1, cfg["card_limit"])
    return cfg


def save_config(cfg: dict) -> None:
    mw.addonManager.writeConfig(ADDON, cfg)


def update_config(**changes) -> dict:
    cfg = get_config()
    cfg.update(changes)
    save_config(cfg)
    return cfg
