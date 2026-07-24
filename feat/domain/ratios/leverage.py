"""Leverage and coverage ratios.

- net debt                = total debt - cash & equivalents
- debt / EBITDA           = total debt / EBITDA
- net debt / EBITDA       = net debt / EBITDA
- debt / equity           = total debt / total equity
- interest coverage       = EBIT / interest expense
"""

from __future__ import annotations

from feat.domain.ratios import div


def net_debt(total_debt: float | None, cash_and_equivalents: float | None) -> float | None:
    if total_debt is None or cash_and_equivalents is None:
        return None
    return total_debt - cash_and_equivalents


def debt_to_ebitda(total_debt: float | None, ebitda: float | None) -> float | None:
    return div(total_debt, ebitda)


def net_debt_to_ebitda(net_debt_value: float | None, ebitda: float | None) -> float | None:
    return div(net_debt_value, ebitda)


def debt_to_equity(total_debt: float | None, total_equity: float | None) -> float | None:
    return div(total_debt, total_equity)


def interest_coverage(
    operating_income: float | None, interest_expense: float | None
) -> float | None:
    if interest_expense is not None:
        interest_expense = abs(interest_expense)
    return div(operating_income, interest_expense)
