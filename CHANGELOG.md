# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Renamed to Stepwise** (from Tag Queue). The window's title bar, the
  deck-screen meter, the Tools menu, the Browser menu and the package
  (`stepwise.ankiaddon`) carry the new name. There's no logo: the name
  alone, as before. The add-on's folder and the key your queue is saved
  under are unchanged, so updating keeps your queue and settings.
- **No header in the window.** The page is all queue: Recount and the ⋯
  menu (Colorful Tags import, Settings) sit at the end of the search
  toolbar, and the title, subtitle and icon are gone (the title bar names
  the window).

- **Jump between search matches**: like vim's `/pattern<Enter>`, Enter
  (Shift+Enter) in the search box goes to the next (previous) match and
  hands the keys to the tree, where `n` / `N` move between matches
  (wrapping around); the bar shows "Match 3 of 47". Esc leaves the search box
  with the results kept; Esc again clears the search.
- The tree remembers which folders are open and which step sections you
  closed, across restarts (kept in the Anki profile).
- **Undo and redo** for changes made in the Stepwise window: `u` or
  Cmd/Ctrl+Z undoes, `Ctrl-r` or Cmd/Ctrl+Shift+Z redoes, up to 50 steps.
  Undoing a check-off also re-suspends the cards it unsuspended (if still
  unstudied), and only what that action changed is put back.

- **Settings** inside the Stepwise window (⋯ → Settings…), replacing the
  JSON config editor: daily limit, count mode, unsuspend on check-off,
  resource-folder patterns with a live preview of what they match, pinned
  resources, the deck-screen meter, a recorded keyboard shortcut, and the
  status colours (swatches or hex). Anki's Config button for the add-on opens
  it too. Saving applies right away: a recount when the count mode or folders
  change, a new shortcut on the Tools menu, and recoloured sidebar tags.

### Changed

- **The new-card count follows sibling burying.** With **Bury new siblings**
  on in a deck's options (as in AnKing's preset), Anki shows one new card per
  note a day, so the meter, each topic's count, "Adds +N" and Fill queue now
  count a note once, leave out buried cards, and leave out notes with a
  sibling due for review today: they count on the day Anki can show them.
  Decks with the option off count every card. A queue row's tooltip says how
  many more come after today, and a topic with nothing until tomorrow says
  so. On one real queue this took the meter from 162 to 140.
- **Narrower windows.** The window can now be as narrow as 440px (it was
  860px). As it narrows, the tree's columns tighten, then Total and then
  Waiting give way and levels indent less, so topic names stay readable; the
  queue panel puts the limit on its own line and slims its footer buttons.
  Below 760px a Topics / Queue switch at the top shows one at a time
  (choosing a topic in the queue, or pressing `/`, goes back to the topics).
  Settings and the import dialog fit the window too.
- The tree's keys work as soon as the window opens (no click first), and
  from anywhere on the page that isn't a text field, button, menu or
  dialog.
- The tree's Status column is down to one thing per row: a progress bar
  (numbers in its tooltip), or a bookmark for Later and a check for Done
  (dates in the tooltip), all ending at one edge. The Queued badge, the queued/Later counts inside folders and
  the 320/507 fractions are gone: the ticked box and the queue panel already
  show those.
- Done now covers topics you never queued or coloured: any tag whose every
  card is studied is marked completed (and turns green with Colorful Tags),
  dated the day its last card was first studied. It applies in resources
  you use (any queued, Later or completed topic), no deeper than the deepest
  one you have there, and only the highest finished tag in each branch. On
  the author's collection that's about 1,950 topics; sweeping every tag
  would have been 17,400, mostly UWorld/AMBOSS question IDs.
- The Done tab loads 100 topics at a time ("Show more"), so replies stay
  small: with 2,000 topics done, each click sent 700 KB before.
- The tag tree uses vim keys: `j`/`k` move, `h`/`l` close or go up / open
  or go in, `gg`/`G` top and bottom, `Ctrl-d`/`Ctrl-u` half a page, `o` opens
  or closes. Save for later moved from `L` to `s`. Arrow keys still work.
- "Watched" is now "checked off" (the meter reads "3/9 checked off", the
  button **Clear checked**), since not every resource is a video.
- Queue and Later show their card counts at the right edge, with each row's
  buttons just left of them.
- The details bar under the tree drops the counts the row already shows
  (suspended, waiting, total) and keeps the clean name, its step and path,
  what queuing it would add, and its status badge.
- The ⋯ menu's option toggles moved into Settings; "Edit config…" is gone
  (it opened the Add-ons window with the main window instead of the add-on
  manager and failed with `'AnkiQt' object has no attribute 'mw'`).

- The queue is a daily plan. ✓ checks a topic off (unsuspending its cards)
  but keeps it in the queue, and the meter counts new cards (never studied,
  suspended or not) across queued and checked-off topics, so checking off doesn't
  shrink it; studying does. Topics leave by themselves once every card is
  studied, and unfinished ones carry over. "Complete all" is replaced by
  **Clear checked**, and checked-off rows can be unchecked.
- `count_mode` defaults to `"new"` (setups that were switched to
  `"suspended"` automatically are moved back once).
- Queue and Later show one number per topic and per resource group, in one
  column labelled **New cards** at the top (the breakdown is in each row's
  tooltip), lined up with the topic's name rather than midway down the row.
- Separate facts are laid out apart instead of strung together with "·": the
  meter, details bar, search bar, Later fill bar, status badges, resource
  picker and toasts (a headline with details underneath).
- Dark mode meets WCAG AA contrast against Anki's real dark theme: faint
  text was 1.6:1 there; text and icons now pass everywhere, including
  hovered and selected rows and toasts.
- Course-order numbers are dropped from tag names everywhere except the main
  tree (`03_Pharmacology` shows as "Pharmacology" in the side panel,
  breadcrumbs, folder labels and toasts). Names that are only a number, like
  UWorld question IDs, are kept.
- Queue and Later are grouped by resource, with topics that share a parent
  folder clustered under it, a unique card count per group, and group buttons
  (complete all / move to Later / move to queue). "Order added" shows the flat
  list.
- Topics whose every card is studied count as done: they show "Done" in the
  tree and progress, and leave Queue/Later automatically (with a note why).
  Topics whose cards are only unsuspended stay in the plan.
- Done rolls up: when everything under a folder is done (completed, or every
  card studied), the folder is marked complete in place of its children's
  entries. It never climbs past a resource. On the author's collection this
  turned 179 Done entries into 117.
- Cards already unsuspended but not studied yet, including ones buried by
  sibling settings, show in a separate **Waiting** column (a ☾ marks buried
  ones) next to **Suspended**, so a topic whose cards are only buried no
  longer looks like it has cards left to unsuspend.
- Clicking a row in Queue, Later or Done reveals that tag in the tree (opens
  its folders, loads enough of a big folder, clears search or a narrower
  resource filter, shows done topics if hidden) instead of needing a
  double-click that searched for it.

### Performance

- Card counts (the meter, "queuing it adds…", search summaries, Fill queue,
  the deck-screen meter) now come from an in-memory index of which cards sit
  under which tag, instead of Anki searches. Anki's `tag:` search runs a regex
  over every note per tag, so a 20-tag queue took ~3 s per click; it now takes
  ~10 ms, and search went from up to ~20 s to ~20 ms.
- Completing/unsuspending finds suspended cards from the index plus one SQL
  check instead of a search.
- The window opens instantly on the last index while a fresh one is built in
  the background (also pre-built a few seconds after Anki starts), and the
  index build itself is faster.
- Folders load 300 children at a time with a "Show more" row (UWorld folders
  hold 4,000+ tags), and off-screen rows skip layout.
- The deck-screen meter updates in place instead of re-rendering the whole deck
  list, and the Browser sidebar redraws its colours only when you switch to it.

### Added

- Initial version.
- **Stepwise window** (Tools → Stepwise, Cmd/Ctrl+Alt+Q), a React web UI
  that follows Anki's light and dark themes. It has a tag tree grouped by
  resource with checkboxes to queue topics, new and total card counts,
  per-resource progress bars, search with highlighted matches, a right-click
  menu, toasts, and keyboard navigation (vim keys, Space to queue, / to
  search).
- **Later** status for topics that don't fit this session: save from the tree
  (bookmark button or **s**), the right-click menu, the Browser sidebar, the
  over-limit warning (**Move to Later**) or a search (**Later** saves every
  match). Later topics don't count toward the limit; **Fill queue** queues the
  oldest ones that fit. They get their own sidebar colour (`later_color`).
- **Step sections**: the tree and search results group resources under
  colour-coded Step 1 / Step 2 / Step 3 headers that stick while scrolling, and
  queue rows show a step chip.
- **Resource filter** next to the search box: show and search all resources,
  your pinned resources, a whole step, or a single resource, grouped by step.
  The choice is remembered.
- **Queue all matches**: one click queues every search match that isn't already
  queued or completed. It previews the new cards that adds, asks for
  confirmation if the total would go over the limit, and is disabled when the
  search hits the 200-match cap.
- **Unique-card meter** against a configurable session limit (150 by default).
  It counts cards shared by several queued topics only once, and shows what a
  selected topic would add before you queue it.
- **Complete** a topic (or all of them) to mark it done and unsuspend its cards.
  Completed topics are listed with their date and can be re-queued.
- **Deck-screen meter** under the deck list (and under Exam Timeline, if
  installed).
- **Browser sidebar** context menu to queue or complete the selected tags.
- **Colorful Tags** integration: queued and completed tags are coloured in the
  sidebar automatically, plus a one-time import of existing colours.
- Queue state is stored in the collection, so it's per profile and syncs.
- `tools/devserver.py` runs the UI in a browser against a copy of a real
  collection, for frontend work with live reload.
