# Tag Queue

An [Anki](https://apps.ankiweb.net/) add-on for planning study sessions by tag.
Tick the topics you'll cover today, grouped by resource (B&B, Bootcamp,
Pixorize, Sketchy, …). A live meter shows how many **new cards** that adds
against your session limit. When you've watched the videos, mark the topics
completed, which also unsuspends their cards.

It's built for the AnKing workflow of "watch the video, unsuspend its cards",
and works with any hierarchical tags.

## Features

- **Tag tree by resource.** Every tag is listed under its resource, with
  checkboxes to queue topics and columns for new cards, total cards and progress
  (e.g. `43/51 done`).
- **Keyword search.** Type `brainstem` or `b&b cardio` to see matching topics
  from every resource, nested under the resource they belong to. A dropdown next
  to the search box limits the tree and the search to **all resources**, your
  **pinned resources**, or a **single resource**.
- **Queue all matches.** One click queues every topic the search found that
  isn't already queued or completed. Before you click, it shows how many new
  cards that adds, and it asks first if the total would go over your limit.
- **Unique-card meter.** The queue counts each card once, even when it's tagged
  under several queued topics (common in AnKing, where one card carries B&B,
  Bootcamp and Pixorize tags). Select a topic to see how many cards it *would
  add* before you queue it.
- **Session limit.** 150 cards by default. The meter and count turn red when the
  queue goes over.
- **Complete in one click.** ✓ on a queued topic (or **Complete all**) marks it
  done and unsuspends its cards. Completed topics move to the **Completed** tab
  with the date, and you can send them back to the queue.
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
2. Expand a resource and tick the topics you plan to watch. Ticking a parent
   queues everything under it. Or search for a keyword, pick the resource you're
   watching from the dropdown, and click **Queue N** to queue every match. Keep
   the meter under your limit.
3. Watch the videos, then click **✓** on each topic, or **Complete all**. Their
   cards are unsuspended and the topics are marked completed.

Right-click a topic for more: browse its cards, unsuspend without completing,
clear its status, or pin a resource to the top.

## Installation

### From AnkiWeb

Search for "Tag Queue" in Anki's **Tools → Add-ons → Get Add-ons**.

### Manual

Download `anki-tag-queue.ankiaddon` from the
[Releases](https://github.com/AIbrahimv2/AnkiTagQueue/releases) page and
double-click it, or run `./build.sh` and open the file it writes to `dist/`.

## Development

The add-on lives entirely in `src/`. To test changes live, symlink `src/` into
your Anki add-ons folder and restart Anki:

```bash
ln -s "$(pwd)/src" ~/Library/Application\ Support/Anki2/addons21/anki-tag-queue
```

Run `./build.sh` to produce a distributable `.ankiaddon` in `dist/`.

## License

[AGPL-3.0-or-later](LICENSE).
