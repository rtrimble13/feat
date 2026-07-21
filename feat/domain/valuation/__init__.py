"""Valuation models (Strategy pattern).

Each model module exposes ``value(inputs: ValuationInputs) ->
Result[ValuationOutcome, AnalysisError]``. ``factory.build_valuation_model``
returns the strategy for a model name. Every model reports the
assumptions it used; nothing is hidden inside the number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ValuationInputs:
    """Everything a valuation strategy might need; models pick what they
    require and return ``MissingRequiredField`` when a needed input is
    absent — absence is an answer, not a zero."""

    ticker: str
    currency: str = "USD"
    price: float | None = None
    shares_diluted: float | None = None
    net_debt: float | None = None
    base_fcff: float | None = None
    base_fcfe: float | None = None
    base_ebitda: float | None = None
    dividends_per_share: float | None = None
    eps: float | None = None
    book_value_per_share: float | None = None
    roe: float | None = None
    payout_ratio: float | None = None
    growth: float = 0.05
    terminal_growth: float = 0.025
    wacc: float = 0.09
    cost_of_equity: float = 0.10
    horizon_years: int = 5
    exit_ev_ebitda: float | None = None


@dataclass(frozen=True, slots=True)
class ValuationOutcome:
    model: str
    fair_value_per_share: float
    price: float | None
    margin_of_safety: float | None
    #: Fair value under the alternate terminal-value method (exit multiple),
    #: shown beside the primary so the analyst can sanity-check the gap.
    fair_value_alt: float | None = None
    assumptions: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)


def margin_of_safety(price: float | None, fair_value: float) -> float | None:
    """1 - price / fair value: positive means the price sits below fair value."""
    if price is None or fair_value <= 0:
        return None
    return 1.0 - price / fair_value
