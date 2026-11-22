#!/usr/bin/env python3
"""Release an add-on, everything but AnkiWeb's Save button.

    release.py [repo]                 # dry run: checks, tests, the version and notes, a test build
    release.py [repo] --publish       # release it: changelog, build, check, push, tag, GitHub release
    release.py [repo] --uploaded      # after saving on AnkiWeb: record the version there

--publish turns `## [Unreleased]` into the next version (features bump the
minor version, fixes alone the patch; --version picks one), commits it,
builds and checks the package, pushes main and the tag, creates the GitHub
release with notes from the changelog, and checks GitHub serves the same
file. Then it says what to do on AnkiWeb, and run from a terminal it opens
the update page and shows the package in Finder, for dragging onto Choose
File. If a step fails, fix it and run --publish again: it picks up where it
stopped.

The upload itself stays in the browser: AnkiWeb's terms don't allow other
clients, and its staff have said scripts calling its upload form break them
(https://forums.ankiweb.net/t/authentication-with-ankiweb-for-add-on-deploy-from-github/40999).
A public upload API is requested in https://github.com/ankitects/anki/issues/4869.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from addons import (
    KIT, LISTING, SCRIPTS, Addon, ankiweb_record, git, installed_anki, load, next_version, on_mac, ssh_mac, MAC_HOST,
    record_upload, release_changelog, release_notes,
)


class Stop(Exception):
    """A check failed: say why and stop."""


def say(msg: str) -> None:
    print(msg, flush=True)


def step(msg: str) -> None:
    say(f"\n▸ {msg}")


def sh(cmd: list[str], cwd: Path, quiet: bool = False) -> str:
    """Run a command, showing it; stop if it fails."""
    say("  $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if not quiet and r.stdout.strip():
        say("\n".join("    " + line for line in r.stdout.strip().splitlines()[-12:]))
    if r.returncode:
        tail = (r.stderr.strip() or r.stdout.strip()).splitlines()[-15:]
        raise Stop(f"`{' '.join(cmd)}` failed (exit {r.returncode}):\n" + "\n".join("    " + l for l in tail))
    return r.stdout


def commit(addon: Addon, path: str, message: str, co_author: str | None) -> None:
    if co_author:
        message += f"\n\nCo-Authored-By: {co_author}"
    sh(["git", "add", "--", path], addon.path)
    sh(["git", "commit", "-q", "-m", message, "--", path], addon.path)


# --- checks ------------------------------------------------------------------------


def porcelain(addon: Addon) -> str:
    """`git status --porcelain`, keeping each line's leading space."""
    return subprocess.run(["git", "status", "--porcelain"], cwd=addon.path, capture_output=True, text=True).stdout.rstrip()


def preflight(addon: Addon, fetch: bool) -> None:
    step("Checking the repo")
    branch = git(addon.path, "branch", "--show-current")
    if branch != "main":
        raise Stop(f"on branch {branch!r}: releases go from main")
    dirty = porcelain(addon)
    if dirty:
        raise Stop("uncommitted changes (anything in src/ would ship): commit or set them aside first\n" + dirty)
    if fetch:
        sh(["git", "fetch", "--quiet", "origin"], addon.path)
    behind = git(addon.path, "rev-list", "--count", "HEAD..@{u}", check=False) or "0"
    if behind != "0":
        raise Stop(f"{behind} commits behind origin: pull first")
    if (addon.path / "src" / "kit").exists() and KIT.exists():
        r = subprocess.run([sys.executable, str(KIT / "sync.py"), "--check", str(addon.path)], capture_output=True, text=True)
        if r.returncode:
            raise Stop("the kit copy is behind: sync it and commit that as build(kit): ... first\n" + r.stdout)
    say("  clean, up to date, kit current")


def run_tests(addon: Addon, skip: bool) -> None:
    tests = addon.path / "tests" / "run.sh"
    if not tests.exists():
        return
    step("Running the tests")
    if skip:
        say("  skipped (--skip-tests)")
        return
    sh(["./tests/run.sh"], addon.path)


def build(addon: Addon) -> Path:
    step("Building and checking the package")
    for cache in (addon.path / "src").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    sh(["./build.sh"], addon.path, quiet=True)
    pkg = addon.path / addon.package
    sh([sys.executable, str(SCRIPTS / "check_package.py"), str(pkg), "src"], addon.path)
    if porcelain(addon):
        raise Stop("the build changed tracked files (a stale web build?): commit them, then run again\n"
                   + porcelain(addon))
    say(f"  {addon.package}, {pkg.stat().st_size / 1024:.0f} KB")
    return pkg


# --- the release ---------------------------------------------------------------------


def plan(addon: Addon, version: str | None) -> tuple[str, dict, bool]:
    """(version, its changelog entry, whether the changelog still says
    Unreleased). A versioned but untagged release (a run that stopped
    halfway) is picked up again."""
    if addon.unreleased_items:
        v = version or next_version(addon.latest, addon.unreleased)
        if addon.tag_exists(v):
            raise Stop(f"v{v} is already tagged: pass --version")
        return v, addon.unreleased, True
    if addon.latest and not addon.tag_exists(addon.latest):
        release = next(r for r in addon.releases if r["version"] == addon.latest)
        return addon.latest, release, False
    raise Stop(f"nothing to release: no changes under Unreleased, and v{addon.latest} is tagged")


def github(addon: Addon, version: str, release: dict, pkg: Path) -> None:
    tag = f"v{version}"
    step("Publishing on GitHub")
    sh(["git", "push", "origin", "main"], addon.path)
    if not addon.tag_exists(version):
        sh(["git", "tag", "-a", tag, "-m", tag], addon.path)
    sh(["git", "push", "origin", tag], addon.path)
    with tempfile.TemporaryDirectory() as tmp:
        notes = Path(tmp) / "notes.md"
        notes.write_text(release_notes(addon, release), encoding="utf-8")
        exists = subprocess.run(["gh", "release", "view", tag, "-R", addon.github], capture_output=True).returncode == 0
        if not exists:
            sh(["gh", "release", "create", tag, str(pkg), "-R", addon.github, "--verify-tag",
                "--title", tag, "--notes-file", str(notes)], addon.path)
        else:
            say(f"  the {tag} release exists; replacing its package with this build")
            sh(["gh", "release", "upload", tag, str(pkg), "-R", addon.github, "--clobber"], addon.path)
        sh(["gh", "release", "download", tag, "-R", addon.github, "-p", pkg.name, "-D", tmp, "--clobber"], addon.path)
        if not filecmp.cmp(Path(tmp) / pkg.name, pkg, shallow=False):
            raise Stop("GitHub's copy of the package differs from dist/")
    say(f"  https://github.com/{addon.github}/releases/tag/{tag}")


def ankiweb_handoff(addon: Addon, version: str, pkg: Path, interactive: bool, co_author: str | None) -> None:
    step("AnkiWeb (in the browser)")
    if not addon.ankiweb:
        say("  Not on AnkiWeb yet: upload it as a new add-on at https://ankiweb.net/shared/upload,\n"
            "  then add its ID to the kit's catalog.json and the skill's table.")
        return
    url = f"https://ankiweb.net/shared/upload?id={addon.ankiweb}"
    anki = installed_anki()
    pick = str(pkg)
    if not on_mac():  # the browser is on the Mac: copy the package to its home folder
        r = ssh_mac("mkdir", "-p", "ankiweb-upload")
        if r and r.returncode == 0 and subprocess.run(
                ["scp", "-q", "-o", "BatchMode=yes", str(pkg), f"{MAC_HOST}:ankiweb-upload/"]).returncode == 0:
            pick = f"~/ankiweb-upload/{pkg.name} on the Mac"
        else:
            say(f"  (Couldn't copy the package to the Mac over SSH: copy {pkg} there yourself.)")
    say(f"  1. Open {url} (sign in if asked).")
    say(f"  2. Choose File: {pick}")
    say("     (Cmd+Shift+G in the file dialog takes a path, or drag the file from Finder onto the button.)")
    if anki:
        say(f"  3. Supported versions: the maximum should be {anki}, the Anki installed here, with no '-'.")
    say("  4. Save, then check the listing says it was updated today.")
    if not interactive:
        say(f"  Then record it: release.py {addon.path} --uploaded")
        return
    subprocess.run(["open", url])
    subprocess.run(["open", "-R", str(pkg)])
    answer = input("\n  Saved on AnkiWeb? Record it [y/N] ").strip().lower()
    if answer == "y":
        record(addon, version, co_author)
    else:
        say(f"  Not recorded. After saving: release.py {addon.path} --uploaded")


def record(addon: Addon, version: str, co_author: str | None) -> None:
    path = addon.path / LISTING
    if not path.exists():
        raise Stop(f"no {LISTING} to record it in")
    today = date.today().isoformat()
    path.write_text(record_upload(path.read_text(encoding="utf-8"), version, today), encoding="utf-8")
    commit(addon, LISTING, f"docs(listing): record {version} on AnkiWeb", co_author)
    say(f"  recorded: AnkiWeb has {version}, uploaded {today} (committed, not pushed)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repo", nargs="?", default=".", help="the add-on's repo (default: here)")
    p.add_argument("--publish", action="store_true", help="release it (pushes and publishes on GitHub)")
    p.add_argument("--uploaded", action="store_true", help="record that AnkiWeb has the newest version")
    p.add_argument("--version", help="release this version instead of the next one")
    p.add_argument("--skip-tests", action="store_true")
    p.add_argument("--no-fetch", action="store_true", help="don't fetch origin before checking")
    p.add_argument("--co-author", help='add "Co-Authored-By: <this>" to the commits it makes')
    args = p.parse_args()

    addon = load(Path(args.repo))
    say(f"{addon.emoji} {addon.name} ({addon.path})".strip())
    try:
        if args.uploaded:
            version = args.version or addon.latest
            if not version or not addon.tag_exists(version):
                raise Stop(f"v{version} isn't tagged: release it first")
            had = ankiweb_record(addon)
            if had and had[0] == version:
                say(f"  already recorded: AnkiWeb has {version} (uploaded {had[1]})")
                return 0
            record(addon, version, args.co_author)
            return 0

        version, release, unreleased = plan(addon, args.version)
        preflight(addon, fetch=not args.no_fetch)
        say(f"\nVersion {version} (now {addon.latest or 'unreleased'}), with these notes:\n")
        say("\n".join("    " + line for line in release_notes(addon, release).splitlines()))
        run_tests(addon, args.skip_tests)

        if not args.publish:
            pkg = build(addon)
            step("Dry run: nothing committed or published")
            say(f"  --publish would release {version}: commit the changelog, rebuild, push main,\n"
                f"  tag v{version}, and create the GitHub release with {pkg.name}.")
            return 0

        if unreleased:
            step(f"Versioning the changelog as {version}")
            text = (addon.path / "CHANGELOG.md").read_text(encoding="utf-8")
            (addon.path / "CHANGELOG.md").write_text(release_changelog(text, version, date.today().isoformat()), encoding="utf-8")
            commit(addon, "CHANGELOG.md", f"docs(changelog): release {version}", args.co_author)
        pkg = build(addon)
        github(addon, version, release, pkg)
        ankiweb_handoff(addon, version, pkg, sys.stdin.isatty(), args.co_author)
        return 0
    except Stop as e:
        say(f"\n✗ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
