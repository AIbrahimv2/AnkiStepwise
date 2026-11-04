# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Add-on settings (Tools -> Add-ons -> Tag Queue -> Config)."""

from __future__ import annotations

from aqt import mw

ADDON = __name__.split(".")[0]

DEFAULTS: dict = {
    "card_limit": 150,
    "count_mode": "suspended",
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
    "config_version": 2,
}


def _migrate(cfg: dict) -> dict:
    """v2: the limit counts suspended cards. "new" was only ever the old
    default, so move it over once; choosing "new" again afterwards sticks."""
    if cfg.get("config_version", 1) < 2:
        if cfg.get("count_mode") == "new":
            cfg["count_mode"] = "suspended"
        cfg["config_version"] = 2
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
