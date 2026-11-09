---
name: anki-addon-release
description: Release, publish or update one of the user's Anki add-ons (Stepwise, Exam Timeline, AnkiGlass, AnkiBare, or a new one), and look after its listings. Covers versioning and the changelog, building and checking the .ankiaddon, the GitHub release, uploading to AnkiWeb and editing the listing (title, tags, description, screenshot), and checking how it shows up in AnkiWeb search. Use in any Anki add-on repo (src/manifest.json plus build.sh) whenever the user says publish, release, ship, upload to AnkiWeb, update the listing, or improve its search ranking.
---

# Releasing the user's Anki add-ons

The user (GitHub AIbrahimv2) publishes several Anki add-ons on GitHub and
AnkiWeb, built the same way. This is how a release goes, what's easy to get
wrong, and the two helper scripts in `scripts/`.

## The add-ons

| Add-on | Local repo | GitHub | AnkiWeb ID | Package |
| --- | --- | --- | --- | --- |
| 🪜 Stepwise | `~/Documents/Projects/anki-tag-queue` | AIbrahimv2/AnkiStepwise | 1949793886 | `dist/stepwise.ankiaddon` |
| 📅 Exam Timeline | `~/Documents/Projects/anki-exam-timeline` | AIbrahimv2/AnkiExamTimeline | 341595498 | `dist/anki-exam-timeline.ankiaddon` |
| 🫧 AnkiGlass | `~/Documents/Projects/anki-glass` | AIbrahimv2/AnkiGlass | 1866406123 | `dist/anki-glass.ankiaddon` |
| 🐻 AnkiBare | not checked out | AIbrahimv2/AnkiBare | 1505882046 | |

The signed-in list of the user's items is https://ankiweb.net/shared/mine.
Add a row here when a new add-on is published, and fix rows that drift.

**Where this skill lives:** in the AnkiStepwise repo, at
`.claude/skills/anki-addon-release/`. On the user's Mac,
`~/.claude/skills/anki-addon-release` is a symlink to it, so every local
session sees it. The other add-on repos have a `CLAUDE.md` pointing here for
cloud sessions. Edit it in the Stepwise repo and push, so both stay current.

## Ground rules

- **Main only.** Commit straight to main; never create branches. Conventional
  Commits (`type(scope): subject`) with a body for anything non-trivial, one
  concern per commit, ending with the Co-Authored-By trailer. Push only as
  part of a release, or when the user asks.
- **Publishing needs the user's go-ahead** ("publish", "release", "yes,
  upload it"). Pushing tags, `gh release create` and saving on AnkiWeb are
  public. A permission check may block `gh repo create` or `gh release create`
  until the user has said so in their own words. If it still blocks, give
  them the exact commands to run.
- **The user signs in and picks files.** You can't type AnkiWeb passwords, and
  the built-in browser can't choose a file for an upload. Fill in everything
  else, then ask the user to sign in in the browser pane and click **Choose
  File**. Give them the path, and tell them Cmd+Shift+G opens it in the
  dialog.
- **No personal data in anything public.** `src/meta.json` holds the user's own
  settings: it must stay gitignored and out of the package. Collection
  snapshots for tests stay in gitignored folders (Stepwise: `tests/fixture/`).
- **Lasting tests and tools go in the repo**, never in a `/private/tmp`
  scratchpad, which gets cleaned within days.
- **UI copy:** no "·" separators. Sentence case.

## Release checklist

1. **Start clean.** `git status -sb` shows nothing uncommitted and isn't behind
   origin (pull first if it is). Run the tests if the repo has them
   (Stepwise: `./tests/run.sh`).
2. **Version.** In `CHANGELOG.md` (Keep a Changelog), rename `## [Unreleased]`
   to `## [X.Y.Z] - YYYY-MM-DD`: new features bump the minor version, fixes
   only bump the patch. Commit it as `docs(changelog): release X.Y.Z`. Check
   the date with `date +%F`.
3. **Build.** `find src -name __pycache__ -exec rm -rf {} +`, then `./build.sh`.
   It zips the *contents* of `src/` (no parent folder; AnkiWeb rejects one)
   and leaves out `__pycache__`, `*.pyc`, `meta.json`, `user_files/` and
   `.DS_Store`. Stepwise builds its web UI first.
4. **Check the package.**
   `python3 ~/.claude/skills/anki-addon-release/scripts/check_package.py dist/<name>.ankiaddon src`
   confirms the layout and that nothing forbidden is inside. It also checks
   that every file git tracks in `src/` is in the package unchanged, and
   that `manifest.json` has `package`, `name` and a `homepage` that exists on
   GitHub.
5. **GitHub.**
   ```bash
   git push origin main
   git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z
   gh release create vX.Y.Z dist/<name>.ankiaddon --verify-tag --title "vX.Y.Z" --notes-file <notes.md>
   gh release download vX.Y.Z -p <name>.ankiaddon -D <scratch> && cmp <scratch>/<name>.ankiaddon dist/<name>.ankiaddon
   ```
   Write the notes in a scratch file: Added, Changed and Fixed, in the user's
   terms, then an install line. For example: "**Install:** download
   `<name>.ankiaddon` below and double-click it, or get it from
   [AnkiWeb](https://ankiweb.net/shared/info/<ID>) with the code <ID>."
6. **AnkiWeb.** Upload the same package (see below).
7. **Report.** Give the links, what you checked, and what you couldn't. For
   example, the listing's "0.13MB" can't tell two builds apart.

## AnkiWeb

| Page | URL |
| --- | --- |
| Update an add-on | `https://ankiweb.net/shared/upload?id=<ID>` |
| Upload a new one | `https://ankiweb.net/shared/upload` |
| The live listing | `https://ankiweb.net/shared/info/<ID>` |
| The user's items | `https://ankiweb.net/shared/mine` |

**Flow, in the built-in browser:**
1. Open the update page. If it redirects to `/account/login`, the pane is
   signed out: ask the user to sign in there.
2. Fill in the fields with `form_input`, then read the whole form back with
   JS. Check the title, tags, support page, versions, description, and the
   chosen file's name and size against `dist/`.
3. Ask the user to choose the file. Press **Save** only once they've said to.
4. Saving lands on `/shared/info/<ID>?cb=…`. There, check the title, the
   "Supported Anki versions" line, that images loaded (`naturalWidth > 0`),
   and that links can be clicked.

**Things to know:**
- **Description-only edits:** saving with no file chosen changes only the
  text. The package stays as it was.
- **Clipboard:** the listing page copies its install code to the clipboard
  when it loads. Tell the user, so it doesn't surprise them.
- **Versions:** each branch has a minimum and maximum Anki version. Use the
  version the add-on was tested on for both, which lists as "26.09.4+". The
  installed version is in the folder name from `ls
  /Applications/Anki.app/Contents/Resources/app_packages | grep aqt-`: 26.9.4
  means "26.09.4". A `-` before the maximum blocks newer versions. Don't keep
  the form's default 2.1.1: it offers the add-on to Anki versions it was never
  tested on.
- **Keep the listing in the repo.** Store the title, tags, support page and
  description in `docs/ankiweb-listing.md`, and update it in the same session
  as any change on AnkiWeb, so the next edit starts from what's live.

## Listing conventions

- **Title:** an emoji, then "Name: lowercase descriptor", under 80
  characters. For example "🪜 Stepwise: unsuspend AnKing one topic at a time"
  or "🫧 AnkiGlass: native macOS Liquid Glass for Anki". Avoid clunky
  qualifiers like "within a daily new-card limit": they belong in the
  description.
- **Support page:** the GitHub issues URL.
- **Description:** Markdown and basic HTML.
  - Bare URLs aren't clickable, so write
    `[github.com/AIbrahimv2/<Repo>](https://github.com/AIbrahimv2/<Repo>)`.
  - Put an image on its own as
    `<p><img src="https://raw.githubusercontent.com/AIbrahimv2/<Repo>/main/docs/screenshot.png" alt="…" width="100%"></p>`.
    Without the `<p>`, AnkiWeb leaves it inline and the next paragraph or list
    starts with no gap.
  - Use the same `docs/screenshot.png` in the README, so replacing one file
    updates both.

## AnkiWeb search

Tested on 2026-11-09:
- **Exact phrases:** search looks for the query as an exact phrase in the
  title, description and tags. "unsuspend anking" doesn't match "unsuspend
  relevant AnKing cards". Partial words do match: "study plan" finds "study
  planner".
- **Tags:** they're searched as one line, so neighbouring tags work as a
  phrase. They don't show on the page.
- **Order:** results are sorted by ratings. Wording decides *whether* an
  add-on shows up, not its rank. A new add-on with no ratings comes after
  nearly every rated match.

**To check where an add-on shows up:**
```bash
python3 ~/.claude/skills/anki-addon-release/scripts/ankiweb_search.py --id <ID> "query one" "query two"
```
It prints each query's result count and the add-on's rank. AnkiWeb returns
HTTP 429 when queried quickly, so the script waits between queries and retries.

**Choosing terms:** run 20 to 40 queries before and after a listing change,
and put the results in a table for the user. Add the words people would
actually type: the resources and exams the add-on serves (AnKing, B&B, First
Aid, USMLE, COMLEX), the problem it solves (study planner, unsuspend cards),
and common abbreviations. Leave out words for things the add-on doesn't do.
Record what you learn in `docs/ankiweb-listing.md`.

## Screenshots

- **Content:** show the real UI with realistic state, in dark mode (the
  user's own setting) unless they ask otherwise. Render at 2x and commit it
  as `docs/screenshot.png`.
- **Add-ons with a web UI and a dev server:** Stepwise runs
  `tools/devserver.py` on a copy of a collection. Set up the state you want
  through its bridge, then render it with headless Chromium:
  ```bash
  /Applications/Chromium.app/Contents/MacOS/Chromium --headless=new \
    --user-data-dir=<scratch>/chromium-profile --hide-scrollbars \
    --force-device-scale-factor=2 --window-size=1280,800 \
    --virtual-time-budget=12000 --screenshot=<scratch>/shot.png "http://localhost:<port>/?theme=dark"
  ```
- **Native Qt add-ons:** these need a screenshot of the real Anki window. Ask
  for computer-use access to Anki, or ask the user for a screenshot (they may
  decline access).
- **Staging:** only change state in a copy of the collection, never the
  user's real one.

## After a release

- **Two copies:** the user's dev copy is usually symlinked into
  `~/Library/Application Support/Anki2/addons21/`. Installing the AnkiWeb
  copy as well runs two copies at once, and settings are per add-on folder.
- **Checking AnkiWeb's package:** the listing page can't tell you which build
  it's serving. The user can run Tools → Add-ons → Check for Updates in Anki
  and look for something new in the release. Ask before downloading the
  package yourself.
