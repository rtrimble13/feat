# Add test coverage for the `compare` and `screen` commands (services + CLI)

- **Lens:** Refactoring (test coverage)
- **Priority:** P1
- **Impact:** High
- **Effort:** Medium
- **Confidence:** High
- **Severity:** —

## Problem

Two of the five shipped commands have **no test coverage at all**:

- `feat/services/compare_peers.py` (103 lines) — peer expansion, per-ticker
  metric assembly, median aggregation, partial-failure handling.
- `feat/services/screen_universe.py` (100 lines) — filter→FMP-param mapping
  (`to_fmp_params`), limit validation, screener-row parsing.
- `feat/cli/compare.py` and `feat/cli/screen.py` — argument wiring, metric
  validation, watchlist writing.

There is no unit test for either service, and neither `compare` nor `screen`
is invoked anywhere in `tests/e2e/test_cli.py` (which exercises `analyze`,
`value`, and `report`). A grep for "compare"/"screen" in the test tree hits
only unrelated names.

## Why it matters

All peer-selection, median/multiple aggregation, and screener filter logic is
completely unverified. Concrete regressions that would ship silently today:

- a wrong key in `ScreenFilters.to_fmp_params` (`screen_universe.py:27-46`)
  sends a bad param to FMP and silently drops a filter;
- `ComparePeers._one` (`compare_peers.py:70-103`) mis-keying a metric, or
  `median` (`relative.py:63`) mishandling an even-length list, corrupts the
  comparison table with no signal;
- `expand_peers` (`compare_peers.py:63-68`) losing the anchor ticker.

## Proposed change

- Unit-test both services against a fake `FundamentalsRepository` (in-memory,
  no HTTP): cover peer expansion incl. anchor, partial failures recorded in
  `failures`, median math (even/odd/all-None), `to_fmp_params` mapping for each
  filter, and the limit-bounds error.
- Add e2e journeys for `feat compare --peers AAPL` and
  `feat screen --sector Technology --min-mcap ...`, mirroring the existing
  `responses`-backed e2e style, including `--to-watchlist` file output and the
  `compare` "no tickers or --peers" usage error (exit 2).

## Acceptance criteria

- New unit tests for `compare_peers.py` and `screen_universe.py` covering happy
  path, partial failure, and each validation branch.
- New e2e tests that actually invoke the `compare` and `screen` commands.
- Coverage for both service modules is non-trivial (lines and error branches
  exercised); existing tests still pass.

## Risk / blast radius

Test-only; no production code changes required. Low risk. If test-writing
surfaces a real defect in the untested logic, file it separately rather than
folding a behavior change into the coverage PR.
