"""FmpAdapter against recorded fixtures: schema mapping, adjClose usage,
empty-response handling, MISSING propagation, batch chunking."""

from datetime import date

import responses

from feat.domain.errors import SymbolNotFound
from feat.domain.values import MISSING, PeriodType, Ticker, is_missing
from feat.infra.fmp.adapter import FmpAdapter, _money_first
from tests.integration.conftest import load_fixture, make_client

V3 = "https://financialmodelingprep.com/api/v3"
V4 = "https://financialmodelingprep.com/api/v4"
STABLE = "https://financialmodelingprep.com/stable"


def adapter(tmp_path) -> FmpAdapter:
    return FmpAdapter(make_client(tmp_path, cache=False))


@responses.activate
def test_profile_maps_to_company(tmp_path):
    responses.get(f"{V3}/profile/TEST", json=load_fixture("profile_test.json"))
    company = adapter(tmp_path).get_company(Ticker("TEST")).unwrap()
    assert company.name == "Test Co"
    assert company.sector == "Technology"
    assert company.beta == 1.2
    assert company.price.amount == 100.0
    assert company.market_cap.amount == 100e9
    assert company.shares_outstanding == 1e9


@responses.activate
def test_empty_profile_is_symbol_not_found(tmp_path):
    responses.get(f"{V3}/profile/NOPE", json=[])
    result = adapter(tmp_path).get_company(Ticker("NOPE"))
    assert result.is_err()
    assert isinstance(result.error, SymbolNotFound)


@responses.activate
def test_history_maps_statements_and_periods(tmp_path):
    responses.get(f"{V3}/income-statement/TEST", json=load_fixture("income_test.json"))
    responses.get(f"{V3}/balance-sheet-statement/TEST", json=load_fixture("balance_test.json"))
    responses.get(f"{V3}/cash-flow-statement/TEST", json=load_fixture("cashflow_test.json"))
    history = adapter(tmp_path).get_history(Ticker("TEST"), PeriodType.ANNUAL, 10).unwrap()

    assert len(history) == 3
    latest = history.latest
    assert latest.period.fiscal_year == 2024
    assert latest.period.end_date == date(2024, 9, 28)  # parsed, not a string
    assert latest.income.revenue.amount == 100e9
    assert latest.balance.total_equity.amount == 60e9
    assert latest.cash_flow.capital_expenditure.amount == -8e9
    # the period param FMP requires is 'annual', never 'quarterly'
    assert "period=annual" in responses.calls[0].request.url


@responses.activate
def test_absent_field_becomes_missing_never_zero(tmp_path):
    responses.get(f"{V3}/income-statement/TEST", json=load_fixture("income_test.json"))
    responses.get(f"{V3}/balance-sheet-statement/TEST", json=load_fixture("balance_test.json"))
    responses.get(f"{V3}/cash-flow-statement/TEST", json=load_fixture("cashflow_test.json"))
    history = adapter(tmp_path).get_history(Ticker("TEST"), PeriodType.ANNUAL, 10).unwrap()
    fy2022 = history.statements[2]
    assert is_missing(fy2022.income.ebitda)  # fixture deliberately omits it
    assert fy2022.income.ebitda is MISSING


def test_money_first_prefers_explicit_net_issuance_over_repayment():
    # net debt issuance wins when present...
    both = {"netDebtIssuance": 5e9, "debtRepayment": -1e9}
    assert _money_first(both, ("netDebtIssuance", "debtRepayment"), "USD").amount == 5e9
    # ...and the legacy field is the fallback when it is absent
    legacy = {"debtRepayment": -1e9}
    assert _money_first(legacy, ("netDebtIssuance", "debtRepayment"), "USD").amount == -1e9
    # neither present, or non-numeric, becomes MISSING (never 0)
    assert is_missing(_money_first({}, ("netDebtIssuance", "debtRepayment"), "USD"))
    assert is_missing(_money_first({"netDebtIssuance": None}, ("netDebtIssuance",), "USD"))


@responses.activate
def test_empty_statements_is_symbol_not_found(tmp_path):
    for path in ("income-statement", "balance-sheet-statement", "cash-flow-statement"):
        responses.get(f"{V3}/{path}/NOPE", json=[])
    result = adapter(tmp_path).get_history(Ticker("NOPE"), PeriodType.ANNUAL, 10)
    assert result.is_err()
    assert isinstance(result.error, SymbolNotFound)


@responses.activate
def test_reference_dcf(tmp_path):
    responses.get(f"{V3}/discounted-cash-flow/TEST", json=load_fixture("dcf_test.json"))
    assert adapter(tmp_path).get_reference_dcf(Ticker("TEST")).unwrap() == 123.45


@responses.activate
def test_missing_reference_dcf_is_none_not_error(tmp_path):
    responses.get(f"{V3}/discounted-cash-flow/TEST", json=[])
    assert adapter(tmp_path).get_reference_dcf(Ticker("TEST")).unwrap() is None


@responses.activate
def test_peers_parsed_and_malformed_symbols_skipped(tmp_path):
    responses.get(f"{V4}/stock_peers", json=load_fixture("peers_test.json"))
    peers = adapter(tmp_path).get_peers(Ticker("TEST")).unwrap()
    assert [p.symbol for p in peers] == ["PEERA", "PEERB"]  # "bad ticker!" dropped


@responses.activate
def test_screen_passes_filters_through(tmp_path):
    responses.get(f"{STABLE}/company-screener", json=load_fixture("screener.json"))
    rows = adapter(tmp_path).screen({"sector": "Technology", "limit": 50}).unwrap()
    assert len(rows) == 2
    url = responses.calls[0].request.url
    assert "sector=Technology" in url and "limit=50" in url


