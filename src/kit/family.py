# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""What AIbrahimv2's add-ons know about each other.

Every add-on carries its own copy of this kit (src/kit/), so they can't
import each other. Instead each copy registers its add-on in one registry
kept on Anki's main window (`mw.aibrahimv2_addons_v1`), made of plain
values and functions. Any copy can then answer for all of them: which are
installed, their versions and changes, whether AnkiWeb has an update, and
which updates you haven't looked at yet. Copies may be from different kit
versions: the newest one leads (it shows the one notice after updates).

The version you last saw is kept in each add-on's own meta.json, under
"kit", which Anki keeps when it updates an add-on.

Outside Anki (tests, dev servers) the registry and meta.json live in this
module, and AnkiWeb is never asked.

Don't edit a vendored copy (src/kit/ in an add-on): change it in
anki-addon-kit and run its sync.py.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable

from . import changelog

# Bump PROTOCOL when the registry's shape changes (copies on different
# protocols then keep apart), and KIT_VERSION whenever the kit changes (the
# newest copy leads).
PROTOCOL = 1
KIT_VERSION = 1
REGISTRY = f"aibrahimv2_addons_v{PROTOCOL}"

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_PATH = os.path.dirname(HERE)  # addons21/<folder>, links not followed
ADDON = __name__.split(".")[0]  # the add-on's folder (and module) name

_self: dict[str, str | None] = {"id": None}
_outside: dict[str, Any] = {"registry": None, "meta": {}}  # outside Anki


def _mw():
    try:
        from aqt import mw
    except Exception:
        return None
    return mw


def platform() -> str:
    if sys.platform == "darwin":
        return "mac"
    return "win" if sys.platform.startswith("win") else "lin"


# --- the registry ----------------------------------------------------------------


def registry() -> dict:
    mw = _mw()
    reg = getattr(mw, REGISTRY, None) if mw is not None else _outside["registry"]
    if not isinstance(reg, dict):
        reg = {"members": {}, "catalogs": [], "lead": None, "noticed": False}
        if mw is not None:
            setattr(mw, REGISTRY, reg)
        else:
            _outside["registry"] = reg
    return reg


def register(
    addon_id: str,
    *,
    open_settings: Callable[[], None] | None = None,
    schema: list[dict] | None = None,
    note: str | None = None,
) -> None:
    """Call once from the add-on's __init__.py. `addon_id` is its id in
    catalog.json. Give `open_settings` if it has settings in its own window,
    or `schema` for settings the kit's page shows (see settings.py); `note`
    is shown under them ("Changes apply after Anki restarts").

    Never raises: a problem in the kit mustn't stop the add-on loading."""
    try:
        _register(addon_id, open_settings, schema, note)
    except Exception:
        import traceback

        traceback.print_exc()


def _register(addon_id, open_settings, schema, note) -> None:
    from . import page  # Anki-only parts, imported lazily

    _self["id"] = addon_id
    reg = registry()
    reg["members"][addon_id] = {
        "id": addon_id,
        "dir": ADDON,
        "path": ADDON_PATH,
        "kit": KIT_VERSION,
        "open_settings": open_settings,
        "schema": schema,
        "note": note,
        "open_page": page.open_page,
    }
    own = _own_catalog()
    if own:
        reg["catalogs"].append(own)
    lead = reg.get("lead")
    if not lead or KIT_VERSION > lead.get("kit", 0):
        reg["lead"] = {"kit": KIT_VERSION, "dir": ADDON}
    _first_run(addon_id)
    page.install_hooks()


def self_id() -> str | None:
    return _self["id"]


def is_lead() -> bool:
    lead = registry().get("lead") or {}
    return lead.get("dir") == ADDON


def _own_catalog() -> dict | None:
    # Beside this file in an add-on (sync.py copies it); at the top of the
    # kit's own repo.
    for path in (os.path.join(HERE, "catalog.json"), os.path.join(os.path.dirname(HERE), "catalog.json")):
        try:
            with open(path, encoding="utf-8") as f:
                cat = json.load(f)
        except (OSError, ValueError):
            continue
        if isinstance(cat, dict) and isinstance(cat.get("addons"), list):
            return cat
    return None


def catalog() -> dict:
    """The newest catalog any installed copy of the kit brought, so an add-on
    released after this one still shows up once anything updates."""
    cats = [c for c in registry()["catalogs"] if isinstance(c, dict)]
    own = _own_catalog()
    if own:
        cats.append(own)
    if not cats:
        return {"author": {"name": "AIbrahimv2", "github": ""}, "addons": []}
    return max(cats, key=lambda c: (str(c.get("updated", "")), len(c.get("addons", []))))


def entry(addon_id: str) -> dict | None:
    return next((a for a in catalog()["addons"] if a.get("id") == addon_id), None)


# --- what's installed --------------------------------------------------------------


def _metas() -> list:
    mw = _mw()
    if mw is None or getattr(mw, "addonManager", None) is None:
        return []
    try:
        return list(mw.addonManager.all_addon_meta())
    except Exception:
        return []


def _install_of(e: dict, metas: list, members: dict):
    """The installed copy of a catalog entry: the one running, else an
    enabled one, else any (so a turned-off AnkiWeb copy beside a linked
    repo doesn't hide the running one)."""
    names = {str(e["ankiweb"])} if e.get("ankiweb") else set()
    names |= set(e.get("dirs", []))
    m = members.get(e["id"])
    if m:
        names.add(m["dir"])
    found = [x for x in metas if x.dir_name in names]
    if m:
        for x in found:
            if x.dir_name == m["dir"]:
                return x
    return next((x for x in found if x.enabled), found[0] if found else None)


def _folder(dir_name: str) -> str | None:
    mw = _mw()
    if mw is None:
        return None
    try:
        return mw.addonManager.addonsFolder(dir_name)
    except Exception:
        return None


def changelog_path(addon_path: str | None) -> str | None:
    """CHANGELOG.md in the package, or beside src/ for a linked repo."""
    if not addon_path:
        return None
    for base in (addon_path, os.path.dirname(os.path.realpath(addon_path))):
        p = os.path.join(base, "CHANGELOG.md")
        if os.path.isfile(p):
            return p
    return None


def releases(addon_path: str | None) -> list[dict]:
    p = changelog_path(addon_path)
    if not p:
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return changelog.parse(f.read())
    except OSError:
        return []


# --- what you've seen (meta.json) ----------------------------------------------------


def kit_state(dir_name: str) -> dict:
    mw = _mw()
    mgr = getattr(mw, "addonManager", None) if mw is not None else None
    if mgr is None or not hasattr(mgr, "addonMeta"):
        return dict(_outside["meta"].get(dir_name, {}))
    try:
        return dict(mw.addonManager.addonMeta(dir_name).get("kit") or {})
    except Exception:
        return {}


def set_kit_state(dir_name: str, **values: Any) -> None:
    mw = _mw()
    mgr = getattr(mw, "addonManager", None) if mw is not None else None
    if mgr is None or not hasattr(mgr, "addonMeta"):
        _outside["meta"].setdefault(dir_name, {}).update(values)
        return
    meta = mgr.addonMeta(dir_name)
    state = dict(meta.get("kit") or {})
    state.update(values)
    meta["kit"] = state
    mgr.writeAddonMeta(dir_name, meta)


def _first_run(addon_id: str) -> None:
    """The first time the kit runs in an add-on, take today's version as
    seen, so a fresh install doesn't announce itself as an update."""
    state = kit_state(ADDON)
    if "seen" in state:
        return
    version = changelog.latest_version(releases(ADDON_PATH))
    set_kit_state(ADDON, seen=version, notified=version)


def mark_seen(addon_id: str) -> None:
    a = _find(addon_id)
    if a and a["dir"] and a["version"]:
        set_kit_state(a["dir"], seen=a["version"], notified=a["version"])


# --- the page's view of it all ---------------------------------------------------------


def _find(addon_id: str) -> dict | None:
    return next((a for a in _addons(with_changes=False) if a["id"] == addon_id), None)


def _addons(with_changes: bool = True) -> list[dict]:
    reg = registry()
    members = reg["members"]
    metas = _metas()
    here = platform()
    out = []
    for e in catalog()["addons"]:
        m = members.get(e["id"])
        meta = _install_of(e, metas, members)
        installed = m is not None or meta is not None
        dir_name = m["dir"] if m else (meta.dir_name if meta else None)
        path = m["path"] if m else (_folder(meta.dir_name) if meta else None)
        rel = releases(path) if installed else []
        version = changelog.latest_version(rel)
        seen = kit_state(dir_name).get("seen") if dir_name else None
        settings = None
        if m and m.get("schema"):
            settings = "page"
        elif m and m.get("open_settings"):
            settings = "window"
        out.append({
            "id": e["id"],
            "name": e.get("name", e["id"]),
            "emoji": e.get("emoji", ""),
            "tagline": e.get("tagline", ""),
            "about": e.get("about", ""),
            "ankiweb": e.get("ankiweb"),
            "github": e.get("github", ""),
            "installed": installed,
            "enabled": m is not None or bool(meta and meta.enabled),
            "running": m is not None,
            "dev": bool(dir_name) and not str(dir_name).isdigit(),
            "supported": here in e.get("platforms", ["mac", "win", "lin"]),
            "version": version,
            "unseen": bool(installed and seen and changelog.newer(version, seen)),
            "settings": settings,
            "dir": dir_name,
            "changes": [
                {**r, "isNew": bool(seen and changelog.newer(r["version"], seen))} for r in rel
            ] if with_changes else [],
        })
    return out


def about(addon_id: str | None = None) -> dict:
    cat = catalog()
    addons = _addons()
    for a in addons:
        a.pop("dir", None)
    return {"self": addon_id or self_id(), "author": cat.get("author", {}), "addons": addons}


def updated_unnoticed() -> list[dict]:
    """Running add-ons updated since you last saw (or were told about) them."""
    out = []
    for a in _addons(with_changes=False):
        if not (a["running"] and a["dir"] and a["version"]):
            continue
        state = kit_state(a["dir"])
        seen, notified = state.get("seen"), state.get("notified")
        if seen and changelog.newer(a["version"], seen) and changelog.newer(a["version"], notified or seen):
            out.append(a)
    return out


def mark_notified(addons: list[dict]) -> None:
    for a in addons:
        set_kit_state(a["dir"], notified=a["version"])


# --- AnkiWeb -------------------------------------------------------------------------

_updates: dict[str, Any] = {"state": "idle", "at": 0.0, "result": {}}
UPDATES_FRESH = 600  # seconds


def updates() -> dict:
    """{done, updates: {id: available | current | dev | unknown}} for the
    installed add-ons. Asks AnkiWeb in the background, through Anki's own
    update check, at most every ten minutes; the page asks again until done."""
    if _updates["state"] == "done" and time.time() - _updates["at"] < UPDATES_FRESH:
        return {"done": True, "updates": _updates["result"]}
    if _updates["state"] == "running":
        return {"done": False, "updates": {}}

    result: dict[str, str] = {}
    ask: dict[int, str] = {}
    for a in _addons(with_changes=False):
        if not a["installed"]:
            continue
        if a["dev"]:
            result[a["id"]] = "dev"
        elif a["dir"]:
            ask[int(a["dir"])] = a["id"]
        else:
            result[a["id"]] = "unknown"

    mw = _mw()
    if not ask or mw is None or getattr(mw, "taskman", None) is None:
        for cid in ask.values():
            result[cid] = "unknown"
        _updates.update(state="done", at=time.time(), result=result)
        return {"done": True, "updates": result}

    def check():
        from anki.utils import int_version

        return mw.backend.get_addon_info(client_version=int_version(), addon_ids=list(ask))

    def done(future) -> None:
        final = dict(result)
        try:
            need = {item.id for item in mw.addonManager.get_updated_addons(future.result())}
            for aid, cid in ask.items():
                final[cid] = "available" if aid in need else "current"
        except Exception:
            for cid in ask.values():
                final[cid] = "unknown"
        _updates.update(state="done", at=time.time(), result=final)

    _updates["state"] = "running"
    mw.taskman.run_in_background(check, done)
    return {"done": False, "updates": {}}


def install(addon_id: str) -> None:
    """Install or update an add-on from AnkiWeb with Anki's own installer,
    which says when it's done (and asks for a restart)."""
    e = entry(addon_id)
    if not e or not e.get("ankiweb"):
        raise ValueError("That add-on isn't on AnkiWeb.")
    mw = _mw()
    if mw is None:
        raise ValueError("Installing works inside Anki only.")
    from aqt.addons import install_or_update_addon, show_log_to_user
    from aqt.utils import tooltip

    def on_done(log) -> None:
        _updates["state"] = "idle"  # look again next time
        if log:
            show_log_to_user(mw, log)
        else:
            tooltip(f"{e.get('name')} is up to date.")

    install_or_update_addon(mw, mw.addonManager, int(e["ankiweb"]), on_done)


def open_url(url: str) -> None:
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise ValueError("Only web links open.")
    mw = _mw()
    if mw is None:
        print("open", url)
        return
    from aqt.utils import openLink

    openLink(url)


# --- the page's commands ------------------------------------------------------------------


def command(msg: dict) -> dict:
    """The add-on's bridge hands `{cmd: "kit", op, ...}` here. Never raises:
    a problem comes back as {"error": ...}, like the add-ons' own replies."""
    try:
        return _command(msg)
    except Exception as exc:
        return {"error": str(exc) or type(exc).__name__}


def _command(msg: dict) -> dict:
    from . import page, settings

    op = msg.get("op")
    addon_id = str(msg.get("id") or self_id() or "")
    if op == "about":
        return {"about": about(addon_id)}
    if op == "seen":
        mark_seen(addon_id)
        return {}
    if op == "updates":
        return updates()
    if op == "install":
        install(addon_id)
        return {"started": True}
    if op == "open":
        open_url(msg.get("url", ""))
        return {}
    if op == "page":
        page.open_page(addon_id, str(msg.get("tab") or "news"))
        return {}
    if op == "open_settings":
        member = registry()["members"].get(addon_id) or {}
        if not member.get("open_settings"):
            raise ValueError("Its settings aren't available.")
        member["open_settings"]()
        return {}
    if op == "settings":
        return settings.load(addon_id)
    if op == "save_settings":
        return settings.save(addon_id, msg.get("values") or {})
    raise ValueError(f"Unknown kit command: {op}")
