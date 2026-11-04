# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Initial version.
- **Tag Queue window** (Tools → Tag Queue, Cmd/Ctrl+Alt+Q). It has a tag tree
  grouped by resource with checkboxes to queue topics, new and total card counts,
  per-resource progress, and search.
- **Resource filter** next to the search box: show and search all resources,
  only pinned resources, or a single resource. The choice is remembered.
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
