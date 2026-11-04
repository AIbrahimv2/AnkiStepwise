# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 AIbrahimv2
"""A compact queue meter on the deck (home) screen. Click it to open the
Tag Queue window."""

from __future__ import annotations

import html
import json

from aqt import mw

from . import actions
from .config import get_config

OPEN_CMD = "tagqueue:open"
UNITS = {"new": "new cards", "suspended": "to unsuspend", "all": "cards"}

STYLE = """
<style>
.tq-wrap { box-sizing: border-box; width: 500px; max-width: 100%; margin: 14px auto 8px;
           padding: 10px 14px 11px; border-radius: 12px; cursor: pointer; text-align: left;
           font-family: -apple-system, system-ui, sans-serif; color: var(--fg, #1a1a1a);
           transition: background .15s; }
.tq-wrap:hover { background: rgba(127,127,127,.09); }
.tq-head { display: flex; align-items: baseline; gap: 8px; }
.tq-label { flex: 1; font-size: 11px; text-transform: uppercase; letter-spacing: .1em; opacity: .5; }
.tq-num b { font-size: 21px; font-weight: 800; letter-spacing: -.02em; }
.tq-unit { font-size: 13px; opacity: .55; }
.tq-bar { height: 4px; border-radius: 2px; background: rgba(127,127,127,.18); margin-top: 7px;
          overflow: hidden; }
.tq-fill { height: 100%; border-radius: 2px; background: var(--fg, #555); opacity: .5; }
.tq-sub { font-size: 11px; opacity: .45; margin-top: 6px; }
.tq-over .tq-num b, .tq-over .tq-sub { color: #e5484d; opacity: 1; }
.tq-over .tq-fill { background: #e5484d; opacity: .9; }
</style>
"""

# Sit directly under the deck list — or under Exam Timeline if it's there,
# which places itself in the same spot.
PLACE_SCRIPT = """
<script>
(function () {
  var w = document.getElementById('tq-widget');
  if (!w) { return; }
  var et = document.getElementById('et-widget');
  if (et && et.parentNode) { et.parentNode.insertBefore(w, et.nextSibling); return; }
  var anchor = document.getElementById('study') || document.querySelector('.decktd');
  var table = anchor && anchor.closest('table');
  if (table) { table.parentNode.insertBefore(w, table.nextSibling); }
})();
</script>
"""


UPDATE_SCRIPT = """
<script>
window.tqUpdate = function (d) {
  var w = document.getElementById('tq-widget');
  if (!w) { return; }
  w.className = d.over ? 'tq-wrap tq-over' : 'tq-wrap';
  w.querySelector('.tq-num b').textContent = d.count;
  w.querySelector('.tq-unit').textContent = ' / ' + d.limit + ' ' + d.unit;
  w.querySelector('.tq-fill').style.width = d.pct + '%';
  w.querySelector('.tq-sub').textContent = d.sub;
};
</script>
"""


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word}" + ("" if n == 1 else "s")


def _data() -> dict | None:
    """What the meter shows, or None while card counts aren't ready yet.
    Counts come from the in-memory index: searching here would block the
    deck screen for seconds on a large collection."""
    cfg = get_config()
    state = actions.load_state()
    queued, later = state.queued(), state.later()
    if queued and actions.usable_index() is None:
        return None
    n = len(actions.fresh_cards(queued)) if queued else 0
    limit = cfg["card_limit"]
    over = n > limit
    if not queued:
        sub = "Nothing queued — click to pick topics"
    elif over:
        sub = f"{_plural(len(queued), 'topic')} · {n - limit:,} over your limit"
    else:
        sub = f"{_plural(len(queued), 'topic')} · {limit - n:,} left"
    if later:
        sub += f" · {len(later):,} saved for later"
    return {
        "count": f"{n:,}", "limit": f"{limit:,}", "unit": UNITS.get(cfg["count_mode"], "cards"),
        "over": over, "pct": min(100, round(100 * n / limit)) if limit else 0, "sub": sub,
    }


def build_widget() -> str:
    d = _data()
    if d is None:
        # Count in the background, then patch the numbers in place.
        actions.request_index(lambda _index: update_in_place())
        cfg = get_config()
        d = {"count": "…", "limit": f"{cfg['card_limit']:,}",
             "unit": UNITS.get(cfg["count_mode"], "cards"), "over": False, "pct": 0,
             "sub": "Counting cards…"}
    cls = "tq-wrap tq-over" if d["over"] else "tq-wrap"
    return (
        f'<div id="tq-widget" class="{cls}" onclick="pycmd(\'{OPEN_CMD}\')" title="Open Tag Queue">'
        '<div class="tq-head"><span class="tq-label">Tag queue</span>'
        f'<span class="tq-num"><b>{d["count"]}</b><span class="tq-unit"> / {d["limit"]} '
        f'{html.escape(d["unit"])}</span></span></div>'
        f'<div class="tq-bar"><div class="tq-fill" style="width:{d["pct"]}%"></div></div>'
        f'<div class="tq-sub">{html.escape(d["sub"])}</div>'
        "</div>" + STYLE + PLACE_SCRIPT + UPDATE_SCRIPT
    )


def update_in_place() -> None:
    """Refresh the meter's numbers without re-rendering the deck screen."""
    if mw.state != "deckBrowser" or not get_config()["show_on_deck_screen"]:
        return
    d = _data()
    if d is None:
        actions.request_index(lambda _index: update_in_place())
        return
    mw.deckBrowser.web.eval(f"window.tqUpdate && window.tqUpdate({json.dumps(d)});")


def on_deck_render(deck_browser, content) -> None:
    if not get_config()["show_on_deck_screen"]:
        return
    try:
        content.stats += build_widget()
    except Exception as exc:  # never break the deck screen
        print(f"Tag Queue: deck widget failed: {exc!r}")


def on_js_message(handled, message: str, context):
    if message == OPEN_CMD:
        from .ui import open_dialog

        open_dialog()
        return (True, None)
    return handled
