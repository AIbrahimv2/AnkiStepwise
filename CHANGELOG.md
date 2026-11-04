# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Initial version.
- **Tag Queue window** (Tools → Tag Queue, Cmd/Ctrl+Alt+Q), a React web UI
  that follows Anki's light and dark themes. It has a tag tree grouped by
  resource with checkboxes to queue topics, new and total card counts,
  per-resource progress bars, search with highlighted matches, a right-click
  menu, toasts, and keyboard navigation (↑/↓, ←/→, Space to queue, / to
  search).
- **Later** status for topics that don't fit this session: save from the tree
  (bookmark button or **L**), the right-click menu, the Browser sidebar, the
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
