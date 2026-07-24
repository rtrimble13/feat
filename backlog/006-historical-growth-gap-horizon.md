# Fix `historical_growth` CAGR horizon when the series has interior gaps

- **Lens:** Hidden bug
- **Priority:** P3
- **Impact:** Low
- **Effort:** Low
- **Confidence:** High
- **Severity:** Low

## Problem

`feat/services/derive.py:189-200`:

```python
def historical_growth(values: list[float | None], max_years: int = 5) -> float | None:
    clean = [v for v in values if v is not None]       # drops interior gaps
    if len(clean) < 2:
        return None
    window = clean[-(max_years + 1):]
    first, last = window[0], window[-1]
    if first <= 0 or last <= 0:
        return None
    years = len(window) - 1                             # counts points, not elapsed years
    return (last / first) ** (1.0 / years) - 1.0
```

`clean` removes `None`s anywhere in the series, then the CAGR exponent uses
`years = len(window) - 1` (a count of *present* points). If a middle year's
revenue is missing, the true elapsed span between `first` and `last` is larger
than `len(window) - 1`, so the annualized rate is computed over the wrong number
of years.

## Why it matters

This CAGR is the **default DCF growth** assumption: `value_company.py:185-189`
does `growth = derive.historical_growth(history.trend("revenue"))`. With a gap
in the reported revenue series, the seeded forecast growth is biased (a
5-calendar-year span with one missing point is treated as a 4-year CAGR,
overstating the annual rate). Blast radius is limited: growth is clamped to
`[-0.20, 0.25]` immediately after, and any analyst can override with `--growth`,
and fully-reported series (the common case) are unaffected — hence Low severity.

## Proposed change

Base the exponent on the actual elapsed periods between the first and last
*present* points rather than the count of non-null values. Two viable options:

- Pass the periods alongside values and use the calendar-year distance between
  the endpoints of the window; or
- Restrict to a contiguous non-null tail (stop at the first gap from the recent
  end) so `len(window) - 1` again equals elapsed years, and document that only
  the uninterrupted recent run is used.

Prefer the first if period metadata is readily threadable; otherwise the second
is a safe, clearly-documented simplification.

## Acceptance criteria

- For a series with an interior gap spanning N calendar years, the returned CAGR
  uses N (not the reduced point count) as the exponent denominator.
- A unit test covers: no-gap series (unchanged), interior-gap series (correct
  horizon), and the existing non-positive-endpoint / <2-point guards.

## Risk / blast radius

Small and self-contained. It changes the default growth for issuers with gappy
revenue history, which will shift their DCF fair value slightly — call that out
in review. No effect when `--growth` is supplied or the series is complete.
