"""End-to-end: invoke the CLI, assert on rendered output and exit codes.

HTTP is stubbed with recorded fixtures; each test gets its own cache dir
via a generated config file, so runs are hermetic and deterministic.
"""

import json

import pytest
import responses

from feat.cli.main import main
from tests.integration.conftest import load_fixture

V3 = "https://financialmodelingprep.com/api/v3"


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    path = tmp_path / "config.toml"
    path.write_text(f'cache_dir = "{tmp_path / "cache"}"\n')
    return str(path)


def stub_company_endpoints():
    responses.get(f"{V3}/profile/TEST", json=load_fixture("profile_test.json"))
    responses.get(f"{V3}/income-statement/TEST", json=load_fixture("income_test.json"))
    responses.get(f"{V3}/balance-sheet-statement/TEST", json=load_fixture("balance_test.json"))
    responses.get(f"{V3}/cash-flow-statement/TEST", json=load_fixture("cashflow_test.json"))
    responses.get(f"{V3}/discounted-cash-flow/TEST", json=load_fixture("dcf_test.json"))


@responses.activate
def test_analyze_json_journey(config_file, capsys):
    stub_company_endpoints()
    exit_code = main(["analyze", "TEST", "--json", "--config", config_file])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ticker"] == "TEST"
    assert payload["company"]["name"] == "Test Co"
    assert payload["ratios"]["FY2024"]["gross_margin"] == pytest.approx(0.4)
    # FCFF = 28e9 + 1e9*(1-0.2) - 8e9
    assert payload["ratios"]["FY2024"]["fcff"] == pytest.approx(20.8e9)
    # FY2022 EBITDA was absent upstream: stays null, never zero
    assert payload["ratios"]["FY2022"]["ebitda_margin"] is None
    assert payload["quality"]["piotroski"]["score"] is not None


@responses.activate
def test_analyze_table_journey(config_file, capsys):
    stub_company_endpoints()
    exit_code = main(["analyze", "TEST", "--no-color", "--config", config_file])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Test Co" in out
    assert "Gross margin" in out
    assert "40.0%" in out
    assert "—" in out  # missing FY2022 EBITDA is flagged, not zeroed


@responses.activate
def test_value_dcf_fcff_journey(config_file, capsys):
    stub_company_endpoints()
    exit_code = main([
        "value", "TEST", "--model", "dcf-fcff", "--json", "--config", config_file,
    ])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model"] == "dcf-fcff"
    assert payload["fair_value_per_share"] > 0
    assert payload["fmp_reference_dcf"] == 123.45  # cross-check surfaced
    assert payload["assumptions"]["wacc"] > payload["assumptions"]["terminal_growth"]


@responses.activate
def test_value_reverse_dcf_journey(config_file, capsys):
    stub_company_endpoints()
    exit_code = main([
        "value", "TEST", "--model", "reverse-dcf", "--json", "--config", config_file,
    ])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert -0.5 <= payload["details"]["implied_growth"] <= 1.0


@responses.activate
def test_unknown_symbol_exit_code(config_file, capsys):
    responses.get(f"{V3}/profile/NOPE", json=[])
    exit_code = main(["analyze", "NOPE", "--config", config_file])
    assert exit_code == 3
    assert "not found" in capsys.readouterr().err


@responses.activate
def test_batch_partial_failure_continues(config_file, capsys):
    stub_company_endpoints()
    responses.get(f"{V3}/profile/NOPE", json=[])
    exit_code = main(["analyze", "NOPE", "TEST", "--json", "--config", config_file])
    captured = capsys.readouterr()
    assert exit_code == 3            # the failure is reported...
    assert '"ticker": "TEST"' in captured.out  # ...but TEST still ran
    assert "NOPE" in captured.err


def test_invalid_ticker_is_usage_error(config_file, capsys):
    exit_code = main(["analyze", "not a ticker!!", "--config", config_file])
    assert exit_code == 2
    assert "invalid ticker" in capsys.readouterr().err


def test_missing_api_key_is_config_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    exit_code = main(["analyze", "TEST"])
    assert exit_code == 7
    assert "FMP_API_KEY" in capsys.readouterr().err


@responses.activate
def test_offline_after_warm_cache(config_file, capsys):
    stub_company_endpoints()
    assert main(["analyze", "TEST", "--json", "--config", config_file]) == 0
    capsys.readouterr()
    network_calls = len(responses.calls)
    assert main(["analyze", "TEST", "--json", "--offline", "--config", config_file]) == 0
    assert len(responses.calls) == network_calls  # served fully from cache
    assert json.loads(capsys.readouterr().out)["ticker"] == "TEST"


@responses.activate
def test_csv_output(config_file, capsys):
    stub_company_endpoints()
    assert main(["analyze", "TEST", "--csv", "--config", config_file]) == 0
    out = capsys.readouterr().out
    assert out.startswith("section,")
    assert "Gross margin" in out


@responses.activate
def test_report_markdown(config_file, capsys):
    stub_company_endpoints()
    assert main(["report", "TEST", "--config", config_file]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Test Co (TEST)")
    assert "Margin of safety" in out or "Fair value" in out
