"""Integration test wiring: an FmpClient with no real sleeps and a
helper to register recorded fixtures against the mocked HTTP layer."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
import requests

from feat.infra.cache import DiskCache
from feat.infra.fmp.client import CircuitBreaker, FmpClient, RateLimiter, Timeouts

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


def make_client(
    tmp_path: Path,
    *,
    cache: bool = True,
    offline: bool = False,
    snapshot: bool = False,
    max_retries: int = 2,
    breaker: CircuitBreaker | None = None,
) -> FmpClient:
    return FmpClient(
        api_key="test-key",
        http=requests.Session(),
        limiter=RateLimiter(6000, sleeper=lambda s: None),
        breaker=breaker or CircuitBreaker(failure_threshold=5, cooldown_seconds=60),
        timeouts=Timeouts(connect=1.0, read=2.0),
        logger=logging.getLogger("feat.test"),
        cache=DiskCache(tmp_path / "cache") if cache else None,
        max_retries=max_retries,
        offline=offline,
        snapshot=snapshot,
        sleeper=lambda s: None,
    )


@pytest.fixture
def client(tmp_path: Path) -> FmpClient:
    return make_client(tmp_path)
