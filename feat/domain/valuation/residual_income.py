"""Residual income model — for financials and asset-heavy names where
free cash flow is noisy.

Clean-surplus projection from current book value:

    RI_t   = (ROE - r_e) x B_{t-1}
    B_t    = B_{t-1} x (1 + ROE x (1 - payout))
    V0     = B0 + sum PV(RI_t) + PV(terminal RI)

Terminal residual income fades via a persistence factor w in [0, 1):
    TV_n = RI_{n+1} / (1 + r_e - w)
w defaults to 0.6 (competition erodes excess returns).
"""

from __future__ import annotations

from feat.domain.errors import AnalysisError, Err, InvalidInput, MissingRequiredField, Ok, Result
from feat.domain.valuation import ValuationInputs, ValuationOutcome, margin_of_safety

DEFAULT_PERSISTENCE = 0.6


def residual_income_value(
    book_value_per_share: float,
    roe: float,
    cost_of_equity: float,
    payout_ratio: float,
    years: int,
    persistence: float = DEFAULT_PERSISTENCE,
) -> tuple[float, list[float]]:
    if not 0.0 <= persistence < 1.0:
        raise ValueError("persistence must be in [0, 1)")
    if not 0.0 <= payout_ratio <= 1.0:
        raise ValueError("payout ratio must be in [0, 1]")
    book = book_value_per_share
    pv_total = 0.0
    ri_series: list[float] = []
    retention = 1.0 - payout_ratio
    for t in range(1, years + 1):
        ri = (roe - cost_of_equity) * book
        ri_series.append(ri)
        pv_total += ri / (1.0 + cost_of_equity) ** t
        book *= 1.0 + roe * retention
    # continuing residual income beyond the horizon, faded by persistence
    ri_next = (roe - cost_of_equity) * book
    tv = ri_next / (1.0 + cost_of_equity - persistence)
    pv_total += tv / (1.0 + cost_of_equity) ** years
    return book_value_per_share + pv_total, ri_series


def value(inputs: ValuationInputs) -> Result[ValuationOutcome, AnalysisError]:
    if inputs.book_value_per_share is None or inputs.book_value_per_share <= 0:
        return Err(MissingRequiredField(
            "book value per share unavailable or non-positive — residual "
            "income needs a positive equity base"
        ))
    if inputs.roe is None:
        return Err(MissingRequiredField("ROE unavailable (net income or equity missing)"))
    payout = inputs.payout_ratio if inputs.payout_ratio is not None else 0.0
    payout = min(max(payout, 0.0), 1.0)
    if inputs.cost_of_equity <= 0:
        return Err(InvalidInput("cost of equity must be positive"))

    fair, ri_series = residual_income_value(
        book_value_per_share=inputs.book_value_per_share,
        roe=inputs.roe,
        cost_of_equity=inputs.cost_of_equity,
        payout_ratio=payout,
        years=inputs.horizon_years,
    )
    if fair <= 0:
        return Err(InvalidInput(
            "residual income value is non-positive under these assumptions — "
            "ROE persistently below the cost of equity"
        ))

    return Ok(ValuationOutcome(
        model="residual-income",
        fair_value_per_share=fair,
        price=inputs.price,
        margin_of_safety=margin_of_safety(inputs.price, fair),
        assumptions={
            "book_value_per_share": inputs.book_value_per_share,
            "roe": inputs.roe,
            "cost_of_equity": inputs.cost_of_equity,
            "payout_ratio": payout,
            "horizon_years": inputs.horizon_years,
            "persistence": DEFAULT_PERSISTENCE,
        },
        details={"residual_income_per_share": ri_series},
    ))
