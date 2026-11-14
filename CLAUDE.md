# Notes for agents

Stepwise is one of AIbrahimv2's Anki add-ons (AnkiWeb ID 1949793886).

- **Releasing, publishing or editing the AnkiWeb listing:** follow the
  `anki-addon-release` skill in `.claude/skills/anki-addon-release/`. It
  covers all of the user's add-ons, and the other add-on repos point here.
- **Tests:** `python3 tests/make_fixture.py` once (a gitignored snapshot of a
  real collection), then `./tests/run.sh`.
- **Building:** `./build.sh` builds the web UI into `src/web/` and the
  package into `dist/stepwise.ankiaddon`.
- **Trying the UI:** `tools/devserver.py` serves it in a browser against a
  copy of a collection. The README's Development section has the commands.
- **Shared kit:** `src/kit/` and `web/src/kit/` are copies of `../anki-addon-kit` (the
  theme, the controls, the Settings / What's new / About dialog and the
  notice after updates). Don't edit them here: change the kit and run its
  `sync.py`; `build.sh` warns when they're behind. `build.sh` puts
  `CHANGELOG.md` in the package, where What's new shows it to users, so
  write it in their terms.
