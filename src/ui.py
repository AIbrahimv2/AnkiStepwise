# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""The Tag Queue window: a dialog hosting the web UI (React, built from
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
        self.setWindowTitle("Tag Queue")
        self.setMinimumSize(860, 560)
        self.resize(1140, 760)
        restoreGeom(self, GEOM_KEY)

        self.index: TagIndex | None = actions.cached_index()
        self.bridge = Bridge(self)
        self._loaded = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.web = AnkiWebView(self, title="tag queue")
        self.web.set_bridge_command(self.bridge.handle, self)
        lay.addWidget(self.web)

        self._index_timer = QTimer(self)
        self._index_timer.setSingleShot(True)
        self._index_timer.setInterval(1500)
        qconnect(self._index_timer.timeout, self.request_index)

    # --- host interface for Bridge ---------------------------------------

    def request_index(self) -> None:
        actions.request_index(self._on_index)

    def reload_index(self, force: bool = False) -> None:
        if force:
            actions.mark_index_dirty()
        self.request_index()

    def _on_index(self, index: TagIndex) -> None:
        changed = self.index is not index
        self.index = index
        if changed:
            self.push({"type": "index"})

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
        if not self._loaded:
            self.load()
        else:
            self.push({"type": "sync"})
            self.request_index()

    def hideEvent(self, ev) -> None:
        actions.unsubscribe(self.on_state_changed)
        saveGeom(self, GEOM_KEY)
        super().hideEvent(ev)

    def cleanup(self) -> None:
        actions.unsubscribe(self.on_state_changed)
        self.web.cleanup()


# --- entry points ------------------------------------------------------------

_dialog: QueueDialog | None = None


def open_dialog() -> None:
    global _dialog
    if _dialog is None:
        _dialog = QueueDialog(mw)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


def close_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.close()
        _dialog.cleanup()
        _dialog.deleteLater()
        _dialog = None


def refresh_open_dialog() -> None:
    """Config was edited by hand: recount and redraw."""
    if _dialog is not None and _dialog.isVisible():
        _dialog.reload_index(force=True)
        _dialog.push({"type": "index"})


def on_operation(changes, handler) -> None:
    actions.on_operation(changes, handler)
    if _dialog is not None and (getattr(changes, "card", False) or getattr(changes, "tag", False)
                                or getattr(changes, "note_text", False)):
        _dialog.schedule_index_refresh()
