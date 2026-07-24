# Test the FMP resilience layer: breaker recovery, limiter timing, backoff, Retry-After

- **Lens:** Refactoring (test coverage) / Robustness
- **Priority:** P1
- **Impact:** High
- **Effort:** Low
- **Confidence:** High
- **Severity:** —

## Problem

The resilience mechanisms in `feat/infra/fmp/client.py` — the reason the client
exists — have their recovery and timing paths unexercised, because the existing
integration tests use a no-op sleeper and a 600 s real-clock breaker cooldown
that never elapses. Specifically untested:

- **CircuitBreaker recovery** — `allow()` returning `True` after cooldown
  (half-open probe, `client.py:99-104`) and `record_success()` resetting
  `_failures`/`_opened_at` (`client.py:106-108`). Only the open/fail-fast
  direction is tested.
- **RateLimiter token bucket** — refill `min(capacity, tokens + elapsed*rate)`,
  the throttling `sleep` branch, burst capacity, and the `rate_per_minute <= 0`
  `ValueError` (`client.py:63-80`). Tests only run it at rate 6000 with a no-op
  sleeper, so no throttling ever happens.
- **Retry backoff** — `min(2.0**attempt, 30.0) + jitter`, the 30 s cap, and the
  `Retry-After` override `delay = max(delay, last_error.seconds)`
  (`client.py:191-199`).
- **`_parse_retry_after`** (`client.py:260-266`) — neither the numeric branch
  nor the HTTP-date fallback (`return None`) is tested, though `Retry-After`
  honoring is advertised in the module docstring.

## Why it matters

A stuck-open breaker (never resetting after a probe) or a miscomputed token
refill (over-throttling every request, or blowing the FMP plan's rate limit)
is a real production availability/cost bug — and today's suite cannot detect
either, because the code paths never run under test. The design already exposes
`clock`, `sleeper`, and `rng` seams precisely so these can be tested
deterministically; they're simply unused.

## Proposed change

Add fake-clock/fake-sleeper unit tests (no HTTP needed for the primitives):

- **Breaker:** feed `failure_threshold` failures → `allow()` is `False` →
  advance the injected clock past `cooldown_seconds` → `allow()` is `True` →
  `record_success()` → `_failures == 0` and `allow()` stays `True`.
- **Limiter:** with an injected clock and a recording sleeper, drain the bucket,
  assert `acquire()` sleeps the expected `(1 - tokens)/rate`, assert refill after
  advancing the clock, and assert `RateLimiter(0)` raises.
- **Backoff/Retry-After:** with a recording sleeper and a stubbed HTTP returning
  429 + `Retry-After`, assert the delays honor the cap, the jitter bound, and
  the `Retry-After` override; unit-test `_parse_retry_after` for numeric and
  HTTP-date inputs.

## Acceptance criteria

- Tests exercise breaker half-open→success-reset, limiter throttle+refill+burst
  +bad-rate, backoff cap/jitter/Retry-After override, and both
  `_parse_retry_after` branches — all with injected clock/sleeper (no real
  sleeping, no wall-clock).
- Existing client tests still pass.

## Risk / blast radius

Test-only. Low risk. If a test reveals the breaker's half-open admits more than
one probe (all callers pass while open-after-cooldown until a result is
recorded), decide whether that's acceptable for a single-threaded CLI and note
it — but keep any behavior change out of this coverage PR.
