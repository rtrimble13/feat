"""Entities: history ordering and trend/missing propagation."""

from feat.domain.entities import FinancialHistory
from tests.conftest import make_statement_set


def test_history_sorted_latest_first():
    history = FinancialHistory([
        make_statement_set(2022), make_statement_set(2024), make_statement_set(2023),
    ])
    assert [p.fiscal_year for p in history.periods] == [2024, 2023, 2022]
    assert history.latest.period.fiscal_year == 2024


def test_trend_is_oldest_first_with_gaps():
    history = FinancialHistory([
        make_statement_set(2024, revenue=120.0),
        make_statement_set(2023, revenue=None),
        make_statement_set(2022, revenue=100.0),
    ])
    assert history.trend("revenue") == [100.0, None, 120.0]
