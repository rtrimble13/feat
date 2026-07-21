# ADR 0004: Single-source the version and automate bumps

## Status
Accepted

## Context
The release version originally lived in two places — a literal in
`pyproject.toml` and `__version__` in `feat/__init__.py`. Two copies drift:
a hand-edited `pyproject.toml` can ship a wheel whose `feat --version`
disagrees with its package metadata, and reviewers cannot tell which number
is authoritative. Bumping by hand also skips the changelog and the tag, so
release provenance rots.

## Decision
- **One source of truth:** `feat/__init__.py`'s `__version__`.
  `pyproject.toml` declares `dynamic = ["version"]` and reads it via
  `[tool.setuptools.dynamic] version = {attr = "feat.__version__"}`.
- **One supported way to change it:** `scripts/bump_version.py` parses the
  current SemVer, applies a `major|minor|patch` bump (or `--set`/`--pre`),
  rewrites `__init__.py`, promotes the `## [Unreleased]` changelog section
  to a dated release, and optionally creates the `vX.Y.Z` commit and tag.
- **A release gate:** the `Release` GitHub Actions workflow fires on `v*`
  tags and fails unless the tag equals `feat.__version__`, the tests pass,
  and the package builds. Drift cannot reach a published artifact.

## Consequences
`feat --version`, the wheel metadata, the changelog and the git tag can no
longer disagree. Cutting a release is `python scripts/bump_version.py patch
--tag && git push --follow-tags`. The cost is a one-time setuptools dynamic
declaration and the small bump script, both covered by tests.
