# AnkiWeb listing

What's in the AnkiWeb add-on form (https://ankiweb.net/shared/upload?id=1949793886).

How AnkiWeb's add-on search behaves, tested in November 2026:

- It looks for the exact phrase, in order, in the title, description and tags.
  Partial words match too ("study plan" finds "study planner"), but "unsuspend
  anking" doesn't find "unsuspend relevant AnKing cards". So the wording people
  would type needs to appear literally.
- Tags don't show on the page, but they're searched as one line, so neighbouring
  tags work as a phrase. Their order matters.
- Words only decide whether an add-on appears. Results are ordered by ratings,
  and nothing here changes that.

## Title

🪜 Stepwise: unsuspend AnKing one topic at a time

## Tags

anking unsuspend cards study planner usmle comlex step1 medical school checklist queue tags planning

## Description

A study planner for AnKing and other medical school decks. Tick the topics you're covering today (a Boards and Beyond video, a Pixorize set, a First Aid chapter) and Stepwise shows how many new cards that adds against your daily new card limit. When you've covered a topic, check it off and its cards are unsuspended.

Unsuspend by tag without opening the Browser. Built for the AnKing Step 1 / Step 2 / Step 3 decks for USMLE and COMLEX, and works with any deck that uses hierarchical tags.

- Tag tree by resource: B&B, Bootcamp, Pixorize, Sketchy, Pathoma, First Aid, Physeo, Osmosis, OME, Ninja Nerd, Dirty Medicine, AMBOSS, UWorld, NBME and the rest, showing the cards left to unsuspend and a progress bar per topic.
- A meter of today's new cards. It follows Bury new siblings, so a note with three clozes counts once, the way Anki will show it.
- Search across every resource, then queue all matches in one click.
- Save topics for later when they don't fit today; fill the queue from them next time, oldest first.
- Topics move to Done by themselves once every card in them is studied.
- Undo, vim-style keys, light and dark mode, a meter on the deck screen.
- Works with Colorful Tags: queued topics turn orange and done ones green in the Browser sidebar, and your existing colours can be imported.

Open it from Tools → Stepwise (Cmd/Ctrl+Shift+S). Your queue is saved in your collection, so it syncs with it.

Source, changelog and issues: [github.com/AIbrahimv2/AnkiStepwise](https://github.com/AIbrahimv2/AnkiStepwise)
