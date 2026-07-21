# Changelog

All notable changes to `feat` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The version itself is single-sourced in `feat/__init__.py` and bumped with
`python scripts/bump_version.py {major|minor|patch}`, which promotes the
`## [Unreleased]` section below into a dated release (see
[docs/adr/0004](docs/adr/0004-single-source-versioning.md)).

## [Unreleased]

### Fixed

- Beneish M-score now computes the LVGI leverage index from total
  liabilities (the canonical Beneish input) rather than interest-bearing
  debt only.
- `residual-income` valuations no longer print a WACC × terminal-growth
  sensitivity grid, whose growth axis had no effect on that model.
- Reconstructed FCFF/FCFE use a genuinely missing diluted share count as a
  gap instead of treating a reported `0.0` as absent.

### Added

- Command vignettes under `docs/vignettes/` walking through each `feat`
  subcommand end to end.
- `scripts/bump_version.py` and single-sourced versioning: the version is
  defined once in `feat/__init__.py` and read dynamically by the build.
- GitHub Actions workflows for CI (tests) and tag-driven release checks.

## [1.0.0] - 2024-01-01

### Added

- Initial release: `analyze`, `value`, `screen`, `compare` and `report`
  commands; layered domain/services/infra architecture; FMP client with
  retry, circuit breaker, rate limiting and disk cache.
