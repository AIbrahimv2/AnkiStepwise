# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""Stepwise (was Tag Queue) — queue tagged topics for a study session and track
them to done.

Pick topics by resource (B&B, Bootcamp, Pixorize, ...) from a tag tree, see a
live count of the *unique* suspended cards they add against your session limit
(150 by default), then mark them completed — which also unsuspends their
cards. Open it from Tools -> Stepwise, the deck-screen meter, or by
right-clicking a tag in the Browser sidebar.
"""

from __future__ import annotations

from aqt import gui_hooks, mw
from aqt.qt import QAction, QKeySequence, QTimer, qconnect

from . import actions, browser_menu, history, ui, widget
from .config import ADDON, get_config


def _install() -> None:
    action = QAction("Stepwise", mw)
    shortcut = get_config()["shortcut"]
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    qconnect(action.triggered, ui.open_dialog)
    mw.form.menuTools.addAction(action)
    actions.menu_action = action  # so Settings can change the shortcut live


def _prebuild_index() -> None:
    """Count cards in the background shortly after the profile opens, so
    the Stepwise window and deck-screen meter are instant later."""
    QTimer.singleShot(4000, lambda: mw.col is not None and actions.request_index())


def _on_profile_close() -> None:
    ui.close_dialog()
    actions.reset()
    history.reset()


def _on_config_saved(_cfg) -> None:
    """Config edited by hand (count mode, roots, colours...): recount."""
    actions.mark_index_dirty(membership=True)
    actions.notify()
    ui.refresh_open_dialog()


gui_hooks.main_window_did_init.append(_install)
gui_hooks.operation_did_execute.append(ui.on_operation)
gui_hooks.profile_did_open.append(_prebuild_index)
gui_hooks.profile_will_close.append(_on_profile_close)
gui_hooks.deck_browser_will_render_content.append(widget.on_deck_render)
gui_hooks.webview_did_receive_js_message.append(widget.on_js_message)
gui_hooks.browser_sidebar_will_show_context_menu.append(browser_menu.on_sidebar_menu)
mw.addonManager.setConfigUpdatedAction(ADDON, _on_config_saved)
# Anki's Config button opens the in-window Settings instead of raw JSON.
mw.addonManager.setConfigAction(ADDON, ui.open_settings)
# Serve the built web UI (src/web/) to the Stepwise window.
mw.addonManager.setWebExports(ADDON, r"web/.*\.(js|css|svg|png|woff2?)")
