# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""The Tag Queue window.

Left: every tag, grouped by resource (B&B, Bootcamp, Pixorize, ...), with a
checkbox to queue it and its card counts. Right: the queue itself, with a
unique-card meter against your limit, and the list of completed topics.
"""

from __future__ import annotations

import html
import time
from datetime import datetime

import aqt
from aqt import mw
from aqt.qt import (
    QCheckBox,
    QColor,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFont,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    Qt,
    QTabWidget,
    QTimer,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    qconnect,
)
from aqt.theme import theme_manager
from aqt.utils import askUser, restoreGeom, restoreSplitter, saveGeom, saveSplitter, tooltip

from . import actions, colorsync
from .config import get_config, update_config
from .counts import (
    TagIndex,
    fresh_ids,
    natural_key,
    prettify,
    resource_roots,
    root_label,
    root_matcher,
    short_path,
)
from .state import COMPLETED, QUEUED, SEP

GEOM_KEY = "tag_queue"
KEY_ROLE = Qt.ItemDataRole.UserRole
PLACEHOLDER = "\x00placeholder"
GROUP = "\x00group"
COL_NAME, COL_NEW, COL_TOTAL, COL_STATUS = range(4)
MAX_MATCHES = 200
OVER_COLOR = "#e5484d"
SCOPE_ALL = "all"
SCOPE_PINNED = "pinned"
UNITS = {"new": "new cards", "suspended": "suspended cards", "all": "cards"}

CHECKED = Qt.CheckState.Checked
PARTIAL = Qt.CheckState.PartiallyChecked
UNCHECKED = Qt.CheckState.Unchecked
CHECKABLE = Qt.ItemFlag.ItemIsUserCheckable
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def _status_color(hex_color: str) -> QColor:
    """Config colours are tuned for sidebar text on dark backgrounds; darken
    them a little in light mode so they stay readable."""
    c = QColor(hex_color)
    return c if theme_manager.night_mode else c.darker(135)


def _muted() -> QColor:
    return QColor(128, 128, 128)


def _fmt_day(ts: int) -> str:
    if not ts:
        return "imported"
    dt = datetime.fromtimestamp(ts)
    s = f"{dt:%b} {dt.day}"
    return s if dt.year == datetime.now().year else f"{s}, {dt.year}"


def _gray(label: QLabel, size: int | None = None) -> QLabel:
    label.setStyleSheet("color: gray;" + (f" font-size: {size}px;" if size else ""))
    return label


# --- small widgets -----------------------------------------------------------


class TagRow(QFrame):
    """One topic in the Queue / Completed lists."""

    def __init__(self, title: str, subtitle: str, note: str, buttons, tip: str = ""):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 4, 6)
        lay.setSpacing(6)

        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(title)
        name.setTextFormat(Qt.TextFormat.PlainText)
        name.setStyleSheet("font-weight: 600;")
        name.setWordWrap(True)
        name.setToolTip(tip)
        text.addWidget(name)
        if subtitle:
            sub = _gray(QLabel(subtitle), 11)
            sub.setTextFormat(Qt.TextFormat.PlainText)
            sub.setWordWrap(True)
            text.addWidget(sub)
        lay.addLayout(text, 1)

        if note:
            n = _gray(QLabel(note))
            n.setAlignment(RIGHT)
            lay.addWidget(n)
        for label, hint, fn in buttons:
            b = QToolButton()
            b.setText(label)
            b.setToolTip(hint)
            b.setAutoRaise(True)
            qconnect(b.clicked, fn)
            lay.addWidget(b)


class RowList(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        self._lay = QVBoxLayout(host)
        self._lay.setContentsMargins(0, 4, 4, 4)
        self._lay.setSpacing(6)
        self._lay.addStretch(1)
        self.setWidget(host)

    def set_rows(self, rows: list[QWidget], empty_text: str) -> None:
        while self._lay.count() > 1:
            w = self._lay.takeAt(0).widget()
            if w is not None:
                # Detach now; deleteLater alone leaves it painted until the
                # event loop gets round to it.
                w.hide()
                w.setParent(None)
                w.deleteLater()
        if not rows:
            empty = _gray(QLabel(empty_text))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setContentsMargins(10, 30, 10, 30)
            rows = [empty]
        for i, w in enumerate(rows):
            self._lay.insertWidget(i, w)


# --- main window -------------------------------------------------------------


class QueueDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Tag Queue")
        self.resize(1040, 700)
        restoreGeom(self, GEOM_KEY)

        self.index: TagIndex | None = None
        self.items: dict[str, QTreeWidgetItem] = {}
        self.roots: list[str] = []
        self._updating = False
        self._queue_ids: set[int] = set()
        self._truncated = False
        self._matches: list[str] | None = None  # top-level search hits; None when browsing

        self._index_timer = self._timer(1500, self.reload_index)
        self._search_timer = self._timer(220, self.build_tree)
        self._limit_timer = self._timer(400, actions.refresh_main_screen)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(12)
        outer.addLayout(self._build_header())
        self.banner = self._build_banner()
        outer.addWidget(self.banner)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self._build_tree_pane())
        self.splitter.addWidget(self._build_queue_pane())
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([620, 420])
        restoreSplitter(self.splitter, GEOM_KEY)
        outer.addWidget(self.splitter, 1)

        self._show_loading()

    def _timer(self, ms: int, fn) -> QTimer:
        t = QTimer(self)
        t.setSingleShot(True)
        t.setInterval(ms)
        qconnect(t.timeout, fn)
        return t

    # --- layout ----------------------------------------------------------

    def _build_header(self) -> QHBoxLayout:
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Tag Queue")
        f = title.font()
        f.setPointSize(f.pointSize() + 5)
        f.setBold(True)
        title.setFont(f)
        titles.addWidget(title)
        titles.addWidget(
            _gray(QLabel("Tick topics to queue them, watch the videos, then mark them completed."))
        )
        head.addLayout(titles, 1)

        more = QToolButton()
        more.setText("⋯")
        more.setToolTip("Options")
        more.setAutoRaise(True)
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more.setStyleSheet("QToolButton { font-size: 18px; padding: 0 6px; }"
                           "QToolButton::menu-indicator { image: none; width: 0; }")
        menu = QMenu(more)
        qconnect(menu.aboutToShow, lambda: self._fill_options(menu))
        more.setMenu(menu)
        head.addWidget(more, 0, Qt.AlignmentFlag.AlignTop)
        return head

    def _build_banner(self) -> QFrame:
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(12, 8, 8, 8)
        msg = QLabel(
            "You colour tags with <b>Colorful Tags</b>. Import those colours so Tag Queue "
            "knows what you've already queued and completed?"
        )
        msg.setWordWrap(True)
        lay.addWidget(msg, 1)
        go = QPushButton("Import…")
        go.setAutoDefault(False)
        qconnect(go.clicked, self.open_import)
        later = QPushButton("Not now")
        later.setAutoDefault(False)
        qconnect(later.clicked, self._dismiss_banner)
        lay.addWidget(go)
        lay.addWidget(later)
        box.hide()
        return box

    def _build_tree_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(8)

        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search topics, e.g. brainstem or b&b cardio")
        self.search.setClearButtonEnabled(True)
        qconnect(self.search.textChanged, lambda _t: self._search_timer.start())
        qconnect(self.search.returnPressed, self._search_now)
        bar.addWidget(self.search, 1)
        self.scope = QComboBox()
        self.scope.setToolTip("Which resources to show and search")
        self.scope.setMinimumContentsLength(14)
        self.scope.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        qconnect(self.scope.activated, self._on_scope)
        bar.addWidget(self.scope)
        self.hide_done = QCheckBox("Hide completed")
        self.hide_done.setChecked(get_config()["hide_completed"])
        qconnect(self.hide_done.toggled, self._on_hide_done)
        bar.addWidget(self.hide_done)
        lay.addLayout(bar)

        # Shown while searching: match summary + queue every match at once.
        self.match_bar = QWidget()
        mb = QHBoxLayout(self.match_bar)
        mb.setContentsMargins(2, 0, 0, 0)
        self.match_lbl = _gray(QLabel())
        self.match_lbl.setTextFormat(Qt.TextFormat.RichText)
        mb.addWidget(self.match_lbl, 1)
        self.queue_matches_btn = QPushButton("Queue all")
        self.queue_matches_btn.setAutoDefault(False)
        qconnect(self.queue_matches_btn.clicked, self._queue_matches)
        mb.addWidget(self.queue_matches_btn)
        self.match_bar.hide()
        lay.addWidget(self.match_bar)

        t = self.tree = QTreeWidget()
        t.setColumnCount(4)
        t.setHeaderLabels(["Topic", "New", "Total", "Status"])
        hdr = t.headerItem()
        hdr.setToolTip(COL_NEW, "Cards you haven't started yet (suspended or never studied)")
        hdr.setToolTip(COL_TOTAL, "Every card under this tag")
        hdr.setTextAlignment(COL_NEW, RIGHT)
        hdr.setTextAlignment(COL_TOTAL, RIGHT)
        h = t.header()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c in (COL_NEW, COL_TOTAL, COL_STATUS):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        t.setUniformRowHeights(True)
        t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        qconnect(t.itemExpanded, self._on_expand)
        qconnect(t.itemChanged, self._on_item_changed)
        qconnect(t.currentItemChanged, lambda *_: self._update_details())
        qconnect(t.customContextMenuRequested, self._on_context)
        lay.addWidget(t, 1)

        self.details = _gray(QLabel(" "))
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.RichText)
        self.details.setMinimumHeight(36)
        lay.addWidget(self.details)
        return pane

    def _build_queue_pane(self) -> QWidget:
        pane = QWidget()
        lay = QVBoxLayout(pane)
        lay.setContentsMargins(10, 0, 0, 0)
        lay.setSpacing(8)

        top = QHBoxLayout()
        top.setSpacing(6)
        self.count_lbl = QLabel("0")
        f = self.count_lbl.font()
        f.setPointSize(f.pointSize() + 16)
        f.setBold(True)
        self.count_lbl.setFont(f)
        self.limit_lbl = _gray(QLabel())
        bottom = Qt.AlignmentFlag.AlignBottom
        top.addWidget(self.count_lbl, 0, bottom)
        top.addWidget(self.limit_lbl, 0, bottom)
        top.addStretch(1)
        top.addWidget(_gray(QLabel("Limit")), 0, bottom)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 5000)
        self.limit_spin.setSingleStep(10)
        self.limit_spin.setToolTip("Most cards you want to add in one study session")
        qconnect(self.limit_spin.valueChanged, self._on_limit)
        top.addWidget(self.limit_spin, 0, bottom)
        lay.addLayout(top)

        self.meter = QProgressBar()
        self.meter.setTextVisible(False)
        self.meter.setFixedHeight(8)
        lay.addWidget(self.meter)
        self.hint = _gray(QLabel())
        lay.addWidget(self.hint)

        self.tabs = QTabWidget()
        self.queue_list = RowList()
        self.done_list = RowList()
        self.tabs.addTab(self.queue_list, "Queue")
        self.tabs.addTab(self.done_list, "Completed")
        lay.addWidget(self.tabs, 1)

        btns = QHBoxLayout()
        self.browse_btn = self._button("Browse", "Open the queued cards in the Browser",
                                       lambda: actions.browse(actions.load_state().queued()))
        self.unsuspend_btn = self._button("Unsuspend", "Unsuspend every card in the queue",
                                          lambda: actions.unsuspend(actions.load_state().queued(), self))
        self.complete_btn = self._button("Complete all", "Mark every queued topic completed",
                                         self._complete_all)
        btns.addWidget(self.browse_btn)
        btns.addStretch(1)
        btns.addWidget(self.unsuspend_btn)
        btns.addWidget(self.complete_btn)
        lay.addLayout(btns)
        return pane

    def _button(self, text: str, tip: str, fn) -> QPushButton:
        b = QPushButton(text)
        b.setToolTip(tip)
        b.setAutoDefault(False)
        qconnect(b.clicked, lambda *_: fn())
        return b

    def _fill_options(self, menu: QMenu) -> None:
        menu.clear()
        menu.addAction("Refresh counts", lambda: self.reload_index(force=True))
        imp = menu.addAction("Import from Colorful Tags…", self.open_import)
        imp.setEnabled(colorsync.available())
        menu.addSeparator()
        self._toggle(menu, "Unsuspend cards when completing", "unsuspend_on_complete")
        self._toggle(menu, "Show the queue on the deck screen", "show_on_deck_screen",
                     actions.refresh_main_screen)
        sync = self._toggle(menu, "Colour tags in Colorful Tags", "colorful_tags_sync")
        sync.setEnabled(colorsync.available())
        menu.addSeparator()
        menu.addAction("Edit config…", lambda: aqt.dialogs.open("AddonsDialog", mw))

    def _toggle(self, menu: QMenu, label: str, key: str, after=None):
        act = menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(bool(get_config()[key]))

        def flip(checked: bool) -> None:
            update_config(**{key: checked})
            self.refresh_side()
            if after:
                after()

        qconnect(act.toggled, flip)
        return act

    # --- lifecycle -------------------------------------------------------

    def showEvent(self, ev) -> None:
        super().showEvent(ev)
        actions.subscribe(self.on_state_changed)
        self.refresh_all()

    def hideEvent(self, ev) -> None:
        actions.unsubscribe(self.on_state_changed)
        saveGeom(self, GEOM_KEY)
        saveSplitter(self.splitter, GEOM_KEY)
        super().hideEvent(ev)

    def refresh_all(self) -> None:
        self._update_banner()
        self.refresh_side()
        self.reload_index()

    def on_state_changed(self) -> None:
        if self.index is not None:
            self.update_items()
        self.refresh_side()

    def schedule_index_refresh(self) -> None:
        if self.isVisible():
            self._index_timer.start()

    def reload_index(self, force: bool = False) -> None:
        if force:
            actions.mark_index_dirty()
        actions.request_index(self._on_index)

    def _on_index(self, index: TagIndex) -> None:
        old, self.index = self.index, index
        self.roots = resource_roots(index, get_config()["resource_roots"])
        if old is None or old.names.keys() != index.names.keys():
            self.build_tree()
        else:
            for key, it in self.items.items():
                if not key.startswith("\x00"):
                    self._set_numbers(it, key)
            self.update_items()
        self.refresh_side()

    # --- tree ------------------------------------------------------------

    def _show_loading(self) -> None:
        self._updating = True
        self.tree.clear()
        self.items = {}
        loading = QTreeWidgetItem(["Counting cards…"])
        loading.setFlags(Qt.ItemFlag.NoItemFlags)
        self.tree.addTopLevelItem(loading)
        self._updating = False

    def _search_now(self) -> None:
        self._search_timer.stop()
        self.build_tree()

    def build_tree(self) -> None:
        if self.index is None:
            return
        self._rebuild_scope()
        self._updating = True
        try:
            expanded = [k for k, it in self.items.items() if it.isExpanded()]
            current = self._current_key()
            self.tree.clear()
            self.items = {}
            self._truncated = False
            self._matches = None
            query = self.search.text().strip()
            if query:
                self._build_filtered(query)
            else:
                self._build_browse()
                for key in sorted(expanded, key=lambda k: k.count(SEP)):
                    if key in self.items:
                        self.items[key].setExpanded(True)
                if self.tree.topLevelItemCount() == 1:
                    # A single resource is in scope: open it straight away.
                    self.tree.topLevelItem(0).setExpanded(True)
            if current in self.items:
                self.tree.setCurrentItem(self.items[current])
        finally:
            self._updating = False
        self.update_items()
        self._update_details()
        self._update_match_bar()

    def _resource_label(self, key: str, root: str | None) -> str:
        label = prettify(self.index.last(key))
        if root and len(self.roots) > 1:
            label += f"  ·  {root_label(self.index.name(root))}"
        return label

    def _pinned(self) -> list[str]:
        return [p.lower() for p in get_config()["pinned_resources"] if isinstance(p, str)]

    def _browse_entries(self) -> tuple[list[tuple[str, str]], list[str]]:
        """Resources under the roots as (key, root), then other top-level
        tags, each in display order (pinned first)."""
        idx = self.index
        pinned = self._pinned()

        def order(key: str):
            return (key not in pinned, pinned.index(key) if key in pinned else 0,
                    natural_key(idx.last(key)))

        resources = sorted(((c, r) for r in self.roots for c in idx.kids(r)),
                           key=lambda kr: (order(kr[0]), kr[1]))
        others = sorted((k for k in idx.kids("") if k not in self.roots), key=order)
        return resources, others

    # --- resource scope (the dropdown next to search) ---------------------

    def _pinned_resources(self) -> list[str]:
        if self.index is None:
            return []
        return [p for p in self._pinned() if p in self.index.names and self._is_resource(p)]

    def _scope_value(self) -> str:
        """'all', 'pinned', or one resource's key. Falls back to 'all' when
        the saved scope no longer applies (pins removed, tag renamed)."""
        v = get_config()["search_scope"]
        v = v.lower() if isinstance(v, str) else SCOPE_ALL
        if v == SCOPE_PINNED:
            return v if self._pinned_resources() else SCOPE_ALL
        if v != SCOPE_ALL and self.index is not None and v in self.index.names and self._is_resource(v):
            return v
        return SCOPE_ALL

    def _scope_keys(self) -> set[str] | None:
        v = self._scope_value()
        if v == SCOPE_ALL:
            return None
        if v == SCOPE_PINNED:
            return set(self._pinned_resources())
        return {v}

    @staticmethod
    def _in_scope(key: str, scope: set[str] | None) -> bool:
        return scope is None or any(key == s or key.startswith(s + SEP) for s in scope)

    def _rebuild_scope(self) -> None:
        if self.index is None:
            return
        self.scope.blockSignals(True)
        self.scope.clear()
        self.scope.addItem("All resources", SCOPE_ALL)
        if self._pinned_resources():
            self.scope.addItem("★ Pinned resources", SCOPE_PINNED)
        self.scope.insertSeparator(self.scope.count())
        resources, others = self._browse_entries()
        for key, root in resources:
            self.scope.addItem(self._resource_label(key, root), key)
        for key in others:
            self.scope.addItem(prettify(self.index.last(key)), key)
        self.scope.setCurrentIndex(max(0, self.scope.findData(self._scope_value())))
        self.scope.blockSignals(False)

    def _on_scope(self, row: int) -> None:
        update_config(search_scope=self.scope.itemData(row) or SCOPE_ALL)
        self.build_tree()

    def _build_browse(self) -> None:
        pinned = self._pinned()
        scope = self._scope_keys()
        resources, others = self._browse_entries()
        for key, root in resources:
            if self._in_scope(key, scope):
                self._make_item(None, key, self._resource_label(key, root), top=True,
                                pinned=key in pinned)

        others = [k for k in others if self._in_scope(k, scope)]
        if not others:
            return
        parent = None
        if self.roots and scope is None:
            parent = QTreeWidgetItem(["Other tags"])
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled)
            parent.setData(COL_NAME, KEY_ROLE, GROUP)
            parent.setForeground(COL_NAME, _muted())
            self.tree.addTopLevelItem(parent)
            self.items[GROUP] = parent
        for key in others:
            self._make_item(parent, key, top=parent is None, pinned=key in pinned)

    def _build_filtered(self, query: str) -> None:
        idx = self.index
        words = query.lower().replace("_", " ").split()
        roots = set(self.roots)
        scope = self._scope_keys()
        matches = [
            k for k in idx.names
            if k not in roots
            and self._in_scope(k, scope)
            and all(w in k.replace("_", " ") for w in words)
        ]
        mset = set(matches)

        def has_matched_ancestor(k: str) -> bool:
            parts = k.split(SEP)
            return any(SEP.join(parts[:i]) in mset for i in range(1, len(parts)))

        top = sorted((k for k in matches if not has_matched_ancestor(k)),
                     key=lambda k: natural_key(idx.name(k)))
        self._truncated = len(top) > MAX_MATCHES
        self._matches = top[:MAX_MATCHES]
        opened: list[QTreeWidgetItem] = []
        for key in top[:MAX_MATCHES]:
            parts = key.split(SEP)
            start = 2 if parts[0] in roots else 1
            root = parts[0] if start == 2 else None
            parent = None
            for i in range(start, len(parts) + 1):
                k = SEP.join(parts[:i])
                it = self.items.get(k)
                if it is None:
                    label = self._resource_label(k, root) if i == start else None
                    it = self._make_item(parent, k, label, lazy=(k == key), top=(i == start))
                    if k != key:
                        opened.append(it)
                parent = it
        for it in opened:
            it.setExpanded(True)
        if not top:
            where = "" if scope is None else f" in {self.scope.currentText()}"
            none = QTreeWidgetItem([f"No topics match “{query}”{where}"])
            none.setFlags(Qt.ItemFlag.NoItemFlags)
            self.tree.addTopLevelItem(none)

    # --- queue every search match ------------------------------------------

    def _match_summary(self):
        """(tags that could be queued, # already queued, # done) for the
        current search hits. Completed topics are never re-queued in bulk."""
        state = actions.load_state()
        cands, queued, done = [], 0, 0
        for key in self._matches or []:
            name = self.index.name(key)
            status, _src = state.effective(name)
            if status == COMPLETED:
                done += 1
            elif status == QUEUED:
                queued += 1
            else:
                cands.append(name)
        return cands, queued, done

    def _projection(self, tags: list[str]) -> tuple[int, int]:
        """(new cards these tags add to the queue, queue size afterwards)."""
        ids = set(fresh_ids(mw.col, tags, get_config()["count_mode"])) if tags else set()
        add = len(ids - self._queue_ids)
        return add, len(self._queue_ids) + add

    def _update_match_bar(self) -> None:
        if self._matches is None or self.index is None:
            self.match_bar.hide()
            return
        n = len(self._matches)
        if not n:
            self.match_bar.hide()
            return
        cands, queued, done = self._match_summary()
        head = (f"First {MAX_MATCHES} matches" if self._truncated
                else f"{n:,} match" + ("" if n == 1 else "es"))
        bits = [head]
        if queued:
            bits.append(f"{queued:,} queued")
        if done:
            bits.append(f"{done:,} done")
        text = " · ".join(bits)
        btn = self.queue_matches_btn
        if self._truncated:
            btn.setText("Queue all")
            btn.setEnabled(False)
            btn.setToolTip("Too many matches to queue at once. Narrow the search or pick a resource.")
        elif not cands:
            btn.setText("Queue all")
            btn.setEnabled(False)
            btn.setToolTip("Every match is already queued or completed.")
        else:
            add, after = self._projection(cands)
            limit = get_config()["card_limit"]
            proj = f"+{add:,} new → {after:,} / {limit:,}"
            if after > limit:
                proj = f"<span style='color:{OVER_COLOR}'>{proj}</span>"
            text += f" — queuing the rest adds {proj}"
            btn.setText(f"Queue {len(cands):,}")
            btn.setEnabled(True)
            btn.setToolTip("Queue every match that isn't already queued or completed")
        self.match_lbl.setText(text)
        self.match_bar.show()

    def _queue_matches(self) -> None:
        if not self._matches or self._truncated:
            return
        cands, _queued, _done = self._match_summary()
        if not cands:
            return
        add, after = self._projection(cands)
        limit = get_config()["card_limit"]
        if after > limit and not askUser(
            f"Queuing {_plural(len(cands), 'topic')} adds {add:,} new cards, bringing your "
            f"queue to {after:,} — {after - limit:,} over your {limit:,}-card limit.\n\n"
            "Queue them anyway?",
            parent=self, defaultno=True, title="Tag Queue",
        ):
            return
        actions.queue(cands)
        tooltip(f"Queued {_plural(len(cands), 'topic')} · +{add:,} new cards", parent=self)

    def _make_item(self, parent, key: str, label: str | None = None, lazy: bool = True,
                   top: bool = False, pinned: bool = False) -> QTreeWidgetItem:
        idx = self.index
        it = QTreeWidgetItem()
        text = label or prettify(idx.last(key))
        it.setText(COL_NAME, ("★ " + text) if pinned else text)
        it.setData(COL_NAME, KEY_ROLE, key)
        it.setToolTip(COL_NAME, idx.name(key))
        it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | CHECKABLE)
        it.setCheckState(COL_NAME, UNCHECKED)
        it.setTextAlignment(COL_NEW, RIGHT)
        it.setTextAlignment(COL_TOTAL, RIGHT)
        if top:
            f = QFont(it.font(COL_NAME))
            f.setBold(True)
            it.setFont(COL_NAME, f)
        self._set_numbers(it, key)
        if lazy and idx.kids(key):
            ph = QTreeWidgetItem()
            ph.setData(COL_NAME, KEY_ROLE, PLACEHOLDER)
            it.addChild(ph)
        if parent is None:
            self.tree.addTopLevelItem(it)
        else:
            parent.addChild(it)
        self.items[key] = it
        return it

    def _set_numbers(self, it: QTreeWidgetItem, key: str) -> None:
        fresh = self.index.fresh.get(key, 0)
        it.setText(COL_NEW, f"{fresh:,}")
        it.setText(COL_TOTAL, f"{self.index.total.get(key, 0):,}")
        if fresh:
            it.setData(COL_NEW, Qt.ItemDataRole.ForegroundRole, None)
        else:
            it.setForeground(COL_NEW, _muted())
        it.setForeground(COL_TOTAL, _muted())

    def _on_expand(self, item: QTreeWidgetItem) -> None:
        if item.childCount() != 1 or item.child(0).data(COL_NAME, KEY_ROLE) != PLACEHOLDER:
            return
        prev, self._updating = self._updating, True
        try:
            item.takeChild(0)
            key = item.data(COL_NAME, KEY_ROLE)
            made = [self._make_item(item, c) for c in self.index.kids(key)]
            ctx = self._ctx()
            for it in made:
                self._update_item(it, ctx)
        finally:
            self._updating = prev

    def _ctx(self):
        state = actions.load_state()
        queued = [q.lower() for q in state.queued()]
        done = [c.lower() for c in state.completed()]
        done_set = set(done)
        top_done = [
            c for c in done
            if not any(SEP.join(c.split(SEP)[:i]) in done_set for i in range(1, c.count(SEP) + 1))
        ]
        cfg = get_config()
        return state, queued, top_done, cfg

    def update_items(self) -> None:
        if self.index is None:
            return
        prev, self._updating = self._updating, True
        try:
            ctx = self._ctx()
            for key, it in self.items.items():
                if not key.startswith("\x00"):
                    self._update_item(it, ctx)
        finally:
            self._updating = prev

    def _update_item(self, it: QTreeWidgetItem, ctx) -> None:
        state, queued, top_done, cfg = ctx
        key = it.data(COL_NAME, KEY_ROLE)
        status, source = state.effective(self.index.name(key))
        inherited = status is not None and source.lower() != key
        nested_q = sum(1 for q in queued if q.startswith(key + SEP))

        flags = it.flags()
        if status == QUEUED:
            it.setCheckState(COL_NAME, CHECKED)
            it.setFlags(flags & ~CHECKABLE if inherited else flags | CHECKABLE)
        else:
            it.setFlags(flags | CHECKABLE)
            it.setCheckState(COL_NAME, PARTIAL if nested_q else UNCHECKED)

        tip = ""
        if status == QUEUED:
            text, color = "Queued", _status_color(cfg["queued_color"])
            if inherited:
                tip = f"Queued as part of {source}"
        elif status == COMPLETED:
            text, color = "✓ Done", _status_color(cfg["completed_color"])
            tip = f"Completed {_fmt_day(state.completed_at(source))}"
            if inherited:
                tip += f" as part of {source}"
        else:
            bits = []
            if nested_q:
                bits.append(f"{nested_q} queued")
            leaves = self.index.leaves.get(key, 1)
            if leaves > 1:
                done = sum(self.index.leaves.get(c, 1) for c in top_done if c.startswith(key + SEP))
                if done:
                    bits.append(f"{done}/{leaves} done")
                    tip = f"{done} of {leaves} topics completed"
            text, color = " · ".join(bits), _muted()
        it.setText(COL_STATUS, text)
        it.setToolTip(COL_STATUS, tip)
        it.setForeground(COL_STATUS, color)
        f = QFont(it.font(COL_STATUS))
        f.setItalic(inherited)
        it.setFont(COL_STATUS, f)

        if status == COMPLETED:
            it.setForeground(COL_NAME, _muted())
        else:
            it.setData(COL_NAME, Qt.ItemDataRole.ForegroundRole, None)
        it.setHidden(self.hide_done.isChecked() and status == COMPLETED)

    def _current_key(self) -> str | None:
        it = self.tree.currentItem()
        key = it.data(COL_NAME, KEY_ROLE) if it else None
        return key if key and not key.startswith("\x00") else None

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating or column != COL_NAME or self.index is None:
            return
        key = item.data(COL_NAME, KEY_ROLE)
        if not key or key.startswith("\x00"):
            return
        tag = self.index.name(key)
        if item.checkState(COL_NAME) == CHECKED:
            actions.queue([tag])
            self._warn_if_over()
        else:
            actions.unqueue([tag])

    def _warn_if_over(self) -> None:
        limit = get_config()["card_limit"]
        n = len(self._queue_ids)
        if n > limit:
            tooltip(f"{n - limit:,} over your {limit:,}-card limit", parent=self)

    def _is_resource(self, key: str) -> bool:
        parent = key.rsplit(SEP, 1)[0] if SEP in key else ""
        return parent in self.roots or (parent == "" and key not in self.roots)

    def _on_context(self, pos) -> None:
        it = self.tree.itemAt(pos)
        key = it.data(COL_NAME, KEY_ROLE) if it else None
        if not key or key.startswith("\x00") or self.index is None:
            return
        tag = self.index.name(key)
        state = actions.load_state()
        own = state.status(tag)
        effective, _src = state.effective(tag)

        menu = QMenu(self)
        if own == QUEUED:
            menu.addAction("Remove from queue", lambda: actions.unqueue([tag]))
        else:
            add = menu.addAction("Add to queue", lambda: (actions.queue([tag]), self._warn_if_over()))
            add.setEnabled(effective != QUEUED)
        if own != COMPLETED:
            menu.addAction("Mark completed", lambda: actions.complete([tag], self))
        if own:
            menu.addAction("Clear status", lambda: actions.clear([tag]))
        menu.addSeparator()
        menu.addAction("Browse cards", lambda: actions.browse([tag]))
        menu.addAction("Unsuspend cards", lambda: actions.unsuspend([tag], self))
        if self._is_resource(key):
            menu.addSeparator()
            pinned = key in self._pinned()
            menu.addAction("Unpin" if pinned else "Pin to top", lambda: self._toggle_pin(tag))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _toggle_pin(self, tag: str) -> None:
        pins = [p for p in get_config()["pinned_resources"] if isinstance(p, str)]
        rest = [p for p in pins if p.lower() != tag.lower()]
        update_config(pinned_resources=rest if len(rest) != len(pins) else pins + [tag])
        self.build_tree()

    def _on_hide_done(self, checked: bool) -> None:
        update_config(hide_completed=checked)
        self.update_items()

    # --- details line ----------------------------------------------------

    def _update_details(self) -> None:
        key = self._current_key()
        if key is None or self.index is None:
            self.details.setText(
                f"Showing the first {MAX_MATCHES} matches — keep typing to narrow it down."
                if self._truncated else
                "Select a topic to see how many new cards it would add to your queue."
            )
            return
        cfg = get_config()
        tag = self.index.name(key)
        state = actions.load_state()
        status, source = state.effective(tag)
        fresh = self.index.fresh.get(key, 0)
        total = self.index.total.get(key, 0)
        head = (f"<b>{html.escape(prettify(self.index.last(key)))}</b> — "
                f"{fresh:,} new of {total:,} cards")
        if status == QUEUED:
            via = "" if source.lower() == key else f" (via {html.escape(prettify(source.rsplit(SEP, 1)[-1]))})"
            tail = f"in your queue{via}"
        elif status == COMPLETED:
            tail = f"completed {_fmt_day(state.completed_at(source))}"
        else:
            ids = set(fresh_ids(mw.col, [tag], cfg["count_mode"]))
            add = len(ids - self._queue_ids)
            overlap = len(ids) - add
            after = len(self._queue_ids) + add
            limit = cfg["card_limit"]
            tail = f"queuing it adds <b>{add:,}</b>"
            if overlap:
                tail += f" ({overlap:,} already queued via other topics)"
            arrow = f"{after:,} / {limit:,}"
            if after > limit:
                arrow = f"<span style='color:{OVER_COLOR}'>{arrow}</span>"
            tail += f" → {arrow}"
        self.details.setText(f"{head} · {tail}")

    # --- queue side ------------------------------------------------------

    def refresh_side(self) -> None:
        cfg = get_config()
        state = actions.load_state()
        queued, done = state.queued(), state.completed()
        mode = cfg["count_mode"]
        self._queue_ids = set(fresh_ids(mw.col, queued, mode)) if queued else set()
        n, limit = len(self._queue_ids), cfg["card_limit"]
        over = n > limit

        self.count_lbl.setText(f"{n:,}")
        self.count_lbl.setStyleSheet(f"color: {OVER_COLOR};" if over else "")
        self.limit_lbl.setText(f"/ {limit:,} {UNITS.get(mode, 'cards')}")
        self.limit_spin.blockSignals(True)
        self.limit_spin.setValue(limit)
        self.limit_spin.blockSignals(False)
        self.meter.setMaximum(limit)
        self.meter.setValue(min(n, limit))
        fill = OVER_COLOR if over else "rgba(127,127,127,0.75)"
        self.meter.setStyleSheet(
            "QProgressBar { border: none; border-radius: 4px; background: rgba(127,127,127,0.18); }"
            f"QProgressBar::chunk {{ border-radius: 4px; background: {fill}; }}"
        )
        if not queued:
            self.hint.setText("Nothing queued yet — tick topics on the left.")
            self.hint.setStyleSheet("color: gray;")
        elif over:
            self.hint.setText(f"{n - limit:,} over your limit · {_plural(len(queued), 'topic')}")
            self.hint.setStyleSheet(f"color: {OVER_COLOR};")
        else:
            self.hint.setText(f"{limit - n:,} left · {_plural(len(queued), 'topic')}")
            self.hint.setStyleSheet("color: gray;")

        is_root = root_matcher(cfg["resource_roots"])
        with_root = len(self.roots) != 1
        names = self.index.names if self.index is not None else None
        complete_tip = "Mark completed" + (
            " and unsuspend its cards" if cfg["unsuspend_on_complete"] else "")

        rows: list[QWidget] = []
        for tag in queued:
            missing = names is not None and tag.lower() not in names
            sub = "Tag not found in this collection" if missing else short_path(tag, is_root, with_root)
            cnt = self._fresh_count(tag, mode)
            rows.append(TagRow(
                prettify(tag.rsplit(SEP, 1)[-1]), sub, f"{cnt:,} new",
                [("✓", complete_tip, lambda *_, t=tag: actions.complete([t], self)),
                 ("✕", "Remove from queue", lambda *_, t=tag: actions.unqueue([t]))],
                tag,
            ))
        self.queue_list.set_rows(rows, "Your queue is empty.\nTick topics on the left to add them.")

        rows = []
        for tag in done:
            sub = short_path(tag, is_root, with_root)
            rows.append(TagRow(
                prettify(tag.rsplit(SEP, 1)[-1]), sub, _fmt_day(state.completed_at(tag)),
                [("↺", "Move back to the queue", lambda *_, t=tag: actions.queue([t])),
                 ("✕", "Clear status", lambda *_, t=tag: actions.clear([t]))],
                tag,
            ))
        self.done_list.set_rows(rows, "Nothing completed yet.")

        self.tabs.setTabText(0, f"Queue ({len(queued)})")
        self.tabs.setTabText(1, f"Completed ({len(done)})")
        for b in (self.browse_btn, self.unsuspend_btn, self.complete_btn):
            b.setEnabled(bool(queued))
        self._update_details()
        self._update_match_bar()

    def _fresh_count(self, tag: str, mode: str) -> int:
        if self.index is not None and self.index.mode == mode:
            return self.index.fresh.get(tag.lower(), 0)
        return len(fresh_ids(mw.col, [tag], mode))

    def _on_limit(self, value: int) -> None:
        update_config(card_limit=value)
        self.refresh_side()
        self._limit_timer.start()

    def _complete_all(self) -> None:
        queued = actions.load_state().queued()
        if not queued:
            return
        msg = f"Mark {_plural(len(queued), 'queued topic')} completed?"
        if get_config()["unsuspend_on_complete"]:
            msg += "\n\nTheir suspended cards will be unsuspended."
        if askUser(msg, parent=self, defaultno=False, title="Tag Queue"):
            actions.complete(queued, self)

    # --- Colorful Tags import --------------------------------------------

    def _update_banner(self) -> None:
        ud = colorsync.find_user_data()
        self.banner.setVisible(
            not get_config()["import_offered"] and ud is not None and bool(colorsync.color_groups(ud))
        )

    def _dismiss_banner(self) -> None:
        update_config(import_offered=True)
        self.banner.hide()

    def open_import(self) -> None:
        ud = colorsync.find_user_data()
        if ud is None:
            tooltip("Colorful Tags isn't installed or is disabled.", parent=self)
            return
        dlg = ImportDialog(self, ud)
        if not dlg.exec():
            return
        names = self.index.names if self.index is not None else None
        state = actions.load_state()
        now = int(time.time())
        changes: dict = {}
        counts = {QUEUED: 0, COMPLETED: 0}
        skipped = 0
        for tags, status in dlg.choices():
            for tag in tags:
                if names is not None:
                    if tag.lower() not in names:
                        skipped += 1
                        continue
                    tag = names[tag.lower()]
                changes.update(state.import_status(tag, status, 0 if status == COMPLETED else now))
                counts[status] += 1
        if dlg.import_pins():
            pins = [p for p in get_config()["pinned_resources"] if isinstance(p, str)]
            have = {p.lower() for p in pins}
            pins += [t for t in colorsync.pinned_tags(ud) if t.lower() not in have]
            update_config(pinned_resources=pins)
        update_config(import_offered=True)
        self.banner.hide()
        actions.commit(state, changes)
        self.build_tree()
        msg = (f"Imported {_plural(counts[QUEUED], 'queued topic')} and "
               f"{_plural(counts[COMPLETED], 'completed topic')}")
        if skipped:
            msg += f" · skipped {skipped:,} tags that no longer exist"
        tooltip(msg, parent=self, period=5000)


class ImportDialog(QDialog):
    CHOICES = [("Ignore", None), ("Queued", QUEUED), ("Completed", COMPLETED)]

    def __init__(self, parent, ud):
        super().__init__(parent)
        self.setWindowTitle("Import from Colorful Tags")
        self.groups = colorsync.color_groups(ud)
        self.pins = colorsync.pinned_tags(ud)
        self.combos: list[tuple[QComboBox, list[str]]] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel("What does each colour mean?")
        f = title.font()
        f.setPointSize(f.pointSize() + 3)
        f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)
        intro = _gray(QLabel(
            "Pick a status for each colour you've used. Tag Queue then keeps the colours "
            "in sync for you: queued tags turn orange, completed tags green."
        ))
        intro.setWordWrap(True)
        lay.addWidget(intro)

        for color, tags in self.groups.items():
            row = QHBoxLayout()
            row.setSpacing(10)
            swatch = QLabel()
            swatch.setFixedSize(18, 18)
            swatch.setStyleSheet(f"background: {color}; border-radius: 4px;")
            row.addWidget(swatch, 0, Qt.AlignmentFlag.AlignTop)
            sample = ", ".join(prettify(t.rsplit(SEP, 1)[-1]) for t in tags[:3])
            if len(tags) > 3:
                sample += ", …"
            info = QLabel(f"<b>{_plural(len(tags), 'tag')}</b><br>"
                          f"<span style='color:gray'>{html.escape(sample)}</span>")
            info.setWordWrap(True)
            info.setMinimumWidth(340)
            row.addWidget(info, 1)
            combo = QComboBox()
            for label, _status in self.CHOICES:
                combo.addItem(label)
            combo.setCurrentIndex(2 if colorsync.looks_green(color) else 0)
            row.addWidget(combo, 0, Qt.AlignmentFlag.AlignTop)
            self.combos.append((combo, tags))
            lay.addLayout(row)

        self.pin_box = QCheckBox(
            f"Also pin the {_plural(len(self.pins), 'tag')} you pinned in Colorful Tags to the top"
        )
        self.pin_box.setChecked(bool(self.pins))
        self.pin_box.setVisible(bool(self.pins))
        lay.addWidget(self.pin_box)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                               | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Import")
        qconnect(box.accepted, self.accept)
        qconnect(box.rejected, self.reject)
        lay.addWidget(box)

    def choices(self) -> list[tuple[list[str], str]]:
        out = []
        for combo, tags in self.combos:
            status = self.CHOICES[combo.currentIndex()][1]
            if status:
                out.append((tags, status))
        return out

    def import_pins(self) -> bool:
        return self.pin_box.isChecked() and bool(self.pins)


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
        _dialog.deleteLater()
        _dialog = None


def on_operation(changes, handler) -> None:
    actions.on_operation(changes, handler)
    if _dialog is not None and (getattr(changes, "card", False) or getattr(changes, "tag", False)
                                or getattr(changes, "note_text", False)):
        _dialog.schedule_index_refresh()
