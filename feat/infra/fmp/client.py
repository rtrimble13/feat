"""FmpClient: the only place that knows FMP is reached over HTTP.

Responsibilities:
- explicit connect/read timeouts on every call
- retry with exponential backoff + jitter for transient failures
  (429 / 5xx / connection errors); honors ``Retry-After``
- circuit breaker: after N consecutive failures, fail fast for a
  cooldown window instead of amplifying an FMP outage
- token-bucket rate limiter tuned to the plan's requests/minute
- API key injected from config, appended as a query parameter, never
  logged (log lines carry the endpoint name, not the URL)
- optional disk cache with per-endpoint TTL, plus offline and snapshot
  modes
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from feat.infra.cache import DiskCache
from feat.infra.fmp.endpoints import Endpoint

Json = Any  # parsed JSON body: list | dict


class FmpError(Exception):
    """Unexpected FMP failure (schema surprise, unrecoverable HTTP error)."""


class FmpRateLimited(FmpError):
    """Still rate-limited after retries."""


class FmpUnavailable(FmpError):
    """FMP unreachable / 5xx after retries, or circuit breaker open."""


@dataclass(frozen=True, slots=True)
class Timeouts:
    connect: float = 5.0
    read: float = 30.0

    def as_tuple(self) -> tuple[float, float]:
        return (self.connect, self.read)


class RateLimiter:
    """Token bucket: ``rate_per_minute`` requests sustained, small burst."""

    def __init__(
        self,
        rate_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
        burst: int | None = None,
    ) -> None:
        if rate_per_minute <= 0:
            raise ValueError("rate must be positive")
        self._rate = rate_per_minute / 60.0
        self._capacity = float(burst if burst is not None else max(rate_per_minute // 10, 1))
        self._tokens = self._capacity
        self._clock = clock
        self._sleep = sleeper
        self._last = clock()

    def acquire(self) -> None:
        while True:
            now = self._clock()
            self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._rate)
            self._last = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return
            self._sleep((1.0 - self._tokens) / self._rate)


class CircuitBreaker:
    """Opens after ``failure_threshold`` consecutive failures; half-opens
    after ``cooldown_seconds`` to probe with a single request."""

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if self._clock() - self._opened_at >= self._cooldown:
            return True  # half-open probe
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = self._clock()


class FmpClient:
    _RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str,
        http: requests.Session,
        limiter: RateLimiter,
        breaker: CircuitBreaker,
        timeouts: Timeouts,
        logger: logging.Logger,
        cache: DiskCache | None = None,
        max_retries: int = 4,
        offline: bool = False,
        snapshot: bool = False,
        sleeper: Callable[[float], None] = time.sleep,
        rng: random.Random | None = None,
    ) -> None:
        if not api_key and not offline:
            raise ValueError("api_key required unless offline")
        self._api_key = api_key
        self._http = http
        self._limiter = limiter
        self._breaker = breaker
        self._timeouts = timeouts
        self._log = logger
        self._cache = cache
        self._max_retries = max_retries
        self._offline = offline
        # snapshot: serve cached responses regardless of age (reproducible
        # reports, no look-ahead) but still allow the network on a miss
        self._snapshot = snapshot
        self._sleep = sleeper
        self._rng = rng or random.Random()

    def get(self, endpoint: Endpoint, path_params: dict[str, str] | None = None,
            **query: str | int | float) -> Json:
        """One rate-limited, retried, cached GET. Returns the parsed JSON
        body; raises FmpRateLimited / FmpUnavailable / FmpError. Never
        swallows an error into an empty result."""
        url = endpoint.url(**(path_params or {}))
        cache_key = self._cache_key(endpoint, path_params, query)

        if self._cache is not None:
            serve_any_age = self._offline or self._snapshot
            cached = self._cache.get(
                cache_key, ttl_seconds=None if serve_any_age else endpoint.cache_ttl_seconds
            )
            if cached is not None:
                self._log.debug("cache hit", extra={"endpoint": endpoint.name})
                return cached
        if self._offline:
            raise FmpUnavailable(
                f"offline mode and no cached response for {endpoint.name} "
                f"({self._describe(path_params, query)})"
            )

        body = self._fetch_with_retry(endpoint, url, query)
        if self._cache is not None:
            self._cache.put(cache_key, body)
        return body

    def _fetch_with_retry(self, endpoint: Endpoint, url: str, query: dict) -> Json:
        if not self._breaker.allow():
            raise FmpUnavailable(
                f"circuit breaker open for FMP (endpoint {endpoint.name}); "
                "retry after the cooldown window"
            )
        params = dict(query)
        params["apikey"] = self._api_key  # requests handles ?/& placement
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                delay = min(2.0 ** attempt, 30.0) + self._rng.uniform(0, 0.5)
                if isinstance(last_error, _RetryAfter) and last_error.seconds is not None:
                    delay = max(delay, last_error.seconds)
                self._log.warning(
                    "retrying FMP request",
                    extra={"endpoint": endpoint.name, "attempt": attempt, "delay_s": round(delay, 2)},
                )
                self._sleep(delay)
            self._limiter.acquire()
            try:
                response = self._http.get(url, params=params, timeout=self._timeouts.as_tuple())
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
                self._breaker.record_failure()
                continue
            if response.status_code in self._RETRYABLE_STATUS:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                last_error = _RetryAfter(response.status_code, retry_after)
                self._breaker.record_failure()
                continue
            if response.status_code != 200:
                self._breaker.record_failure()
                raise FmpError(
                    f"FMP returned HTTP {response.status_code} for {endpoint.name}"
                )
            try:
                body = response.json()
            except ValueError as exc:
                self._breaker.record_failure()
                raise FmpError(f"non-JSON body from FMP for {endpoint.name}") from exc
            if isinstance(body, dict) and "Error Message" in body:
                self._breaker.record_failure()
                raise FmpError(f"FMP error for {endpoint.name}: {body['Error Message']}")
            self._breaker.record_success()
            return body

        if isinstance(last_error, _RetryAfter) and last_error.status == 429:
            raise FmpRateLimited(
                f"still rate-limited by FMP after {self._max_retries} retries "
                f"({endpoint.name})"
            )
        raise FmpUnavailable(
            f"FMP unavailable after {self._max_retries} retries ({endpoint.name}): "
            f"{last_error}"
        )

    @staticmethod
    def _cache_key(endpoint: Endpoint, path_params: dict | None, query: dict) -> str:
        parts = [endpoint.name]
        for k in sorted(path_params or {}):
            parts.append(f"{k}={path_params[k]}")  # type: ignore[index]
        for k in sorted(query):
            parts.append(f"{k}={query[k]}")
        return "|".join(parts)

    @staticmethod
    def _describe(path_params: dict | None, query: dict) -> str:
        merged = {**(path_params or {}), **query}
        return ", ".join(f"{k}={v}" for k, v in sorted(merged.items())) or "no params"


class _RetryAfter(Exception):
    def __init__(self, status: int, seconds: float | None) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.seconds = seconds


def _parse_retry_after(header: str | None) -> float | None:
    if header is None:
        return None
    try:
        return max(0.0, float(header))
    except ValueError:
        return None  # HTTP-date form: fall back to computed backoff
