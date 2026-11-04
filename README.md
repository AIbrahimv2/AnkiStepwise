# Tag Queue

An [Anki](https://apps.ankiweb.net/) add-on for planning study sessions by tag.
Tick the topics you'll cover today, grouped by resource (B&B, Bootcamp,
Pixorize, Sketchy, …). A live meter shows how many **new cards** that adds
against your session limit. When you've covered a topic (a video, a chapter,
a set of notes), check it off, which also unsuspends its cards.

It's built for the AnKing workflow of "cover the resource, unsuspend its cards",
and works with any hierarchical tags. The window is a web UI (React) that follows
Anki's light and dark themes, with vim-style keyboard navigation.

## Features

- **Tag tree by resource, split by step.** Resources sit under colour-coded
  **Step 1 / Step 2 / Step 3** sections that stay pinned to the top while you
  scroll, with checkboxes to queue topics and columns for new cards, total cards
  and a progress bar (hover it for the numbers); the status column marks Later
  topics with a bookmark and done ones with a check (hover for the date). Queue, Later and Done rows carry a matching
  step chip.
- **Keyword search.** Type `brainstem` or `b&b cardio` to see matching topics
  from every resource, nested under the resource they belong to. A dropdown next
  to the search box limits the tree and the search to **all resources**, your
  **pinned resources**, or a **single resource**.
- **Queue all matches.** One click queues every topic the search found that
  isn't already queued or completed. Hover the button to see how many new
  cards that adds; it asks first if the total would go over your limit.
- **Save for later.** Found a topic that won't fit this session? Hover it and
  click the bookmark (or press **s**) to park it in the **Later** tab, where it
  doesn't count toward your limit. Going over the limit offers **Move to
  Later** right in the warning, and **Fill queue** later queues the oldest
  Later topics that fit under your limit.
- **Suspended vs waiting.** The tree shows **Suspended** (cards you still have
  to unsuspend — what counts toward your limit) separately from **Waiting**
  (already unsuspended but not studied yet; a ☾ marks ones buried by sibling
  settings, which come back by themselves), so a topic whose cards are only
  buried no longer looks unfinished.
- **Grouped by resource.** Queue and Later group topics under their resource
  (Pixorize, Bootcamp, …) with each group's unique new-card count in the same
  column as the topics' counts (labelled once, at the top), and cluster topics
  that share a parent folder. Group buttons complete a whole resource or
  move it to/from Later. Switch to "Order added" any time.
- **Done takes care of itself.** A topic whose every card has been studied
  counts as done and leaves Queue/Later on its own (cards that are only
  unsuspended keep it open). Topics you studied without ever queuing or
  colouring them are marked done too, dated the day you finished them:
  in every resource you use, down to the deepest level you've queued at
  there (so stray question IDs and sub-headings that other resources' cards
  happen to finish don't bury the Done list). Once everything in a folder is done the folder
  itself is marked complete, so Done shows "16 Neuro" rather than each of its
  videos.
- **Click to find it.** Click any row in Queue, Later or Done to jump to that
  tag in the tree: it opens the step, resource and folders, scrolls there and
  highlights it.
- **Unique-card meter.** The queue counts each card once, even when it's tagged
  under several queued topics (common in AnKing, where one card carries B&B,
  Bootcamp and Pixorize tags). Select a topic to see how many cards it *would
  add* before you queue it.
- **Daily plan.** The queue is your plan for the day's new cards (150 by
  default). The meter counts every new card in it, still suspended or already
  unsuspended, so checking a topic off doesn't change it; studying the
  cards does. It turns red when the plan goes over.
- **Check off as you go.** ✓ on a queued topic unsuspends its cards and
  checks it off: it stays in the queue (with an undo) until every card in it
  is studied, then moves to Done by itself. Anything unfinished carries over to
  the next day. **Clear checked** takes checked-off topics off early.
- **Deck-screen meter.** A compact meter under the deck list; click it to open
  the queue.
- **Browser sidebar.** Right-click any tag (or several) → **Tag Queue** → Add to
  queue / Mark completed.
- **Colorful Tags integration.** If
  [Colorful Tags](https://ankiweb.net/shared/info/594329229) is installed,
  queued tags turn orange and completed tags green in the Browser sidebar
  automatically. If you already colour tags by hand, the first run offers to
  import those colours as queued or completed.
- The queue is saved in your collection, so it's per profile and syncs with it.

## Usage

1. Open **Tools → Tag Queue** (Cmd/Ctrl+Alt+Q) or click the meter on the deck
   screen.
2. Expand a resource and tick the topics you plan to cover. Ticking a parent
   queues everything under it. Or search for a keyword, pick the resource you're
   using from the dropdown, and click **Queue N** to queue every match. Keep
   the meter under your limit.
3. Work through the topics one by one (watch the video, read the chapter) and
   click **✓** after each. Its cards are unsuspended and it's checked off, but it stays in the plan, so the meter
   keeps showing the day's new cards.
4. Study. As you finish a topic's cards it leaves the queue by itself; whatever
   you didn't get to stays queued for tomorrow, still counted against the
   limit.

Hit your limit but found more to do? Press **s** on a topic (or click its
bookmark) to save it for later. Next session, open the **Later** tab and click
**Fill queue**.

Right-click a topic for more: save it for later, browse its cards, unsuspend
without completing, clear its status, or pin a resource to the top.

### Keyboard

The tag tree uses vim keys (arrow keys, Home and End work too):

| Keys | Does |
| --- | --- |
| `j` / `k` | Move down / up |
| `l` / `h` | Open a folder or step into it / close it or go to its parent |
| `gg` / `G` | Jump to the top / bottom |
| `Ctrl-d` / `Ctrl-u` | Move half a page down / up |
| `o` or `Enter` | Open or close a folder |
| `Space` | Queue or unqueue the topic |
| `s` | Save the topic for later (or take it back off Later) |
| `u` or `Cmd/Ctrl+Z` | Undo the last change |
| `Ctrl-r` or `Cmd/Ctrl+Shift+Z` | Redo it |
| `/` | Search |

Undo covers what you do in the Tag Queue window (queue, unqueue, Later,
check off, clear, Fill queue, queue or save all search matches, imports),
up to 50 steps back. Undoing a check-off puts the topic back in the queue
and suspends the cards it unsuspended again, if you haven't studied them
yet. Changes made elsewhere since (the Browser sidebar, automatic Done)
are left alone.

### Settings

**⋯ → Settings…** in the Tag Queue window (Anki's **Config** button for the
add-on opens the same thing) covers the daily limit and what counts toward
it, unsuspending on check-off, which top-level tags hold your resources
(with a live list of what each pattern matches), pinned resources, the
deck-screen meter, the keyboard shortcut (press the keys to record it), and
the queued/done/later colours used here and in the Browser sidebar. Changes
apply when you save; there's no JSON to edit.

## Installation

### From AnkiWeb

Search for "Tag Queue" in Anki's **Tools → Add-ons → Get Add-ons**.

### Manual

Download `anki-tag-queue.ankiaddon` from the
[Releases](https://github.com/AIbrahimv2/AnkiTagQueue/releases) page and
double-click it, or run `./build.sh` and open the file it writes to `dist/`.

## Development

The add-on that Anki loads lives entirely in `src/`. To test changes live,
symlink `src/` into your Anki add-ons folder and restart Anki:

```bash
ln -s "$(pwd)/src" ~/Library/Application\ Support/Anki2/addons21/anki-tag-queue
```

The window's UI is a React + TypeScript app in `web/`, built with Vite into
`src/web/app.js` and `src/web/app.css` (committed, so the add-on works straight
from a checkout). It talks to Python through Anki's `pycmd` bridge:
`src/bridge.py` handles the commands, and `src/viewmodel.py` shapes the data.

```bash
cd web && npm install
npm run build        # rebuild src/web/ after changing the UI
```

To work on the UI with live reload and **real data**, run the dev server. It
uses Anki's own Python to serve the real bridge against a temporary copy of a
collection, then start Vite:

```bash
PY=~/Library/Application\ Support/AnkiProgramFiles/python/cpython-3.13.5-macos-aarch64-none/bin/python3
"$PY" tools/devserver.py --collection ~/Library/Application\ Support/Anki2/User\ 1/collection.anki2
cd web && npm run dev   # http://localhost:5173 (add ?theme=dark for dark mode)
```

Run `./build.sh` to build the UI and produce a distributable `.ankiaddon` in
`dist/`.

## License

[AGPL-3.0-or-later](LICENSE).
