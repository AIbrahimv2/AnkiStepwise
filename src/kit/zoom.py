# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""How big an add-on's window draws. Anki draws its web views at 100% on a
Mac whatever its own interface size, so an add-on window gets the keys a
browser has: Cmd+= and Cmd+- (Ctrl on Windows and Linux) zoom its page a
step at a time, and Cmd+0 puts it back at 100%. Everything on the page
grows together (text, rows, logos, a card in a frame), through Qt's page
zoom, so the page's own measurements stay in CSS pixels.

The add-on keeps the size (`read` and `write`, its config), so the window
opens at it next time, and its Settings can set it too:

    apply = kit.zoom(self, self.web, read=lambda: get_config()["zoom_percent"],
                     write=lambda p: update_config(zoom_percent=p))
    ...
    apply(cfg["zoom_percent"])  # after Settings saves a new size
"""

from __future__ import annotations

from collections.abc import Callable

# The sizes the keys step through, as browsers have them (percent).
STEPS = (50, 67, 75, 80, 90, 100, 110, 125, 150, 175, 200)
MIN, MAX = STEPS[0], STEPS[-1]


def clamp(percent) -> int:
    """A size the window can take: a whole percent from MIN to MAX."""
    try:
        return max(MIN, min(MAX, int(round(float(percent)))))
    except (TypeError, ValueError):
        return 100


def step(percent: int, by: int) -> int:
    """The next size up (by > 0) or down from `percent`, which needn't be
    one of the steps (Settings takes any whole percent)."""
    now = clamp(percent)
    if by > 0:
        return next((s for s in STEPS if s > now), MAX)
    return next((s for s in reversed(STEPS) if s < now), MIN)


def zoom(window, web, read: Callable[[], int], write: Callable[[int], None]) -> Callable[[int], None]:
    """Draw `web` (in `window`) at the saved size, now and after every load,
    and bind the keys on `window`. Returns `apply(percent)`, to show a size
    Settings has saved."""
    from aqt.qt import QKeySequence, QShortcut, Qt, qconnect  # Anki's, imported here so tests run without it
    from aqt.utils import tooltip

    def apply(percent: int) -> None:
        web.setZoomFactor(clamp(percent) / 100)

    def change(to: int) -> None:
        to = clamp(to)
        if to != clamp(read()):
            write(to)
        apply(to)
        tooltip(f"{to}%", period=900, parent=window)

    apply(read())
    qconnect(web.loadFinished, lambda _ok: apply(read()))
    for keys, by in (("Ctrl+=", 1), ("Ctrl++", 1), ("Ctrl+-", -1), ("Ctrl+0", 0)):
        shortcut = QShortcut(QKeySequence(keys), window)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        act = (lambda by=by: change(step(read(), by) if by else 100))
        qconnect(shortcut.activated, act)
        # Anki's own View menu has Cmd+0 for its main window: if Qt finds
        # both, it calls neither's `activated`; take it here.
        qconnect(shortcut.activatedAmbiguously, act)
    return apply
