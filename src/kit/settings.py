# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Settings the kit's page shows for an add-on without a page of its own
(AnkiGlass, say), described by a schema and stored in its Anki config.

A schema is a list of sections:

    [{"section": "Screens", "fields": [
        {"key": "glass_screens", "type": "multi", "label": "Glass on",
         "hint": "...", "options": [{"value": "review", "label": "Review"}]},
        {"key": "glass_card", "type": "switch", "label": "...", "hint": "..."},
        {"key": "tint_dark", "type": "text", "label": "...", "mono": True},
        {"key": "side", "type": "choice", "label": "...", "options": [...]},
    ]}]

Plain Python: Anki is only asked for the config, so tests can run it.
Don't edit a vendored copy (src/kit/ in an add-on): change it in
anki-addon-kit and run its sync.py.
"""

from __future__ import annotations

from typing import Any

from . import family

MAX_TEXT = 200
_outside: dict[str, dict] = {}  # config outside Anki
_outside_defaults: dict[str, dict] = {}


def _member(addon_id: str) -> dict:
    m = family.registry()["members"].get(addon_id)
    if not m or not m.get("schema"):
        raise ValueError("This add-on has no settings here.")
    return m


def _config(dir_name: str) -> tuple[dict, dict]:
    """(config, defaults)."""
    mw = family._mw()
    if mw is None or getattr(mw, "addonManager", None) is None:
        cfg = _outside.setdefault(dir_name, {})
        return dict(cfg), dict(_outside_defaults.get(dir_name, {}))
    mgr = mw.addonManager
    return dict(mgr.getConfig(dir_name) or {}), dict(mgr.addonConfigDefaults(dir_name) or {})


def _fields(schema: list[dict]):
    for section in schema:
        yield from section.get("fields", [])


def load(addon_id: str) -> dict:
    m = _member(addon_id)
    cfg, defaults = _config(m["dir"])
    keys = [f["key"] for f in _fields(m["schema"])]
    return {
        "schema": m["schema"],
        "values": {k: cfg.get(k, defaults.get(k)) for k in keys},
        "defaults": {k: defaults.get(k) for k in keys},
        "note": m.get("note"),
    }


def check(schema: list[dict], values: dict) -> tuple[dict, dict[str, str]]:
    """(clean values, problems by key)."""
    clean: dict[str, Any] = {}
    problems: dict[str, str] = {}
    for f in _fields(schema):
        key, kind = f["key"], f.get("type")
        if key not in values:
            continue
        v = values[key]
        allowed = [o["value"] for o in f.get("options", [])]
        if kind == "switch":
            clean[key] = bool(v)
        elif kind == "multi":
            if not isinstance(v, list):
                problems[key] = "Pick from the list."
                continue
            clean[key] = [o for o in allowed if o in v]  # in the schema's order
        elif kind == "choice":
            if v not in allowed:
                problems[key] = "Pick one of the choices."
                continue
            clean[key] = v
        elif kind == "text":
            text = str(v).strip()
            if len(text) > MAX_TEXT:
                problems[key] = f"Keep it under {MAX_TEXT} characters."
            elif not text and not f.get("optional"):
                problems[key] = "This can't be empty."
            else:
                clean[key] = text
    return clean, problems


def save(addon_id: str, values: dict) -> dict:
    m = _member(addon_id)
    clean, problems = check(m["schema"], values)
    if problems:
        return {"problems": problems}
    cfg, _defaults = _config(m["dir"])
    cfg.update(clean)
    mw = family._mw()
    if mw is None or getattr(mw, "addonManager", None) is None:
        _outside[m["dir"]] = cfg
    else:
        mw.addonManager.writeConfig(m["dir"], cfg)
    return {"saved": True, "note": m.get("note")}
