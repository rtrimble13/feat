"""FmpClient resilience: retries, rate limits, breaker, cache, offline."""

import responses

from feat.infra.fmp import endpoints as ep
from feat.infra.fmp.client import (
    CircuitBreaker,
    FmpError,
    FmpRateLimited,
    FmpUnavailable,
)
from tests.integration.conftest import make_client

import pytest

PROFILE_URL = "https://financialmodelingprep.com/api/v3/profile/TEST"


@responses.activate
def test_success_passes_through_body(client):
    responses.get(PROFILE_URL, json=[{"symbol": "TEST"}])
    body = client.get(ep.PROFILE, {"symbol": "TEST"})
    assert body == [{"symbol": "TEST"}]
    assert "apikey=test-key" in responses.calls[0].request.url


@responses.activate
def test_retries_429_then_succeeds(client):
    responses.get(PROFILE_URL, status=429)
    responses.get(PROFILE_URL, json=[{"symbol": "TEST"}])
    body = client.get(ep.PROFILE, {"symbol": "TEST"})
    assert body == [{"symbol": "TEST"}]
    assert len(responses.calls) == 2


@responses.activate
def test_exhausted_429s_raise_rate_limited(tmp_path):
    client = make_client(tmp_path, max_retries=1)
    responses.get(PROFILE_URL, status=429)
    responses.get(PROFILE_URL, status=429)
    with pytest.raises(FmpRateLimited):
        client.get(ep.PROFILE, {"symbol": "TEST"})


@responses.activate
def test_5xx_exhaustion_raises_unavailable(tmp_path):
    client = make_client(tmp_path, max_retries=1)
    responses.get(PROFILE_URL, status=503)
    responses.get(PROFILE_URL, status=503)
    with pytest.raises(FmpUnavailable):
        client.get(ep.PROFILE, {"symbol": "TEST"})


@responses.activate
def test_error_message_body_raises_fmp_error(client):
    responses.get(PROFILE_URL, json={"Error Message": "Invalid API key"})
    with pytest.raises(FmpError, match="Invalid API key"):
        client.get(ep.PROFILE, {"symbol": "TEST"})


@responses.activate
def test_non_retryable_status_fails_fast(client):
    responses.get(PROFILE_URL, status=403)
    with pytest.raises(FmpError, match="403"):
        client.get(ep.PROFILE, {"symbol": "TEST"})
    assert len(responses.calls) == 1


@responses.activate
def test_circuit_breaker_opens_and_fails_fast(tmp_path):
    breaker = CircuitBreaker(failure_threshold=2, cooldown_seconds=600)
    client = make_client(tmp_path, cache=False, max_retries=1, breaker=breaker)
    responses.get(PROFILE_URL, status=503)
    responses.get(PROFILE_URL, status=503)
    with pytest.raises(FmpUnavailable):
        client.get(ep.PROFILE, {"symbol": "TEST"})
    calls_after_first = len(responses.calls)
    # breaker is now open: the next call must not touch the network
    with pytest.raises(FmpUnavailable, match="circuit breaker open"):
        client.get(ep.PROFILE, {"symbol": "TEST"})
    assert len(responses.calls) == calls_after_first


@responses.activate
def test_cache_hit_avoids_second_request(client):
    responses.get(PROFILE_URL, json=[{"symbol": "TEST"}])
    client.get(ep.PROFILE, {"symbol": "TEST"})
    client.get(ep.PROFILE, {"symbol": "TEST"})
    assert len(responses.calls) == 1


@responses.activate
def test_offline_serves_cache_and_never_calls_network(tmp_path):
    warm = make_client(tmp_path)
    responses.get(PROFILE_URL, json=[{"symbol": "TEST"}])
    warm.get(ep.PROFILE, {"symbol": "TEST"})

    offline = make_client(tmp_path, offline=True)
    body = offline.get(ep.PROFILE, {"symbol": "TEST"})
    assert body == [{"symbol": "TEST"}]
    assert len(responses.calls) == 1  # only the warm-up call


@responses.activate
def test_offline_miss_is_explicit_error(tmp_path):
    offline = make_client(tmp_path, offline=True)
    with pytest.raises(FmpUnavailable, match="offline"):
        offline.get(ep.PROFILE, {"symbol": "TEST"})
    assert len(responses.calls) == 0


def test_offline_requires_no_api_key(tmp_path):
    import logging
    import requests as req
    from feat.infra.cache import DiskCache
    from feat.infra.fmp.client import FmpClient, RateLimiter, Timeouts

    FmpClient(
        api_key="", http=req.Session(), limiter=RateLimiter(60),
        breaker=CircuitBreaker(), timeouts=Timeouts(),
        logger=logging.getLogger("t"), cache=DiskCache(tmp_path), offline=True,
    )
    with pytest.raises(ValueError):
        FmpClient(
            api_key="", http=req.Session(), limiter=RateLimiter(60),
            breaker=CircuitBreaker(), timeouts=Timeouts(),
            logger=logging.getLogger("t"), offline=False,
        )
