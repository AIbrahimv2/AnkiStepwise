# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""The Stepwise window: a dialog hosting the web UI (React, built from
web/ into src/web/) in an AnkiWebView, wired to `Bridge` for data and
actions."""

from __future__ import annotations

import json
import os

from aqt import mw
from aqt.qt import QDialog, QTimer, QVBoxLayout, qconnect
from aqt.utils import restoreGeom, saveGeom
from aqt.webview import AnkiWebView

from . import actions
from .bridge import Bridge
from .config import ADDON
from .counts import TagIndex

GEOM_KEY = "tag_queue_web"
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def asset_url(name: str) -> str:
    """URL for a built asset, versioned by mtime so a rebuild is never
    served from cache."""
    try:
        v = int(os.path.getmtime(os.path.join(WEB_DIR, name)))
    except OSError:
        v = 0
    return f"/_addons/{ADDON}/web/{name}?v={v}"


class QueueDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Stepwise")
        # The page switches to one panel at a time below 760px wide.
        self.setMinimumSize(440, 560)
        self.resize(1140, 760)
        restoreGeom(self, GEOM_KEY)

        self.bridge = Bridge(self)
        self._loaded = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.web = AnkiWebView(self, title="stepwise")
        self.web.set_bridge_command(self.bridge.handle, self)
        lay.addWidget(self.web)

        self._index_timer = QTimer(self)
        self._index_timer.setSingleShot(True)
        self._index_timer.setInterval(1500)
        qconnect(self._index_timer.timeout, self.request_index)
        # For the window's whole life, hidden or not: a window made ahead of
        # time (prewarm) must hear about rebuilds before it's first shown.
        actions.on_index_built(self._on_index_built)
        actions.on_building(self._on_building)

    # --- host interface for Bridge ---------------------------------------

    @property
    def index(self) -> TagIndex | None:
        """The last built index, even if a rebuild is under way: the window
        opens instantly and refreshes its numbers when the rebuild lands."""
        return actions.cached_index()

    def request_index(self) -> None:
        """Only while the window shows: a window made ahead of time doesn't
        start a rebuild (that waits until you open it, with "Syncing")."""
        if self.isVisible():
            actions.request_index()

    def reload_index(self, force: bool = False) -> None:
        if force:
            actions.mark_index_dirty(membership=True)
        self.request_index()

    def _on_index_built(self, _index: TagIndex) -> None:
        self.push({"type": "index"})

    def _on_building(self, on: bool) -> None:
        self.push({"type": "syncing", "on": on})

    def open_settings(self) -> None:
        """Show the Settings dialog in the page (now, or as soon as it loads)."""
        if self.bridge.booted:
            self.push({"type": "settings"})
        else:
            self.bridge.settings_on_boot = True

    def push(self, event: dict) -> None:
        if self._loaded:
            self.web.eval(f"window.tagQueue && window.tagQueue.push({json.dumps(event)});")

    def show_toast(self, message: str) -> None:
        self.bridge.toast(message)

    # --- lifecycle -------------------------------------------------------

    def load(self) -> None:
        self.web.stdHtml(
            '<div id="root"></div>',
            css=[asset_url("app.css")],
            js=[asset_url("app.js")],
            context=self,
        )
        self._loaded = True

    def on_state_changed(self) -> None:
        """Queue changed somewhere else (browser sidebar, deck screen...)."""
        if not self.bridge.busy:
            self.push({"type": "sync"})

    def schedule_index_refresh(self) -> None:
        if self.isVisible():
            self._index_timer.start()

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        actions.subscribe(self.on_state_changed)
        actions.set_announcer(self.show_toast)
        if not self._loaded:
            self.load()
        else:
            self.push({"type": "sync"})
            self.request_index()
        # Keyboard focus to the page, so the tree's keys work without a
        # click first (the page then focuses the tree itself).
        self.web.setFocus()

    def hideEvent(self, ev) -> None:
        actions.unsubscribe(self.on_state_changed)
        actions.set_announcer(None)
        saveGeom(self, GEOM_KEY)
        super().hideEvent(ev)

    def cleanup(self) -> None:
        actions.unsubscribe(self.on_state_changed)
        actions.off_index_built(self._on_index_built)
        actions.off_building(self._on_building)
        self.web.cleanup()


# --- entry points ------------------------------------------------------------

_dialog: QueueDialog | None = None


def prewarm() -> None:
    """Make the window and load its page, hidden, once startup has settled,
    so the first open is as quick as the rest. Counts nothing: the page
    shows the index saved last session until you open the window."""
    global _dialog
    if _dialog is None and mw.col is not None:
        _dialog = QueueDialog(mw)
        _dialog.load()


def open_dialog() -> None:
    global _dialog
    if _dialog is None:
        _dialog = QueueDialog(mw)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def open_settings() -> None:
    """Anki's Config button for the add-on: open the window on Settings
    rather than Anki's JSON editor."""
    open_dialog()
    if _dialog is not None:
        _dialog.open_settings()


def close_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.close()
        _dialog.cleanup()
        _dialog.deleteLater()
        _dialog = None


def refresh_open_dialog() -> None:
    """Config was edited by hand: recount (the rebuild pushes a redraw)."""
    if _dialog is not None and _dialog.isVisible():
        _dialog.reload_index(force=True)


def on_operation(changes, handler) -> None:
    actions.on_operation(changes, handler)
    if _dialog is not None and (getattr(changes, "card", False) or getattr(changes, "tag", False)
                                or getattr(changes, "note_text", False)):
        _dialog.schedule_index_refresh()
