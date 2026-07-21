"""Reconstruction of FCFF and FCFE from raw reported statements.

    FCFF = OCF + interest expense x (1 - tax rate) - capex
    FCFE = OCF - capex + net debt issued

FMP reports capex as a negative investing outflow; the sign is
normalized here. If OCF or capex is missing the result is None — a
free-cash-flow figure built on a silent zero would corrupt every DCF.
"""

from __future__ import annotations


def fcff(
    operating_cash_flow: float | None,
    interest_expense: float | None,
    tax_rate: float | None,
    capital_expenditure: float | None,
) -> float | None:
    if operating_cash_flow is None or capital_expenditure is None:
        return None
    interest = abs(interest_expense) if interest_expense is not None else 0.0
    rate = tax_rate if tax_rate is not None else 0.0
    return operating_cash_flow + interest * (1.0 - rate) - abs(capital_expenditure)


def fcfe(
    operating_cash_flow: float | None,
    capital_expenditure: float | None,
    net_debt_issued: float | None,
) -> float | None:
    if operating_cash_flow is None or capital_expenditure is None:
        return None
    borrowing = net_debt_issued if net_debt_issued is not None else 0.0
    return operating_cash_flow - abs(capital_expenditure) + borrowing
