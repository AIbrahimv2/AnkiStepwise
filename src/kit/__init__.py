# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""AnkiAddonKit: what AIbrahimv2's Anki add-ons share.

Vendored into each add-on as src/kit/ (and web/src/kit/ for the page) by
the kit's sync.py. Don't edit a vendored copy: change it in
https://github.com/AIbrahimv2/AnkiAddonKit (checked out beside the add-ons
as anki-addon-kit) and sync it.

In the add-on's __init__.py:

    from . import kit
    kit.register("stepwise", open_settings=ui.open_settings)

In its bridge, for a page that shows the kit's dialog:

    def cmd_kit(self, msg):
        return kit.command(msg)

To show the kit's own window (What's new, About, schema settings):

    kit.open_page(tab="about")

For AnkiGlass's glass behind one of the add-on's windows (when it's
installed and its setting is on), while making the window:

    kit.glass(self)  # after its web view, before it shows or loads its page
"""

from __future__ import annotations

from .family import KIT_VERSION, about, command, glass, register, self_id


def open_page(addon_id: str | None = None, tab: str = "news") -> None:
    from .page import open_page as _open

    _open(addon_id or self_id(), tab)


__all__ = ["KIT_VERSION", "about", "command", "glass", "open_page", "register"]
