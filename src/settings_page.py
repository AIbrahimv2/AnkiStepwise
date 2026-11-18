# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Stepwise's Settings, a tab of the add-on kit's window (beside What's new
and About) rather than a dialog over the Stepwise window. Its panel
(web/src/settings-main.tsx, built into web/settings.js) sends its commands
here, open Stepwise window or not; after a save, an open window hears it
("settingsSaved") and updates."""

from __future__ import annotations

import json

from . import actions, ui
from .bridge import Bridge

# The panel's commands: the rest of the bridge is the Stepwise window's.
COMMANDS = {"settings", "root_matches", "save_settings"}


class _Host:
    """What Bridge asks of the Stepwise window, without one: the shared
    index, and the window (if open) to tell about changes."""

    @property
    def index(self):
        return actions.cached_index()

    def request_index(self) -> None:
        window = ui.window()
        if window is not None:
            window.request_index()

    def reload_index(self, force: bool = False) -> None:
        if force:
            actions.mark_index_dirty(membership=True)
        self.request_index()

    def push(self, event: dict) -> None:
        window = ui.window()
        if window is not None:
            window.push(event)


def handle(msg: dict) -> dict:
    cmd = str(msg.get("cmd"))
    if cmd not in COMMANDS:
        return {"error": f"Unknown command: {cmd}"}
    host = _Host()
    reply = Bridge(host).handle(json.dumps(msg))
    if cmd == "save_settings" and "error" not in reply and not reply.get("problems"):
        # The saved toast is the panel's "Saved"; the window gets the rest.
        host.push({"type": "settingsSaved", **{k: v for k, v in reply.items() if k != "toasts"}})
    return reply


# For kit.register: the panel's files, in this add-on's folder.
PAGE = {"script": "web/settings.js", "style": "web/settings.css", "bridge": handle}
