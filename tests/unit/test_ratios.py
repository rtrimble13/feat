"""Ratio math: standard cases and the edge cases that corrupt models."""

import pytest

from feat.domain.ratios import div, avg
from feat.domain.ratios import (
    cashflow_quality,
    dupont,
    efficiency,
    leverage,
    liquidity,
    pershare,
    profitability,
)
from feat.services import derive
from tests.conftest import make_statement_set


class TestDiv:
    def test_none_propagates(self):
        assert div(None, 2) is None
        assert div(2, None) is None

    def test_zero_denominator_is_none_not_infinity(self):
        assert div(1, 0) is None

    def test_normal(self):
        assert div(1, 4) == 0.25


class TestProfitability:
    def test_margins(self):
        assert profitability.gross_margin(40, 100) == 0.4
        assert profitability.net_margin(19.2, 100) == pytest.approx(0.192)

    def test_zero_revenue_gives_none(self):
        assert profitability.gross_margin(40, 0) is None

    def test_roe_uses_average_equity_when_prior_given(self):
        assert profitability.return_on_equity(10, 100, 150) == pytest.approx(10 / 125)

    def test_negative_equity_roe_still_computes_sign(self):
        # negative equity: ratio is reported (negative), not hidden
        assert profitability.return_on_equity(10, -50) == pytest.approx(-0.2)

    def test_roic_definition(self):
        # NOPAT = 25 * (1 - 0.2) = 20 ; IC = 30 + 60 - 20 = 70
        tax = profitability.effective_tax_rate(4.8, 24)
        assert tax == pytest.approx(0.2)
        nopat = profitability.nopat(25, tax)
        ic = profitability.invested_capital(30, 60, 20)
        assert profitability.return_on_invested_capital(nopat, ic) == pytest.approx(20 / 70)

    def test_tax_rate_clamped_on_tax_benefit(self):
        assert profitability.effective_tax_rate(-5, 10) == 0.0
        assert profitability.effective_tax_rate(15, 10) == 1.0

    def test_spread(self):
        assert profitability.roic_wacc_spread(0.12, 0.09) == pytest.approx(0.03)
        assert profitability.roic_wacc_spread(None, 0.09) is None


class TestLiquidityLeverageEfficiency:
    def test_current_and_quick(self):
        assert liquidity.current_ratio(45, 20) == 2.25
        assert liquidity.quick_ratio(20, 5, 10, 20) == pytest.approx(1.75)

    def test_quick_ratio_missing_cash_is_none(self):
        assert liquidity.quick_ratio(None, 5, 10, 20) is None

    def test_net_debt_needs_both_inputs(self):
        assert leverage.net_debt(30, 20) == 10
        assert leverage.net_debt(30, None) is None

    def test_interest_coverage_uses_abs_interest(self):
        assert leverage.interest_coverage(25, -1) == 25.0

    def test_cash_conversion_cycle(self):
        dso = efficiency.days_sales_outstanding(10, 100)
        dio = efficiency.days_inventory_outstanding(5, 60)
        dpo = efficiency.days_payable_outstanding(8, 60)
        ccc = efficiency.cash_conversion_cycle(dso, dio, dpo)
        assert ccc == pytest.approx(dso + dio - dpo)
        assert efficiency.cash_conversion_cycle(dso, None, dpo) is None


class TestPerShareAndQuality:
    def test_dps_normalizes_sign(self):
        assert pershare.dividends_per_share(-3, 10) == pytest.approx(0.3)

    def test_dilution_rate(self):
        assert pershare.dilution_rate(105, 100) == pytest.approx(0.05)

    def test_accruals_ratio(self):
        assert cashflow_quality.accruals_ratio(19.2, 28, 120) == pytest.approx(
            (19.2 - 28) / 120
        )


class TestDuPont:
    def test_three_way_ties_to_roe(self):
        d = dupont.dupont_3way(19.2, 100, 120, 60)
        assert d.roe == pytest.approx(19.2 / 60)

    def test_five_way_ties_to_roe(self):
        d = dupont.dupont_5way(19.2, 24, 25, 100, 120, 60)
        assert d.roe == pytest.approx(19.2 / 60)

    def test_missing_component_yields_none(self):
        d = dupont.dupont_3way(19.2, None, 120, 60)
        assert d.roe is None


class TestDeriveRows:
    def test_rows_from_statement_set(self):
        current = make_statement_set(2024)
        prior = make_statement_set(2023, revenue=90.0, total_assets=110.0, total_equity=55.0)
        rows = derive.ratio_rows(current, prior)
        assert rows["gross_margin"] == pytest.approx(0.4)
        assert rows["revenue_growth"] == pytest.approx(100 / 90 - 1)
        assert rows["net_debt"] == pytest.approx(10.0)
        # FCFF = 28 + 1*(1-0.2) - 8 = 20.8 ; FCFE = 28 - 8 + (-1) = 19.0
        assert rows["fcff"] == pytest.approx(20.8)
        assert rows["fcfe"] == pytest.approx(19.0)

    def test_missing_inputs_flag_not_zero(self):
        current = make_statement_set(2024, revenue=None, operating_cash_flow=None,
                                     free_cash_flow=None)
        rows = derive.ratio_rows(current, None)
        assert rows["gross_margin"] is None
        assert rows["fcff"] is None
        assert rows["ocf_to_net_income"] is None

    def test_avg_helper(self):
        assert avg(10, 20) == 15
        assert avg(10, None) is None
