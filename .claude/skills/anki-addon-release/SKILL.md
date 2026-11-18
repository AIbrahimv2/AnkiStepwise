---
name: anki-addon-release
description: Release, publish or update one of the user's Anki add-ons (Stepwise, Exam Timeline, AnkiGlass, AnkiBare, Skim, or a new one), and look after its listings. Covers what's waiting to be released, versioning and the changelog, building and checking the .ankiaddon, the GitHub release, uploading to AnkiWeb and editing the listing (title, tags, description, screenshot), and checking how it shows up in AnkiWeb search. Use in any Anki add-on repo (src/manifest.json plus build.sh) whenever the user says publish, release, ship, upload to AnkiWeb, what's unreleased, update the listing, or improve its search ranking.
---

# Releasing the user's Anki add-ons

The user (GitHub AIbrahimv2) publishes several Anki add-ons on GitHub and
AnkiWeb, built the same way. This is how changes are tracked until they're
released, how a release goes, what's easy to get wrong, and the helper
scripts in `scripts/`.

## The add-ons

| Add-on | Local repo | GitHub | AnkiWeb ID | Package |
| --- | --- | --- | --- | --- |
| 🪜 Stepwise | `~/Documents/Projects/anki-stepwise` | AIbrahimv2/AnkiStepwise | 1949793886 | `dist/stepwise.ankiaddon` |
| 📅 Exam Timeline | `~/Documents/Projects/anki-exam-timeline` | AIbrahimv2/AnkiExamTimeline | 341595498 | `dist/anki-exam-timeline.ankiaddon` |
| 🫧 AnkiGlass | `~/Documents/Projects/anki-glass` | AIbrahimv2/AnkiGlass | 1866406123 | `dist/anki-glass.ankiaddon` |
| 🐻 AnkiBare | `~/Documents/Projects/anki-bare` | AIbrahimv2/AnkiBare | 1505882046 | `dist/anki-bare.ankiaddon` |
| 👀 Skim | `~/Documents/Projects/anki-skim` | AIbrahimv2/AnkiSkim | not published yet | `dist/skim.ankiaddon` |

The signed-in list of the user's items is https://ankiweb.net/shared/mine.
Add a row here when a new add-on is published, and fix rows that drift.

**The shared kit:** every add-on carries a copy of
`~/Documents/Projects/anki-addon-kit` (`src/kit/`, and `web/src/kit/` for
those with a page): the theme and controls, the Settings / What's new /
About dialog, and the notice after updates. Its `catalog.json` lists the
add-ons for About; when one is published (or its AnkiWeb ID changes), update
it there, bump `updated`, sync, and release an add-on so users see it.

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

## Keeping track of what's unreleased

- **Every change users will notice gets a line under `## [Unreleased]`** in
  the add-on's `CHANGELOG.md`, in their terms, in the session that makes it.
  A kit change gets one in every add-on it's synced into. That's the list a
  release is cut from, and What's new shows it.
- **AnkiWeb's version is recorded** under "Package on AnkiWeb" in each
  `docs/ankiweb-listing.md`. `release.py --uploaded` updates it.
- **To see what's waiting**, for every add-on at once:
  ```bash
  python3 ~/.claude/skills/anki-addon-release/scripts/release_status.py --fetch -v
  ```
  It shows each add-on's newest version, the version AnkiWeb has, the changes
  under Unreleased with the version they'd make, and what needs doing:
  commits since the last tag the changelog doesn't mention, uncommitted or
  unpushed work, a kit copy that's behind, a version without its GitHub
  release, or AnkiWeb behind GitHub. Run it when the user asks what's
  unreleased, and before a release.

## Releasing: release.py

`scripts/release.py` does the checklist below, everything but AnkiWeb's Save:

```bash
R=~/.claude/skills/anki-addon-release/scripts
python3 $R/release.py ~/Documents/Projects/<repo>            # dry run
python3 $R/release.py ~/Documents/Projects/<repo> --publish --co-author "Claude ... <noreply@anthropic.com>"
python3 $R/release.py ~/Documents/Projects/<repo> --uploaded --co-author "..."   # after Save on AnkiWeb
```

- **Dry run** (no flag): checks the repo is clean, on main, not behind origin
  and has a current kit copy; runs `tests/run.sh` if there is one; prints the
  version and the GitHub notes; builds and checks the package. Nothing is
  committed or published. Show the user the version and notes.
- **`--publish`** needs the user's go-ahead (see Ground rules). It versions
  the changelog (features bump the minor version, fixes alone the patch;
  `--version` overrides), commits it, rebuilds, runs `check_package.py`,
  pushes main and the tag, creates the GitHub release, and checks GitHub
  serves the same file. If a step fails, fix it and run `--publish` again:
  an untagged version is picked up where it stopped.
- **AnkiWeb:** it then prints the update page, the package path and the
  Anki version for the form's maximum. From a terminal it opens the page and
  shows the file in Finder, and asks whether to record the upload. Run by
  you, do the upload with the user as in the AnkiWeb section, then run
  `--uploaded` once the listing shows today's date.
- Pass `--co-author` with the trailer from the system prompt when you run it;
  leave it out when the user runs it themselves.

## Release checklist

What `release.py` does, step by step. Follow it by hand where the script
can't run (a cloud session without the sibling repos, say).

1. **Start clean.** `git status -sb` shows nothing uncommitted and isn't behind
   origin (pull first if it is). Run the tests if the repo has them
   (Stepwise: `./tests/run.sh`). `python3 ../anki-addon-kit/sync.py --check .`
   says whether the kit copy is current; if not, sync it (and commit that as
   its own `build(kit): ...` commit) before releasing.
2. **Version.** In `CHANGELOG.md` (Keep a Changelog), rename `## [Unreleased]`
   to `## [X.Y.Z] - YYYY-MM-DD`: new features bump the minor version, fixes
   only bump the patch. The changelog ships in the package and What's new
   shows it to users, and its newest version is the add-on's version, so
   word it for them and never release with changes left under Unreleased. Commit it as `docs(changelog): release X.Y.Z`. Check
   the date with `date +%F`.
3. **Build.** `find src -name __pycache__ -exec rm -rf {} +`, then `./build.sh`.
   It zips the *contents* of `src/` (no parent folder; AnkiWeb rejects one)
   and leaves out `__pycache__`, `*.pyc`, `meta.json`, `user_files/` and
   `.DS_Store`, then adds `CHANGELOG.md` at the top. Stepwise, Skim and Exam
   Timeline build their web UI first.
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

**The upload stays in the browser, with the user.** Don't script it, even if
asked: AnkiWeb's terms ("Access to the Service") don't allow access from
browser extensions or other third-party clients. Its staff have said that
scripts posting to its upload form break them: dae in 2024 on
[the forum](https://forums.ankiweb.net/t/authentication-with-ankiweb-for-add-on-deploy-from-github/40999),
and again in June 2026 about a community GitHub Action
([thread](https://forums.ankiweb.net/t/github-action-to-upload-anki-add-on/70165)).
Breaking the terms puts the account holding every add-on at risk. A public
upload API is requested in
[ankitects/anki#4869](https://github.com/ankitects/anki/issues/4869) (open,
no work on it as of 2026-11-17). When it ships, `release.py` can call it.

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
5. For a new package (not a description-only edit), record it:
   `release.py <repo> --uploaded`.

**Things to know:**
- **Description-only edits:** saving with no file chosen changes only the
  text. The package stays as it was.
- **Caching:** the listing's text comes from `/svc/shared/item-info`, which
  browsers may keep for 10 minutes (`max-age=600`), and images from
  raw.githubusercontent.com, kept for 5. A browser that opened the listing
  just before a save shows the old version for that long. Check a save
  with `?cb=<anything>` on the listing URL, and tell the user a hard
  refresh shows it.
- **Clipboard:** the listing page copies its install code to the clipboard
  when it loads. Tell the user, so it doesn't surprise them.
- **Versions:** each branch has a minimum and maximum Anki version, and the
  minimum decides who can install it. On an older Anki, pasting the code
  fails with "Invalid code, or add-on not available for your version of
  Anki", and people read that as a broken code. Stepwise's listing once
  required the version the user happened to have (26.09.4, five days old),
  and the first review said "Anki says code is invalid".
  - **Minimum:** the oldest version the add-on was tested on, not the
    installed one. Stepwise tests other versions with
    `tests/run_on_anki.sh <version>`. Its listed minimum and the reasons are
    in `docs/ankiweb-listing.md`. Rerun the tests on that version before each
    release.
  - **Maximum:** the installed version, from `ls
    /Applications/Anki.app/Contents/Resources/app_packages | grep aqt-` (26.9.4
    means "26.09.4"). Without a `-` in front, newer versions still get the
    add-on. A `-` blocks them.
  - Don't keep the form's default 2.1.1: it offers the add-on to versions
    nobody tested.
  - After saving, check the listing's "Supported Anki versions" line.
- **Keep the listing in the repo.** Store the title, tags, support page and
  description in `docs/ankiweb-listing.md`, and update it in the same session
  as any change on AnkiWeb, so the next edit starts from what's live.

## Replying to reviews

Reviews show at the bottom of the listing, and recent ones on
https://ankiweb.net/shared/mine with a **Reply** button. Reply opens a box
with a **Save** button. A saved reply is public, shown under the review as
"Comment from author".

- **Get the wording approved.** Draft the reply in the box, show it to the
  user, and press Save only once they've approved it.
- **Praise:** keep it short and plain, for example "Thank you, glad it's
  useful!".
- **Bug reports:** say which version fixes it and how to get it (Tools →
  Add-ons → Check for Updates, then restart Anki). Explain any limitation in
  the user's terms, but not the technical cause of the bug.
- **Check it posted:** reload the listing with `?cb=<anything>` to skip the
  cache, and look for "Comment from author".

## Listing conventions

- **Title:** an emoji, then "Name: lowercase descriptor", under 80
  characters. For example "🪜 Stepwise: unsuspend AnKing one topic at a time"
  or "🫧 AnkiGlass: native macOS Liquid Glass for Anki". Avoid clunky
  qualifiers like "within a daily new-card limit": they belong in the
  description.
- **Support page:** the GitHub issues URL.
- **Description:** Markdown and basic HTML, laid out the same in every
  listing:
  ```markdown
  <What it does, in one or two sentences. A Mac-only add-on says so here.>

  **Code: <ID>.** Paste it in Anki under **Tools → Add-ons → Get Add-ons**. Needs Anki <minimum> or newer<, on a Mac>.

  <p><img src="https://raw.githubusercontent.com/AIbrahimv2/<Repo>/main/docs/screenshot.png" alt="…" width="100%"></p>
  <Or a pair that belongs together: two screens, or **Before** and **After**.>

  <A little more about it, if needed.>

  **Features**

  - …

  <As needed, in this order: how to open and use it, **Settings**,
  **Good to know**, more images.>

  Source, changelog and issues: [github.com/AIbrahimv2/<Repo>](https://github.com/AIbrahimv2/<Repo>)

  <p><img src="https://raw.githubusercontent.com/AIbrahimv2/AnkiAddonKit/main/assets/signature.png" alt="AIbrahimv2" width="180"></p>
  ```
  - Never start the description with an image: the pitch and the code line
    come first. The minimum is the one in "Supported Anki versions".
  - The signature is the kit's (`tools/signature_png.py` renders it), the
    same file in every listing. Once the add-ons page on
    abdelrahmanibrahim.com is live, it links there.
  - Bare URLs aren't clickable, so write
    `[github.com/AIbrahimv2/<Repo>](https://github.com/AIbrahimv2/<Repo>)`.
  - Put an image on its own as
    `<p><img src="https://raw.githubusercontent.com/AIbrahimv2/<Repo>/main/docs/screenshot.png" alt="…" width="100%"></p>`.
    Without the `<p>`, AnkiWeb leaves it inline and the next paragraph or list
    starts with no gap.
  - Use the same `docs/screenshot.png` in the README, so replacing one file
    updates both.
  - With more than one image, make them all the same size and show each at
    `width="100%"` here and in the README, so they line up at one scale.

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

Every add-on's screenshots are made one way, with the kit's shared tools
(`anki-addon-kit/screenshots/shots.py`, whose docstring has the details).
Each add-on has a `tools/screenshots.py` that describes its scenes:

```bash
python3 tools/screenshots.py      # writes docs/*.png
```

| Add-on | Images | Scene |
| --- | --- | --- |
| Exam Timeline | `screenshot.png`, `editor.png` | deck screen with the timeline; the editor (its dev server) |
| Stepwise | `screenshot.png` | its window, from `tests/fixture/` via its dev server |
| AnkiGlass | `screenshot.png`, `review.png` | deck list; a real AnKing card under review (760×690, so it shows whole) |
| AnkiBare | `screenshot.png` | the window with and without its title bar, side by side, labelled Before and After on the image |

- **Look:** Anki's own pages (its markup and stylesheets from Anki.app) in
  dark mode, with AnkiGlass's CSS and glass on the main window, framed as a
  macOS window on macOS Tahoe's dark wallpaper (top-left crop, chosen for
  the contrast of the text over it), at 2x. Add-on windows stay solid, as
  AnkiGlass leaves them. Where AnkiGlass isn't the subject, the image is
  credited "Shown with AnkiGlass" in the README and the listing.
- **Size:** all of one add-on's images are the same size (its largest
  window plus the wallpaper around it), so they're shown at `width="100%"`.
  Main-window shots are 760×622 points, so those add-ons share 1776×1556.
- **Data:** made up (the kit's demo decks), or a copy of a collection, never
  the user's own. AnkiGlass's card is a real AnKing card (note
  1486608813182, goblet cells) with a CC0 image, rendered by Anki from a
  copy of the collection (`shots.export_cards`). For anything public, use
  openly licensed images (the card's credit says so) that show whole, with
  their credit, in the window; avoid clinical photos that are graphic or
  sensitive.
- **Comparisons:** show them as one image, side by side (`Session.side_by_side`),
  with their labels written on it, not as headings above separate images.
- **New add-on:** write its `tools/screenshots.py` on `shots.Session`
  (`main_window`, `capture`, `frames`), copying the closest one above.
- **Native Qt parts** with no page to render: ask for computer-use access to
  Anki, or ask the user for a screenshot.

## After a release

- **Two copies:** the user's dev copy is usually symlinked into
  `~/Library/Application Support/Anki2/addons21/`. Installing the AnkiWeb
  copy as well runs two copies at once, and settings are per add-on folder.
- **Checking AnkiWeb's package:** the listing page can't tell you which build
  it's serving. The user can run Tools → Add-ons → Check for Updates in Anki
  and look for something new in the release. Ask before downloading the
  package yourself.
