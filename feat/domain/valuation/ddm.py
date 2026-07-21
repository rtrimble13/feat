"""Dividend discount models: Gordon growth, two-stage, and H-model.

Gordon:     V0 = D1 / (r - g)
Two-stage:  explicit high-growth dividends, then Gordon terminal.
H-model:    V0 = [D0 x (1+gL) + D0 x H x (gS - gL)] / (r - gL),
            H = fade half-life in years.
"""

from __future__ import annotations

from feat.domain.errors import Err, InvalidInput, MissingRequiredField, Ok, Result
from feat.domain.valuation import ValuationInputs, ValuationOutcome, margin_of_safety
from feat.domain.valuation.dcf import present_value, project_flows, terminal_value_perpetuity


def gordon(d1: float, r: float, g: float) -> float:
    if r <= g:
        raise ValueError(f"required return ({r:.2%}) must exceed growth ({g:.2%})")
    return d1 / (r - g)


def two_stage(d0: float, g_high: float, high_years: int, g_terminal: float, r: float) -> float:
    if r <= g_terminal:
        raise ValueError(f"required return ({r:.2%}) must exceed terminal growth ({g_terminal:.2%})")
    dividends = project_flows(d0, [g_high] * high_years)
    tv = terminal_value_perpetuity(dividends[-1], r, g_terminal)
    return present_value(dividends, tv, r)


def h_model(d0: float, g_short: float, g_long: float, half_life_years: float, r: float) -> float:
    if r <= g_long:
        raise ValueError(f"required return ({r:.2%}) must exceed long-run growth ({g_long:.2%})")
    return (d0 * (1.0 + g_long) + d0 * half_life_years * (g_short - g_long)) / (r - g_long)


def value(inputs: ValuationInputs) -> Result[ValuationOutcome, "object"]:
    d0 = inputs.dividends_per_share
    if d0 is None or d0 <= 0:
        return Err(MissingRequiredField(
            "no dividend history: DDM needs a positive dividend per share — "
            "try --model dcf-fcff or residual-income for non-payers"
        ))
    r, g_s, g_l = inputs.cost_of_equity, inputs.growth, inputs.terminal_growth
    if r <= g_l:
        return Err(InvalidInput(
            f"cost of equity ({r:.2%}) must exceed terminal growth ({g_l:.2%})"
        ))

    two = two_stage(d0, g_s, inputs.horizon_years, g_l, r)
    h = h_model(d0, g_s, g_l, inputs.horizon_years / 2.0, r)
    gordon_v = gordon(d0 * (1.0 + g_l), r, g_l)

    return Ok(ValuationOutcome(
        model="ddm",
        fair_value_per_share=two,
        fair_value_alt=h,
        price=inputs.price,
        margin_of_safety=margin_of_safety(inputs.price, two),
        assumptions={
            "dividends_per_share": d0,
            "growth_high": g_s,
            "terminal_growth": g_l,
            "cost_of_equity": r,
            "high_growth_years": inputs.horizon_years,
        },
        details={
            "two_stage": two,
            "h_model": h,
            "gordon": gordon_v,
        },
    ))
