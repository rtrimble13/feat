# Avoid recomputing the full ratio panel just to read the accruals ratio

- **Lens:** Enhancement (performance / clarity)
- **Priority:** P3
- **Impact:** Low
- **Effort:** Low
- **Confidence:** High
- **Severity:** —

## Problem

`feat/services/analyze_company.py`:

- Line 60-62 computes `derive.ratio_rows(current, prior)` for every period,
  including the latest — this produces the full ~40-metric panel and is stored
  in `report.ratios`.
- Line 124, inside `_quality`, calls `derive.ratio_rows(current, prior)` a
  **second time** for the same latest/prior pair solely to read
  `["accruals_ratio"]`.

`ratio_rows` computes every profitability, liquidity, leverage, efficiency,
per-share, cash-flow-quality and DuPont family — all discarded here except one
value.

## Why it matters

Pure wasted work: the entire ratio panel is recomputed to extract a single
metric that was already computed moments earlier. The CPU cost is negligible at
current scale, so this is about clarity as much as performance — the double call
obscures that `accruals_ratio` is already available.

## Proposed change

Compute the accruals ratio once. Either:

- read it from the already-computed latest-period dict
  (`ratios[0][1]["accruals_ratio"]`, since `ratios` is most-recent-first and the
  latest row was built from `(statements[0], statements[1])`); or
- compute just `cashflow_quality.accruals_ratio(...)` directly in `_quality`
  instead of the whole panel.

Prefer whichever keeps `_quality`'s inputs explicit; passing the already-computed
value in is cleanest.

## Acceptance criteria

- `derive.ratio_rows` is not invoked a second time for the latest period inside
  `_quality`.
- `QualitySummary.accruals_ratio` is unchanged for existing fixtures (covered by
  the analyze tests).

## Risk / blast radius

Trivial and local to `analyze_company.py`. The only care point is index
alignment — confirm `ratios[0]` corresponds to `statements[0]`/`statements[1]`
(it does) if you read the value from the panel rather than recomputing the
single metric.
