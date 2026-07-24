"""Unit coverage for the compare and screen services.

Both services are exercised against an in-memory fake repository (no HTTP),
covering the peer-selection, median aggregation, filter-mapping and
validation logic that has no other test.
"""

from __future__ import annotations

import pytest

from feat.domain.entities import Company, FinancialHistory
from feat.domain.errors import Err, InsufficientHistory, Ok, SymbolNotFound
from feat.domain.ports import FundamentalsRepository
from feat.domain.values import Money, Ticker
from feat.services.compare_peers import ComparePeers
from feat.services.screen_universe import ScreenFilters, ScreenUniverse
from tests.conftest import make_statement_set


def make_company(symbol: str, *, price: float = 100.0, market_cap: float = 100e9,
                 shares: float = 1e9, sector: str = "Technology") -> Company:
    return Company(
        ticker=Ticker(symbol),
        name=f"{symbol} Co",
        sector=sector,
        currency="USD",
        market_cap=Money(market_cap),
        price=Money(price),
        shares_outstanding=shares,
        beta=1.0,
    )


def make_history(*, revenue_latest: float, revenue_prior: float) -> FinancialHistory:
    return FinancialHistory([
        make_statement_set(2024, revenue=revenue_latest),
        make_statement_set(2023, revenue=revenue_prior),
    ])


class FakeFundamentals(FundamentalsRepository):
    """Configurable in-memory FundamentalsRepository for service tests."""

    def __init__(self) -> None:
        self.companies: dict[str, Company] = {}
        self.histories: dict[str, FinancialHistory] = {}
        self.peers: dict[str, list[Ticker]] = {}
        self.screen_rows: list[dict] = []
        self.company_errors: dict[str, object] = {}

    def add(self, symbol: str, *, revenue_latest: float = 120.0,
            revenue_prior: float = 100.0, **company_kwargs) -> None:
        self.companies[symbol] = make_company(symbol, **company_kwargs)
        self.histories[symbol] = make_history(
            revenue_latest=revenue_latest, revenue_prior=revenue_prior
        )

    def get_company(self, ticker: Ticker):
        sym = ticker.symbol
        if sym in self.company_errors:
            return Err(self.company_errors[sym])
        if sym in self.companies:
            return Ok(self.companies[sym])
        return Err(SymbolNotFound(f"{sym} not found"))

    def get_history(self, ticker: Ticker, period, years: int):
        sym = ticker.symbol
        if sym in self.histories:
            return Ok(self.histories[sym])
        return Err(SymbolNotFound(f"no history for {sym}"))

    def get_reference_dcf(self, ticker: Ticker):
        return Ok(None)

    def get_peers(self, ticker: Ticker):
        return Ok(self.peers.get(ticker.symbol, []))

    def screen(self, filters):
        return Ok(list(self.screen_rows))


# --- ComparePeers ---------------------------------------------------------


class TestComparePeers:
    def test_compares_multiple_tickers_and_computes_medians(self):
        repo = FakeFundamentals()
        repo.add("TEST", revenue_latest=120.0, revenue_prior=100.0)
        repo.add("OTHER", revenue_latest=80.0, revenue_prior=100.0)
        report = ComparePeers(repo).run(
            [Ticker("TEST"), Ticker("OTHER")], metrics=["revenue"]
        ).unwrap()

        assert set(report.rows) == {"TEST", "OTHER"}
        assert report.rows["TEST"]["revenue"] == pytest.approx(120.0)
        assert report.rows["OTHER"]["revenue"] == pytest.approx(80.0)
        # median of an even set = mean of the two middle values
        assert report.medians["revenue"] == pytest.approx(100.0)
        assert report.failures == {}

    def test_partial_failure_is_recorded_and_run_continues(self):
        repo = FakeFundamentals()
        repo.add("TEST")
        report = ComparePeers(repo).run(
            [Ticker("TEST"), Ticker("NOPE")], metrics=["revenue"]
        ).unwrap()

        assert list(report.rows) == ["TEST"]           # good ticker still ran
        assert "NOPE" in report.failures                # bad one is reported
        assert isinstance(report.failures["NOPE"], SymbolNotFound)

    def test_all_failures_returns_first_error(self):
        repo = FakeFundamentals()
        result = ComparePeers(repo).run([Ticker("NOPE"), Ticker("GONE")])
        assert result.is_err()
        assert isinstance(result.error, SymbolNotFound)

    def test_empty_history_is_insufficient(self):
        repo = FakeFundamentals()
        repo.companies["TEST"] = make_company("TEST")
        repo.histories["TEST"] = FinancialHistory([])   # profile ok, no statements
        result = ComparePeers(repo).run([Ticker("TEST")])
        assert result.is_err()
        assert isinstance(result.error, InsufficientHistory)

    def test_default_metrics_used_when_none_requested(self):
        repo = FakeFundamentals()
        repo.add("TEST")
        report = ComparePeers(repo).run([Ticker("TEST")]).unwrap()
        assert "revenue" in report.metrics and "pe" in report.metrics
        # every requested metric appears in each row (value may be None)
        assert set(report.rows["TEST"]) == set(report.metrics)

    def test_revenue_growth_metric_is_computed_from_prior(self):
        repo = FakeFundamentals()
        repo.add("TEST", revenue_latest=110.0, revenue_prior=100.0)
        report = ComparePeers(repo).run(
            [Ticker("TEST")], metrics=["revenue_growth"]
        ).unwrap()
        assert report.rows["TEST"]["revenue_growth"] == pytest.approx(0.10)

    def test_expand_peers_puts_anchor_first_and_drops_self(self):
        repo = FakeFundamentals()
        repo.peers["TEST"] = [Ticker("TEST"), Ticker("PEERA"), Ticker("PEERB")]
        tickers = ComparePeers(repo).expand_peers(Ticker("TEST")).unwrap()
        assert tickers[0] == Ticker("TEST")            # anchor first
        assert tickers.count(Ticker("TEST")) == 1      # self de-duplicated
        assert Ticker("PEERA") in tickers and Ticker("PEERB") in tickers

    def test_expand_peers_propagates_repository_error(self):
        class FailingPeers(FakeFundamentals):
            def get_peers(self, ticker):
                return Err(SymbolNotFound("no peers"))

        result = ComparePeers(FailingPeers()).expand_peers(Ticker("TEST"))
        assert result.is_err()


# --- ScreenUniverse -------------------------------------------------------


class TestScreenFilters:
    def test_maps_all_filters_to_fmp_param_names(self):
        params = ScreenFilters(
            sector="Technology", industry="Hardware", exchange="NASDAQ",
            country="US", min_market_cap=1e10, max_market_cap=1e12,
            min_price=10.0, max_price=500.0, min_beta=0.5, max_beta=2.0,
            min_volume=1e6, min_dividend=1.0, limit=25,
        ).to_fmp_params()
        assert params == {
            "sector": "Technology", "industry": "Hardware", "exchange": "NASDAQ",
            "country": "US", "marketCapMoreThan": 1e10, "marketCapLowerThan": 1e12,
            "priceMoreThan": 10.0, "priceLowerThan": 500.0, "betaMoreThan": 0.5,
            "betaLowerThan": 2.0, "volumeMoreThan": 1e6, "dividendMoreThan": 1.0,
            "limit": 25,
        }

    def test_omits_unset_filters_but_always_sends_limit(self):
        params = ScreenFilters(sector="Technology").to_fmp_params()
        assert params == {"sector": "Technology", "limit": 50}


class TestScreenUniverse:
    def test_parses_rows_and_skips_records_without_symbol(self):
        repo = FakeFundamentals()
        repo.screen_rows = [
            {"symbol": "TEST", "companyName": "Test Co", "sector": "Technology",
             "marketCap": 100e9, "price": 100.0, "beta": 1.2,
             "lastAnnualDividend": 3.0, "exchangeShortName": "NASDAQ"},
            {"companyName": "No Symbol Co"},          # dropped: no symbol
        ]
        report = ScreenUniverse(repo).run(ScreenFilters(sector="Technology")).unwrap()
        assert [r.symbol for r in report.rows] == ["TEST"]
        row = report.rows[0]
        assert row.market_cap == pytest.approx(100e9)
        assert row.dividend == pytest.approx(3.0)
        assert row.exchange == "NASDAQ"

    def test_non_numeric_and_bool_fields_become_none(self):
        repo = FakeFundamentals()
        repo.screen_rows = [
            {"symbol": "TEST", "marketCap": "n/a", "price": True, "beta": None},
        ]
        row = ScreenUniverse(repo).run(ScreenFilters()).unwrap().rows[0]
        assert row.market_cap is None   # string rejected, never coerced
        assert row.price is None        # bool rejected (isinstance(True, int) trap)
        assert row.beta is None

    def test_exchange_falls_back_to_long_name(self):
        repo = FakeFundamentals()
        repo.screen_rows = [{"symbol": "TEST", "exchange": "New York Stock Exchange"}]
        row = ScreenUniverse(repo).run(ScreenFilters()).unwrap().rows[0]
        assert row.exchange == "New York Stock Exchange"

    @pytest.mark.parametrize("bad_limit", [0, 1001, -5])
    def test_limit_out_of_bounds_is_invalid_input(self, bad_limit):
        repo = FakeFundamentals()
        result = ScreenUniverse(repo).run(ScreenFilters(limit=bad_limit))
        assert result.is_err()
        from feat.domain.errors import InvalidInput
        assert isinstance(result.error, InvalidInput)

    def test_repository_error_propagates(self):
        class FailingScreen(FakeFundamentals):
            def screen(self, filters):
                return Err(SymbolNotFound("screener down"))

        result = ScreenUniverse(FailingScreen()).run(ScreenFilters(limit=10))
        assert result.is_err()
