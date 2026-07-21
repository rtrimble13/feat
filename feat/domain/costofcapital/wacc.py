"""Market-value-weighted WACC.

    WACC = E/(D+E) x r_e + D/(D+E) x r_d x (1 - t)

E = market value of equity (market cap), D = market value of debt
(book total debt as the standard proxy), r_d from interest expense /
total debt or a rating-implied spread over the risk-free rate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WaccInputs:
    market_value_equity: float
    market_value_debt: float
    cost_of_equity: float
    cost_of_debt: float
    tax_rate: float


def cost_of_debt_from_interest(
    interest_expense: float | None, total_debt: float | None
) -> float | None:
    """Effective interest rate on outstanding debt; None if unknowable."""
    if interest_expense is None or total_debt is None or total_debt <= 0:
        return None
    return abs(interest_expense) / total_debt


def wacc(inputs: WaccInputs) -> float:
    e, d = inputs.market_value_equity, inputs.market_value_debt
    if e < 0 or d < 0:
        raise ValueError("market values must be non-negative")
    total = e + d
    if total == 0:
        raise ValueError("zero total capital")
    if not 0.0 <= inputs.tax_rate <= 1.0:
        raise ValueError(f"tax rate must be a fraction in [0, 1], got {inputs.tax_rate}")
    return (e / total) * inputs.cost_of_equity + (d / total) * inputs.cost_of_debt * (
        1.0 - inputs.tax_rate
    )
