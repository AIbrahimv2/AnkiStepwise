# Tag Queue

Open the queue from **Tools → Tag Queue** (Cmd/Ctrl+Alt+Q), the meter on the deck
screen, or by right-clicking a tag in the Browser sidebar. Most settings can be
changed from the window itself (the limit box and the **⋯** menu); the rest live
here.

Your queued and completed topics are **not** stored here. They're saved in the
collection itself, so each profile has its own queue and it syncs with your
collection.

- `card_limit` — the most cards you want to add in one study session (default
  `150`). The meter turns red when the queue goes over it.
- `count_mode` — which cards count toward the daily limit:
  - `"new"` (default): new cards, i.e. never studied, whether still
    suspended, already unsuspended or buried. Checking a watched topic off
    (which unsuspends it) doesn't change this number; studying does.
  - `"suspended"`: only cards still suspended (what's left to unsuspend).
  - `"all"`: every card under the tag.
- `unsuspend_on_complete` — unsuspend a topic's cards when you mark it
  completed (default `true`).
- `resource_roots` — top-level tags whose children are listed as resources.
  Wildcards are allowed. The default, `["#AK_Step*"]`, lists `B&B`, `Bootcamp`,
  `Pixorize`, … from the AnKing Step 1/2/3 decks. Other top-level tags appear
  under **Other tags**.
- `pinned_resources` — full tag names shown first, marked with ★. Right-click a
  resource → **Pin to top** to change this from the window.
- `hide_completed` — hide completed topics in the tag tree.
- `search_scope` — which resources the tree shows and searches, as picked from
  the dropdown next to the search box: `"all"`, `"pinned"`, a whole step
  (e.g. `"#ak_step1_v12"`), or one resource's full tag name (lower-case).
- `show_on_deck_screen` — show the queue meter under the deck list.
- `colorful_tags_sync` — if the
  [Colorful Tags](https://ankiweb.net/shared/info/594329229) add-on is
  installed, colour queued and completed tags in the Browser sidebar
  automatically. Colours you assigned yourself are never removed.
- `queued_color` / `completed_color` / `later_color` — the sidebar colours
  used for that.
- `shortcut` — keyboard shortcut for the Tools menu entry (empty to disable).
- `import_offered` — set to `false` to see the "import from Colorful Tags"
  banner again.
