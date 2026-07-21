"""Entities: history ordering, TTM roll-up, missing propagation."""

from feat.domain.entities import FinancialHistory
from feat.domain.values import is_missing
from tests.conftest import make_statement_set, quarter_period


def test_history_sorted_latest_first():
    history = FinancialHistory([
        make_statement_set(2022), make_statement_set(2024), make_statement_set(2023),
    ])
    assert [p.fiscal_year for p in history.periods] == [2024, 2023, 2022]
    assert history.latest.period.fiscal_year == 2024


def test_ttm_sums_four_quarters():
    quarters = [
        make_statement_set(period=quarter_period(2024, q), revenue=10.0 + q)
        for q in (1, 2, 3, 4)
    ]
    history = FinancialHistory(quarters)
    ttm = history.ttm_income()
    assert ttm is not None
    assert ttm.revenue.amount == (11 + 12 + 13 + 14)


def test_ttm_requires_four_quarters():
    history = FinancialHistory([
        make_statement_set(period=quarter_period(2024, q)) for q in (1, 2, 3)
    ])
    assert history.ttm_income() is None


def test_ttm_missing_quarter_poisons_sum_never_zeroes():
    quarters = [
        make_statement_set(period=quarter_period(2024, q),
                           revenue=None if q == 2 else 10.0)
        for q in (1, 2, 3, 4)
    ]
    ttm = FinancialHistory(quarters).ttm_income()
    assert ttm is not None
    assert is_missing(ttm.revenue)  # not 30.0


def test_trend_is_oldest_first_with_gaps():
    history = FinancialHistory([
        make_statement_set(2024, revenue=120.0),
        make_statement_set(2023, revenue=None),
        make_statement_set(2022, revenue=100.0),
    ])
    assert history.trend("revenue") == [100.0, None, 120.0]


def test_common_size_income_scales_by_revenue():
    history = FinancialHistory([make_statement_set(2024, revenue=100.0, gross_profit=40.0)])
    row = history.common_size_income()[0]
    assert row["gross_profit"] == 0.4
