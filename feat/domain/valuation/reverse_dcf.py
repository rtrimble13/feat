"""Reverse DCF: solve for the growth rate the current price implies.

Holds every other FCFF-DCF assumption fixed and bisects on the initial
growth rate until the model value matches the market price. The result
is a hurdle to judge ("does 14%/yr for 5 years sound achievable?"),
not a forecast.
"""

from __future__ import annotations

from feat.domain.errors import Err, InvalidInput, MissingRequiredField, Ok, Result
from feat.domain.valuation import ValuationInputs, ValuationOutcome
from feat.domain.valuation.dcf import run_dcf

_GROWTH_LO = -0.50
_GROWTH_HI = 1.00
_TOLERANCE = 1e-6
_MAX_ITER = 200


def _fair_value(inputs: ValuationInputs, growth: float) -> float:
    core = run_dcf(
        base_flow=inputs.base_fcff,  # type: ignore[arg-type]
        growth=growth,
        terminal_growth=inputs.terminal_growth,
        discount_rate=inputs.wacc,
        years=inputs.horizon_years,
    )
    return (core.pv_perpetuity - inputs.net_debt) / inputs.shares_diluted  # type: ignore[operator]


def implied_growth(inputs: ValuationInputs) -> float | None:
    """Bisection on growth; None if the price is outside the bracket."""
    lo, hi = _GROWTH_LO, _GROWTH_HI
    price = inputs.price
    assert price is not None
    f_lo = _fair_value(inputs, lo) - price
    f_hi = _fair_value(inputs, hi) - price
    if f_lo * f_hi > 0:
        return None
    for _ in range(_MAX_ITER):
        mid = (lo + hi) / 2.0
        f_mid = _fair_value(inputs, mid) - price
        if abs(f_mid) < _TOLERANCE or (hi - lo) / 2.0 < _TOLERANCE:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def value(inputs: ValuationInputs) -> Result[ValuationOutcome, "object"]:
    if inputs.price is None or inputs.price <= 0:
        return Err(MissingRequiredField("market price unavailable"))
    if inputs.base_fcff is None or inputs.base_fcff <= 0:
        return Err(MissingRequiredField(
            "positive base FCFF required to invert the DCF"
        ))
    if inputs.shares_diluted is None or inputs.shares_diluted <= 0:
        return Err(MissingRequiredField("diluted share count unavailable"))
    if inputs.net_debt is None:
        return Err(MissingRequiredField("net debt unavailable"))
    if inputs.wacc <= inputs.terminal_growth:
        return Err(InvalidInput(
            f"WACC ({inputs.wacc:.2%}) must exceed terminal growth "
            f"({inputs.terminal_growth:.2%})"
        ))

    g = implied_growth(inputs)
    if g is None:
        return Err(InvalidInput(
            "no growth rate between -50% and +100% reproduces the current "
            "price under these assumptions — revisit WACC or terminal growth"
        ))

    return Ok(ValuationOutcome(
        model="reverse-dcf",
        fair_value_per_share=inputs.price,
        price=inputs.price,
        margin_of_safety=None,
        assumptions={
            "base_fcff": inputs.base_fcff,
            "terminal_growth": inputs.terminal_growth,
            "wacc": inputs.wacc,
            "horizon_years": inputs.horizon_years,
            "net_debt": inputs.net_debt,
            "shares_diluted": inputs.shares_diluted,
        },
        details={"implied_growth": g},
    ))
