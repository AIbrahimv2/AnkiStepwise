# Stepwise

Open the queue from **Tools → Stepwise** (Cmd/Ctrl+Alt+Q), the meter on the deck
screen, or by right-clicking a tag in the Browser sidebar. Settings are edited in
the window itself: **⋯ → Settings…** (Anki's Config button for this add-on opens
it too). The keys below are what it saves, for reference.

Your queued and completed topics are **not** stored here. They're saved in the
collection itself, so each profile has its own queue and it syncs with your
collection.

- `card_limit` — the most cards you want to add in one study session (default
  `150`). The meter turns red when the queue goes over it.
- `count_mode` — which cards count toward the daily limit:
  - `"new"` (default): the new cards Anki will show you today, whether
    still suspended or already unsuspended. It follows each deck's **Bury
    new siblings** option: with it on, a note counts once (Anki shows one
    new card per note a day), and a note with a sibling due today doesn't
    count. Buried cards wait for the day they come back. Checking a topic
    off (which unsuspends it) doesn't change this number; studying does.
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
