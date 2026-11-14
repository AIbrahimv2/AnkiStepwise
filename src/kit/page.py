# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""The kit's own window, and the notice after an update.

The window shows the same Settings, What's new and About dialog the add-ons
with a web page show in it, for add-ons without one (AnkiGlass, AnkiBare)
and for the notice. Its page is built from anki-addon-kit's standalone/
into web/page.js and web/page.css, and inlined, so the add-on needn't
export any files.

After Anki starts, the leading copy of the kit (see family.py) shows one
notice for every add-on updated since you last looked: "Stepwise 1.2.0 and
Skim 1.1.0 were updated. See what's new". It shows once per version.

Anki is imported inside functions, so the rest of the kit runs outside it.
Don't edit a vendored copy (src/kit/ in an add-on): change it in
anki-addon-kit and run its sync.py.
"""

from __future__ import annotations

import json
import os

from . import family

WEB = os.path.join(family.HERE, "web")
GEOM_KEY = "aibrahimv2_kit_page"
NOTICE_DELAY_MS = 2500
NOTICE_SHOW_MS = 14000

_hooked = False
_window = None


def install_hooks() -> None:
    global _hooked
    if _hooked or family._mw() is None:
        return
    try:
        from aqt import gui_hooks
    except Exception:
        return
    gui_hooks.profile_did_open.append(_on_profile_open)
    _hooked = True


def _on_profile_open() -> None:
    reg = family.registry()
    if not family.is_lead() or reg.get("noticed"):
        return
    reg["noticed"] = True
    mw = family._mw()
    mw.progress.single_shot(NOTICE_DELAY_MS, _show_notice, False)


# --- the window ------------------------------------------------------------------


def _asset(name: str) -> str:
    with open(os.path.join(WEB, name), encoding="utf-8") as f:
        return f.read()


def open_page(addon_id: str | None = None, tab: str = "news") -> None:
    """Show the kit's window for an add-on, on a tab: "settings", "news" or
    "about". One window: opening it again switches what it shows."""
    global _window
    from aqt import mw
    from aqt.qt import QApplication

    addon_id = addon_id or family.self_id()
    if _window is None:
        parent = QApplication.activeWindow() or mw
        _window = _make_window(parent)
    _window.show_addon(addon_id, tab)


def _make_window(parent):
    from aqt.qt import QDialog, QVBoxLayout
    from aqt.utils import restoreGeom, saveGeom
    from aqt.webview import AnkiWebView

    class KitWindow(QDialog):
        def __init__(self) -> None:
            super().__init__(parent)
            self.setMinimumSize(420, 420)
            self.resize(620, 680)
            restoreGeom(self, GEOM_KEY)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            self.web = AnkiWebView(self, title="addon kit")
            self.web.set_bridge_command(self._on_bridge, self)
            lay.addWidget(self.web)

        def show_addon(self, addon_id: str, tab: str) -> None:
            e = family.entry(addon_id) or {}
            self.setWindowTitle(e.get("name", "Add-ons"))
            boot = json.dumps({"id": addon_id, "tab": tab})
            # The bundle is inlined; a literal "</script" in it would end the tag.
            js = _asset("page.js").replace("</script", "<\\/script")
            self.web.stdHtml(
                f'<div id="root"></div><script>window.KIT_PAGE = {boot};</script><script>{js}</script>',
                head=f"<style>{_asset('page.css')}</style>",
                context=self,
            )
            self.show()
            self.raise_()
            self.activateWindow()

        def _on_bridge(self, raw: str):
            if not isinstance(raw, str) or not raw.startswith("{"):
                return None
            try:
                msg = json.loads(raw)
            except ValueError:
                return None
            if msg.get("op") == "close":
                self.close()
                return {}
            if msg.get("op") == "open_settings":
                reply = family.command(msg)
                if "error" not in reply:
                    self.close()
                return reply
            return family.command(msg)

        def closeEvent(self, ev) -> None:
            saveGeom(self, GEOM_KEY)
            global _window
            _window = None
            self.web.cleanup()
            self.deleteLater()
            super().closeEvent(ev)

    return KitWindow()


# --- the notice -------------------------------------------------------------------


def _names(addons: list[dict]) -> str:
    parts = [f"{a['name']} {a['version']}" for a in addons]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _show_notice() -> None:
    addons = family.updated_unnoticed()
    if not addons:
        return
    family.mark_notified(addons)
    first = addons[0]["id"]
    text = f"{_names(addons)} {'was' if len(addons) == 1 else 'were'} updated."
    show_notice(text, "See what's new", lambda: open_page(first, "news"))


def show_notice(text: str, action: str, on_click) -> None:
    """A small card at the bottom of the main window, gone on its own after
    a while. Clicking it does `on_click`; × just closes it."""
    from aqt import mw
    from aqt.qt import (
        QColor, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, Qt, QTimer,
    )
    from aqt.theme import theme_manager

    dark = theme_manager.night_mode
    bg, fg, sub, line = (
        ("#3a3a3a", "#fcfcfc", "#cfcfcf", "rgba(255,255,255,0.12)")
        if dark
        else ("#ffffff", "#141414", "#5c5c5c", "rgba(0,0,0,0.10)")
    )
    accent = "#60a5fa" if dark else "#2563eb"

    class Notice(QFrame):
        def mousePressEvent(self, ev) -> None:
            self.close()
            on_click()

    card = Notice(mw)
    card.setObjectName("kitNotice")
    card.setCursor(Qt.CursorShape.PointingHandCursor)
    card.setStyleSheet(
        f"#kitNotice {{ background: {bg}; border: 1px solid {line}; border-radius: 12px; }}"
        f"#kitNotice QLabel {{ color: {fg}; background: transparent; font-size: 13px; }}"
        f"#kitNotice QLabel#kitAction {{ color: {accent}; font-weight: 600; }}"
        f"#kitNotice QPushButton {{ color: {sub}; background: transparent; border: none; font-size: 15px; padding: 0 2px; }}"
        f"#kitNotice QPushButton:hover {{ color: {fg}; }}"
    )
    lay = QHBoxLayout(card)
    lay.setContentsMargins(14, 10, 10, 10)
    lay.setSpacing(10)
    label = QLabel(text)
    act = QLabel(action + " →")
    act.setObjectName("kitAction")
    close = QPushButton("×")
    close.setToolTip("Close")
    close.setCursor(Qt.CursorShape.ArrowCursor)
    close.clicked.connect(card.close)
    lay.addWidget(label)
    lay.addWidget(act)
    lay.addWidget(close)
    shadow = QGraphicsDropShadowEffect(card)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(0, 0, 0, 90 if dark else 45))
    card.setGraphicsEffect(shadow)
    card.adjustSize()

    def place() -> None:
        area = mw.centralWidget() or mw
        pos = area.mapTo(mw, area.rect().bottomLeft())
        x = pos.x() + (area.width() - card.width()) // 2
        y = pos.y() - card.height() - 56
        card.move(max(8, x), max(8, y))

    place()
    card.show()
    card.raise_()
    QTimer.singleShot(NOTICE_SHOW_MS, card.close)
