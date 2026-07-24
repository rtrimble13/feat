"""Resilience primitives under a fake clock/sleeper.

The recovery and timing paths of the circuit breaker, rate limiter and retry
backoff never ran under the existing suite (it used a no-op sleeper and a
600 s real-clock cooldown). These tests drive them deterministically via the
injected `clock`, `sleeper` and `rng` seams the classes already expose.
"""

from __future__ import annotations

import logging
import random

import pytest
import requests
import responses

from feat.infra.fmp import endpoints as ep
from feat.infra.fmp.client import (
    CircuitBreaker,
    FmpUnavailable,
    FmpClient,
    RateLimiter,
    Timeouts,
    _parse_retry_after,
)

PROFILE_URL = "https://financialmodelingprep.com/api/v3/profile/TEST"


# --- CircuitBreaker recovery ---------------------------------------------


class TestCircuitBreaker:
    def test_stays_closed_below_threshold(self):
        breaker = CircuitBreaker(failure_threshold=3, clock=lambda: 0.0)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.allow()  # 2 < 3, still closed

    def test_opens_then_half_opens_after_cooldown_and_resets_on_success(self):
        now = [1000.0]
        breaker = CircuitBreaker(
            failure_threshold=2, cooldown_seconds=60, clock=lambda: now[0]
        )
        breaker.record_failure()
        breaker.record_failure()
        assert not breaker.allow()          # open

        now[0] += 59
        assert not breaker.allow()          # still within cooldown

        now[0] += 2                          # 61 s elapsed > 60 s cooldown
        assert breaker.allow()              # half-open probe admitted

        breaker.record_success()
        assert breaker.allow()
        # proof the failure counter reset: one fresh failure (< threshold 2)
        # must not re-open the breaker.
        breaker.record_failure()
        assert breaker.allow()

    def test_half_open_probe_failure_reopens_for_another_cooldown(self):
        now = [0.0]
        breaker = CircuitBreaker(
            failure_threshold=1, cooldown_seconds=10, clock=lambda: now[0]
        )
        breaker.record_failure()             # opens (threshold 1)
        assert not breaker.allow()

        now[0] = 11
        assert breaker.allow()              # half-open

        breaker.record_failure()             # probe fails -> reopen at t=11
        now[0] = 15
        assert not breaker.allow()          # within the new cooldown
        now[0] = 22
        assert breaker.allow()              # recovered again


# --- RateLimiter token-bucket timing -------------------------------------


class TestRateLimiter:
    def test_rejects_non_positive_rate(self):
        with pytest.raises(ValueError):
            RateLimiter(0)
        with pytest.raises(ValueError):
            RateLimiter(-10)

    def test_throttles_when_bucket_empty(self):
        now = [0.0]
        slept: list[float] = []

        def sleeper(seconds: float) -> None:
            slept.append(seconds)
            now[0] += seconds                # sleeping advances the (fake) clock

        # rate 60/min = 1 token/sec, burst capacity 1
        rl = RateLimiter(60, clock=lambda: now[0], sleeper=sleeper, burst=1)
        rl.acquire()                         # consumes the single token, no wait
        assert slept == []
        rl.acquire()                         # bucket empty -> wait one refill period
        assert slept == [pytest.approx(1.0)]

    def test_refills_over_elapsed_time(self):
        now = [0.0]
        slept: list[float] = []
        rl = RateLimiter(60, clock=lambda: now[0],
                         sleeper=lambda s: slept.append(s), burst=2)
        rl.acquire()
        rl.acquire()                         # drain both tokens, no wait
        assert slept == []

        now[0] += 2.0                        # 2 s -> +2 tokens (capped at burst=2)
        rl.acquire()
        rl.acquire()                         # both served from the refill
        assert slept == []

    def test_burst_capacity_defaults_to_a_tenth_of_the_rate(self):
        now = [0.0]
        slept: list[float] = []
        # rate 600/min, default burst = max(600 // 10, 1) = 60
        rl = RateLimiter(600, clock=lambda: now[0], sleeper=lambda s: slept.append(s))
        for _ in range(60):
            rl.acquire()                     # 60 immediate tokens from the burst
        assert slept == []


# --- Retry backoff + Retry-After -----------------------------------------


def recording_client(*, max_retries: int = 2,
                     breaker: CircuitBreaker | None = None) -> tuple[FmpClient, list[float]]:
    slept: list[float] = []
    client = FmpClient(
        api_key="test-key",
        http=requests.Session(),
        limiter=RateLimiter(6000, sleeper=lambda s: None),
        breaker=breaker or CircuitBreaker(failure_threshold=100),
        timeouts=Timeouts(connect=1.0, read=2.0),
        logger=logging.getLogger("feat.test"),
        cache=None,
        max_retries=max_retries,
        sleeper=lambda s: slept.append(s),
        rng=random.Random(0),                # deterministic jitter
    )
    return client, slept


class TestBackoff:
    @responses.activate
    def test_retry_after_header_floors_the_backoff(self):
        client, slept = recording_client(max_retries=2)
        responses.get(PROFILE_URL, status=429, headers={"Retry-After": "5"})
        responses.get(PROFILE_URL, json=[{"symbol": "TEST"}])
        assert client.get(ep.PROFILE, {"symbol": "TEST"}) == [{"symbol": "TEST"}]
        # computed backoff for attempt 1 is ~2s + jitter; Retry-After raises it to 5.
        assert slept == [pytest.approx(5.0)]

    @responses.activate
    def test_backoff_grows_exponentially_and_caps_at_30s(self):
        client, slept = recording_client(
            max_retries=5, breaker=CircuitBreaker(failure_threshold=100)
        )
        responses.get(PROFILE_URL, status=503)   # every attempt fails
        with pytest.raises(FmpUnavailable):
            client.get(ep.PROFILE, {"symbol": "TEST"})
        # one sleep before each of the 5 retries: 2, 4, 8, 16, then 32 capped to 30
        assert len(slept) == 5
        for got, base in zip(slept, [2, 4, 8, 16, 30]):
            assert base <= got < base + 0.5      # base + jitter in [0, 0.5)
        assert slept[-1] < 30.5                   # 2**5 = 32 capped at 30


class TestParseRetryAfter:
    def test_numeric_seconds(self):
        assert _parse_retry_after("5") == pytest.approx(5.0)
        assert _parse_retry_after("0") == pytest.approx(0.0)

    def test_negative_is_clamped_to_zero(self):
        assert _parse_retry_after("-3") == pytest.approx(0.0)

    def test_none_and_http_date_fall_back_to_none(self):
        assert _parse_retry_after(None) is None
        # HTTP-date form is not parsed here; caller falls back to computed backoff
        assert _parse_retry_after("Wed, 21 Oct 2026 07:28:00 GMT") is None
