"""End-to-end coverage for the `compare` and `screen` commands.

These two commands had no e2e journey; here they are driven through the real
CLI entry point with HTTP stubbed by recorded fixtures.
"""

import json

import pytest
import responses

from feat.cli.main import main
from tests.integration.conftest import load_fixture

V3 = "https://financialmodelingprep.com/api/v3"
V4 = "https://financialmodelingprep.com/api/v4"
STABLE = "https://financialmodelingprep.com/stable"


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    path = tmp_path / "config.toml"
    path.write_text(f'cache_dir = "{tmp_path / "cache"}"\n')
    return str(path)


def stub_symbol(symbol: str) -> None:
    """Register profile + three statements for a symbol, reusing fixtures."""
    responses.get(f"{V3}/profile/{symbol}", json=load_fixture("profile_test.json"))
    responses.get(f"{V3}/income-statement/{symbol}", json=load_fixture("income_test.json"))
    responses.get(f"{V3}/balance-sheet-statement/{symbol}",
                  json=load_fixture("balance_test.json"))
    responses.get(f"{V3}/cash-flow-statement/{symbol}", json=load_fixture("cashflow_test.json"))


# --- compare --------------------------------------------------------------


@responses.activate
def test_compare_explicit_tickers_json(config_file, capsys):
    stub_symbol("TEST")
    stub_symbol("OTHER")
    exit_code = main(["compare", "TEST", "OTHER", "--json", "--config", config_file])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload["rows"]) == {"TEST", "OTHER"}
    assert "roe" in payload["metrics"]
    assert "medians" in payload


@responses.activate
def test_compare_table_output(config_file, capsys):
    stub_symbol("TEST")
    stub_symbol("OTHER")
    exit_code = main(["compare", "TEST", "OTHER", "--no-color", "--config", config_file])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Comparison" in out
    assert "Median" in out


@responses.activate
def test_compare_peers_seeds_from_peer_list(config_file, capsys):
    responses.get(f"{V4}/stock_peers", json=load_fixture("peers_test.json"))
    for symbol in ("TEST", "PEERA", "PEERB"):
        stub_symbol(symbol)
    exit_code = main(["compare", "--peers", "TEST", "--json", "--config", config_file])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    # anchor plus the two well-formed peers ("bad ticker!" is dropped upstream)
    assert set(payload["rows"]) == {"TEST", "PEERA", "PEERB"}


@responses.activate
def test_compare_partial_failure_reports_and_continues(config_file, capsys):
    stub_symbol("TEST")
    responses.get(f"{V3}/profile/NOPE", json=[])
    exit_code = main(["compare", "TEST", "NOPE", "--json", "--config", config_file])
    captured = capsys.readouterr()
    assert exit_code == 0                       # a partial batch still succeeds
    assert "TEST" in json.loads(captured.out)["rows"]
    assert "NOPE" in captured.err               # the skip is surfaced on stderr


def test_compare_without_tickers_or_peers_is_usage_error(config_file, capsys):
    exit_code = main(["compare", "--config", config_file])
    assert exit_code == 2
    assert "needs tickers or --peers" in capsys.readouterr().err


def test_compare_unknown_metric_is_usage_error(config_file, capsys):
    exit_code = main(["compare", "TEST", "--metrics", "not_a_metric", "--config", config_file])
    assert exit_code == 2
    assert "unknown metrics" in capsys.readouterr().err


# --- screen ---------------------------------------------------------------


@responses.activate
def test_screen_json_journey(config_file, capsys):
    responses.get(f"{STABLE}/company-screener", json=load_fixture("screener.json"))
    exit_code = main([
        "screen", "--sector", "Technology", "--min-mcap", "1e10",
        "--json", "--config", config_file,
    ])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [r["symbol"] for r in payload["matches"]] == ["TEST", "OTHER"]
    assert payload["filters"]["sector"] == "Technology"


@responses.activate
def test_screen_writes_watchlist(config_file, tmp_path, capsys):
    responses.get(f"{STABLE}/company-screener", json=load_fixture("screener.json"))
    watchlist = tmp_path / "watch.txt"
    exit_code = main([
        "screen", "--sector", "Technology", "--to-watchlist", str(watchlist),
        "--no-color", "--config", config_file,
    ])
    assert exit_code == 0
    assert watchlist.read_text().splitlines() == ["TEST", "OTHER"]
    assert "wrote 2 symbols" in capsys.readouterr().err


@responses.activate
def test_screen_invalid_limit_is_error(config_file, capsys):
    # limit is validated before any network call is needed
    exit_code = main(["screen", "--limit", "0", "--config", config_file])
    assert exit_code == 2
    assert "limit" in capsys.readouterr().err
