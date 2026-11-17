"""What the release scripts know about the user's add-ons: where each repo
is, its catalog entry (name, AnkiWeb ID), its changelog, its package, and
which version AnkiWeb has, as recorded in docs/ankiweb-listing.md.

Used by release_status.py and release.py. The add-on repos sit side by side
(~/Documents/Projects on the user's Mac, found from where this file lives);
set ANKI_PROJECTS to look elsewhere.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# scripts/ -> anki-addon-release/ -> skills/ -> .claude/ -> anki-stepwise/ -> Projects/
PROJECTS = Path(os.environ.get("ANKI_PROJECTS") or SCRIPTS.parents[4])
KIT = PROJECTS / "anki-addon-kit"

LISTING = "docs/ankiweb-listing.md"
RECORD_HEADING = "## Package on AnkiWeb"
_RECORD = re.compile(
    r"^## Package on AnkiWeb\s*\n\s*\nVersion (?P<version>[^\s,]+), uploaded (?P<date>\d{4}-\d{2}-\d{2})\.",
    re.M,
)
# Keep a Changelog headings whose changes count as features (a minor
# release); only Fixed and Security make a patch release.
PATCH_ONLY = {"fixed", "security"}


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", *args], repo, check).stdout.strip()


@dataclass
class Addon:
    path: Path
    id: str
    name: str
    emoji: str
    github: str
    ankiweb: int | None
    package: str  # dist/<name>.ankiaddon, relative to path
    releases: list[dict] = field(default_factory=list)

    @property
    def latest(self) -> str | None:
        return next((r["version"] for r in self.releases if r["version"]), None)

    @property
    def unreleased(self) -> dict | None:
        r = self.releases[0] if self.releases else None
        return r if r and r["version"] is None else None

    @property
    def unreleased_items(self) -> list[tuple[str, str]]:
        """(section title, item) for each change under Unreleased."""
        r = self.unreleased
        return [(s["title"], item) for s in r["sections"] for item in s["items"]] if r else []

    def tag_exists(self, version: str) -> bool:
        return run(["git", "rev-parse", "-q", "--verify", f"refs/tags/v{version}"], self.path, check=False).returncode == 0


def _changelog_module(repo: Path):
    """The kit's changelog parser, the one What's new uses."""
    for path in (repo / "src" / "kit" / "changelog.py", KIT / "py" / "changelog.py"):
        if path.exists():
            spec = importlib.util.spec_from_file_location(f"changelog_{repo.name}", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise SystemExit(f"{repo.name}: no changelog parser (src/kit/changelog.py)")


def parse_changelog(repo: Path) -> list[dict]:
    return _changelog_module(repo).parse((repo / "CHANGELOG.md").read_text(encoding="utf-8"))


def _catalog() -> list[dict]:
    for path in [KIT / "catalog.json", *sorted(PROJECTS.glob("*/src/kit/catalog.json"))]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["addons"]
    return []


def _package(repo: Path) -> str:
    m = re.search(r'^OUT="([^"]+)"', (repo / "build.sh").read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit(f"{repo.name}: build.sh has no OUT=\"dist/....ankiaddon\" line")
    return m.group(1)


def is_addon_repo(path: Path) -> bool:
    return all((path / p).exists() for p in ("build.sh", "CHANGELOG.md", "src/manifest.json"))


def load(repo: Path) -> Addon:
    repo = repo.resolve()
    if not is_addon_repo(repo):
        raise SystemExit(f"{repo} isn't an add-on repo (build.sh, CHANGELOG.md and src/manifest.json)")
    origin = git(repo, "remote", "get-url", "origin", check=False)
    entry = next((a for a in _catalog() if a["github"].lower() in origin.lower()), None)
    if entry is None:
        manifest = json.loads((repo / "src" / "manifest.json").read_text(encoding="utf-8"))
        entry = {"id": repo.name, "name": manifest.get("name", repo.name), "emoji": "", "github": "", "ankiweb": None}
    return Addon(
        path=repo,
        id=entry["id"],
        name=entry["name"],
        emoji=entry.get("emoji", ""),
        github=entry.get("github", ""),
        ankiweb=entry.get("ankiweb"),
        package=_package(repo),
        releases=parse_changelog(repo),
    )


def all_addons() -> list[Addon]:
    return [load(p) for p in sorted(PROJECTS.iterdir()) if p.is_dir() and is_addon_repo(p)]


# --- versions ------------------------------------------------------------------------


def version_key(v: str | None) -> tuple:
    if not v:
        return ()
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.-]", v))


def next_version(latest: str | None, unreleased: dict | None) -> str:
    """Features bump the minor version; fixes alone bump the patch."""
    if not latest:
        return "1.0.0"
    major, minor, patch = (list(version_key(latest)) + [0, 0, 0])[:3]
    titles = {s["title"].strip().lower() for s in (unreleased or {}).get("sections", []) if s["items"]}
    if titles and titles <= PATCH_ONLY:
        return f"{major}.{minor}.{patch + 1}"
    return f"{major}.{minor + 1}.0"


def release_changelog(text: str, version: str, date: str) -> str:
    """Rename the Unreleased heading to the version, in the file's style
    (`## [1.2.0] - date` or `## 1.2.0 - date`)."""
    m = re.search(r"^##[ \t]+(\[)?unreleased\]?[ \t]*$", text, re.M | re.I)
    if not m:
        raise ValueError("no Unreleased heading in CHANGELOG.md")
    heading = f"## [{version}] - {date}" if m.group(1) else f"## {version} - {date}"
    return text[: m.start()] + heading + text[m.end():]


def release_notes(addon: Addon, release: dict) -> str:
    """GitHub release notes: the version's changes, then how to install it."""
    out: list[str] = []
    for s in release["sections"]:
        if not s["items"]:
            continue
        if s["title"]:
            out += [f"### {s['title']}", ""]
        out += [f"- {item}" for item in s["items"]] + [""]
    pkg = Path(addon.package).name
    install = f"**Install:** download `{pkg}` below and double-click it"
    if addon.ankiweb:
        install += f", or get it from [AnkiWeb](https://ankiweb.net/shared/info/{addon.ankiweb}) with the code {addon.ankiweb}"
    out.append(install + ".")
    return "\n".join(out) + "\n"


# --- what AnkiWeb has --------------------------------------------------------------------


def ankiweb_record(addon: Addon) -> tuple[str, str] | None:
    """(version, date) of the package last uploaded to AnkiWeb, as recorded."""
    path = addon.path / LISTING
    if not path.exists():
        return None
    m = _RECORD.search(path.read_text(encoding="utf-8"))
    return (m.group("version"), m.group("date")) if m else None


def record_upload(text: str, version: str, date: str) -> str:
    """docs/ankiweb-listing.md with the package on AnkiWeb set to `version`."""
    line = f"Version {version}, uploaded {date}."
    m = _RECORD.search(text)
    if m:
        return text[: m.start("version") - len("Version ")] + line + text[m.end():]
    section = (
        f"{RECORD_HEADING}\n\n{line} The release script (`release.py --uploaded`\n"
        "in the `anki-addon-release` skill) updates this line after each upload.\n\n"
    )
    first = re.search(r"^## ", text, re.M)
    if not first:
        return text.rstrip("\n") + "\n\n" + section.rstrip("\n") + "\n"
    return text[: first.start()] + section + text[first.start():]


def installed_anki() -> str | None:
    """The Anki installed on this Mac, as AnkiWeb writes it (26.9.4 -> 26.09.4)."""
    pkgs = Path("/Applications/Anki.app/Contents/Resources/app_packages")
    for p in sorted(pkgs.glob("aqt-*.dist-info")) if pkgs.exists() else []:
        parts = p.name[len("aqt-"): -len(".dist-info")].split(".")
        if len(parts) == 3 and all(x.isdigit() for x in parts):
            return f"{parts[0]}.{int(parts[1]):02d}.{parts[2]}"
    return None
