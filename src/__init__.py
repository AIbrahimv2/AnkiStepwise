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

from . import actions, browser_menu, history, kit, settings_page, ui, widget
from .config import ADDON, get_config


def _install() -> None:
    action = QAction("Stepwise", mw)
    shortcut = get_config()["shortcut"]
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
    qconnect(action.triggered, ui.open_dialog)
    mw.form.menuTools.addAction(action)
    actions.menu_action = action  # so Settings can change the shortcut live


# The window is made (hidden) once Anki's own startup has settled, and a
# moment later the saved index is checked against the collection.
PREWARM_MS = 8000
SETTLE_MS = 9500


def _on_profile_open() -> None:
    """Read the tag index saved last session (about 40 ms) and count
    nothing: startup isn't slowed. The saved index is shown as it is. Once
    startup has settled it's checked against the collection (about 35 ms):
    if nothing changed since (a restart the same day), it's used as it is;
    if something did, it's rebuilt in the background, on the deck screen,
    so opening Stepwise finds it current. Only the very first time, with
    nothing saved, is it counted shortly after startup."""
    if not actions.load_saved_index():
        QTimer.singleShot(4000, lambda: mw.col is not None and actions.request_index())
    QTimer.singleShot(PREWARM_MS, ui.prewarm)
    QTimer.singleShot(SETTLE_MS, lambda: mw.col is not None and actions.settle_saved_index())


def _on_profile_close() -> None:
    ui.close_dialog()
    actions.save_index()  # for next session's startup
    actions.reset()
    history.reset()


def _on_config_saved(_cfg) -> None:
    """Config edited by hand (count mode, roots, colours...): recount."""
    actions.mark_index_dirty(membership=True)
    actions.notify()
    ui.refresh_open_dialog()


gui_hooks.main_window_did_init.append(_install)
gui_hooks.operation_did_execute.append(ui.on_operation)
gui_hooks.profile_did_open.append(_on_profile_open)
gui_hooks.profile_will_close.append(_on_profile_close)
gui_hooks.deck_browser_will_render_content.append(widget.on_deck_render)
gui_hooks.webview_did_receive_js_message.append(widget.on_js_message)
gui_hooks.browser_sidebar_will_show_context_menu.append(browser_menu.on_sidebar_menu)
mw.addonManager.setConfigUpdatedAction(ADDON, _on_config_saved)
# Anki's Config button opens Settings (in the kit's window) instead of raw JSON.
mw.addonManager.setConfigAction(ADDON, ui.open_settings)
# Serve the built web UI (src/web/) to the Stepwise window.
mw.addonManager.setWebExports(ADDON, r"web/.*\.(js|css|svg|png|woff2?)")
# The add-on kit shared with AIbrahimv2's other add-ons (src/kit/): one window
# for Settings, What's new and About, and one notice after updates.
kit.register("stepwise", open_settings=ui.open_settings, settings_page=settings_page.PAGE)
