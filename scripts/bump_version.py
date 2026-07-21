#!/usr/bin/env python3
"""Bump feat's single-sourced version and keep the changelog honest.

The version lives in exactly one place — ``feat/__init__.py``'s
``__version__`` — and ``pyproject.toml`` reads it dynamically (see
docs/adr/0004). This script is the supported way to change it: it parses
the current semantic version, applies a bump, rewrites ``__init__.py``,
promotes the ``## [Unreleased]`` changelog section to the new version, and
(optionally) creates the release commit and ``vX.Y.Z`` tag.

Usage:
    python scripts/bump_version.py patch            # 1.0.0 -> 1.0.1
    python scripts/bump_version.py minor            # 1.0.1 -> 1.1.0
    python scripts/bump_version.py major            # 1.1.0 -> 2.0.0
    python scripts/bump_version.py --set 2.3.4      # set explicitly
    python scripts/bump_version.py patch --pre rc.1 # 1.0.1 -> 1.0.2-rc.1
    python scripts/bump_version.py patch --dry-run  # print, change nothing
    python scripts/bump_version.py minor --tag      # also commit + git tag

Exit codes: 0 success · 2 usage error · 3 repository state error.
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INIT_PATH = ROOT / "feat" / "__init__.py"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

_VERSION_RE = re.compile(r'^__version__\s*=\s*"(?P<version>[^"]+)"', re.MULTILINE)
# SemVer 2.0.0 core plus an optional dotted pre-release identifier.
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?$"
)


class VersionError(Exception):
    """Version string or repository state is not workable."""


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    pre: str | None = None

    @classmethod
    def parse(cls, raw: str) -> "SemVer":
        match = _SEMVER_RE.match(raw.strip())
        if not match:
            raise VersionError(
                f"{raw!r} is not a valid semantic version (expected MAJOR.MINOR.PATCH)"
            )
        return cls(
            major=int(match["major"]),
            minor=int(match["minor"]),
            patch=int(match["patch"]),
            pre=match["pre"],
        )

    def bump(self, part: str) -> "SemVer":
        # A bump always clears any pre-release tag; --pre re-adds one.
        if part == "major":
            return SemVer(self.major + 1, 0, 0)
        if part == "minor":
            return SemVer(self.major, self.minor + 1, 0)
        if part == "patch":
            return SemVer(self.major, self.minor, self.patch + 1)
        raise VersionError(f"unknown bump part {part!r}")

    def with_pre(self, pre: str | None) -> "SemVer":
        return SemVer(self.major, self.minor, self.patch, pre)

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        return f"{core}-{self.pre}" if self.pre else core


def read_current_version() -> SemVer:
    text = INIT_PATH.read_text(encoding="utf-8")
    match = _VERSION_RE.search(text)
    if not match:
        raise VersionError(f"no __version__ assignment found in {INIT_PATH}")
    return SemVer.parse(match["version"])


def write_version(new: SemVer) -> None:
    text = INIT_PATH.read_text(encoding="utf-8")
    updated, count = _VERSION_RE.subn(f'__version__ = "{new}"', text)
    if count != 1:
        raise VersionError(f"expected exactly one __version__ line in {INIT_PATH}, found {count}")
    INIT_PATH.write_text(updated, encoding="utf-8")


def update_changelog(new: SemVer, today: str) -> bool:
    """Promote the '## [Unreleased]' section to the new version.

    Returns True if the changelog was rewritten. A missing changelog or a
    missing Unreleased header is a soft skip — versioning still proceeds.
    """
    if not CHANGELOG_PATH.exists():
        return False
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    unreleased = re.compile(r"^##\s*\[Unreleased\]\s*$", re.MULTILINE | re.IGNORECASE)
    match = unreleased.search(text)
    if not match:
        return False
    # Insert a fresh, empty Unreleased section above the promoted release so
    # the next cycle has somewhere to accumulate entries.
    replacement = (
        "## [Unreleased]\n\n"
        f"## [{new}] - {today}"
    )
    updated = text[: match.start()] + replacement + text[match.end():]
    CHANGELOG_PATH.write_text(updated, encoding="utf-8")
    return True


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise VersionError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def ensure_clean_worktree() -> None:
    if _git("status", "--porcelain"):
        raise VersionError(
            "working tree is not clean; commit or stash changes before tagging"
        )


def create_tag(new: SemVer, changed: list[Path]) -> None:
    tag = f"v{new}"
    existing = _git("tag", "--list", tag)
    if existing:
        raise VersionError(f"tag {tag} already exists")
    _git("add", *[str(p.relative_to(ROOT)) for p in changed])
    _git("commit", "-m", f"Release {tag}")
    _git("tag", "-a", tag, "-m", f"feat {tag}")
    print(f"created commit and tag {tag}; push with:  git push --follow-tags")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bump_version",
        description="Bump feat's single-sourced semantic version.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "part", nargs="?", choices=["major", "minor", "patch"],
        help="which component to increment",
    )
    group.add_argument("--set", dest="explicit", metavar="X.Y.Z",
                       help="set an explicit version instead of bumping")
    parser.add_argument("--pre", metavar="ID",
                        help="attach a pre-release identifier, e.g. rc.1")
    parser.add_argument("--tag", action="store_true",
                        help="create the release commit and git tag (needs a clean tree)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the new version and exit without writing")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        current = read_current_version()
        if args.explicit is not None:
            new = SemVer.parse(args.explicit)
        else:
            new = current.bump(args.part)
        if args.pre is not None:
            new = new.with_pre(args.pre)

        if str(new) == str(current):
            raise VersionError(f"new version equals current ({current}); nothing to do")

        print(f"{current} -> {new}")
        if args.dry_run:
            return 0

        if args.tag:
            ensure_clean_worktree()

        write_version(new)
        today = datetime.date.today().isoformat()
        changed = [INIT_PATH]
        if update_changelog(new, today):
            changed.append(CHANGELOG_PATH)
        else:
            print("note: no CHANGELOG.md [Unreleased] section to promote (skipped)")

        if args.tag:
            create_tag(new, changed)
        else:
            print("updated files; review the diff, then commit and tag when ready")
        return 0
    except VersionError as exc:
        print(f"bump_version: {exc}", file=sys.stderr)
        return 3
    except argparse.ArgumentError as exc:  # pragma: no cover - argparse exits itself
        print(f"bump_version: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
