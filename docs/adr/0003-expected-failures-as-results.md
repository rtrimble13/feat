# ADR 0003: Expected failures are Result values; unexpected ones raise

## Status
Accepted

## Context
Talking to a market-data vendor fails in *expected* ways: unknown symbol,
thin history, rate limits, outages. Exceptions for these blur the line
between "the analyst typo'd a ticker" and "feat has a bug", and invite
catch-all handlers that swallow real defects.

## Decision
- Domain/services return `Result[T, AnalysisError]` with typed variants
  (`SymbolNotFound`, `InsufficientHistory`, `MissingRequiredField`,
  `RateLimited`, `UpstreamUnavailable`, `InvalidInput`, `ConfigError`),
  each carrying its CLI exit code (3/4/4/5/6/2/7).
- The transport layer raises `FmpError` subclasses; the adapter is the only
  place that converts the expected ones into `Err` values.
- Truly unexpected errors (bugs, corrupt cache files) raise and surface a
  stack trace under `-v`; there are no `except Exception: pass` handlers.
- Batch runs report per-ticker errors and continue; the exit code reflects
  the first failure.

## Consequences
Exit codes are stable and script-friendly; error messages are specific and
actionable; a genuine bug is never silently downgraded to "no data".
