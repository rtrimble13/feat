"""FCFF DCF: firm value discounted at WACC.

    EV      = PV(FCFF explicit) + PV(terminal value)
    Equity  = EV - net debt
    Value/sh = Equity / diluted shares

FCFF is reconstructed upstream from raw statements as
    FCFF = OCF + interest expense x (1 - tax rate) - capex.
"""

from __future__ import annotations

from feat.domain.errors import AnalysisError, Err, InvalidInput, MissingRequiredField, Ok, Result
from feat.domain.valuation import ValuationInputs, ValuationOutcome, margin_of_safety
from feat.domain.valuation.dcf import run_dcf


def value(inputs: ValuationInputs) -> Result[ValuationOutcome, AnalysisError]:
    if inputs.base_fcff is None:
        return Err(MissingRequiredField(
            "FCFF could not be reconstructed (missing operating cash flow, "
            "interest expense or capex in the reported statements)"
        ))
    if inputs.shares_diluted is None or inputs.shares_diluted <= 0:
        return Err(MissingRequiredField("diluted share count unavailable"))
    if inputs.net_debt is None:
        return Err(MissingRequiredField("net debt unavailable (total debt or cash missing)"))
    if inputs.wacc <= inputs.terminal_growth:
        return Err(InvalidInput(
            f"WACC ({inputs.wacc:.2%}) must exceed terminal growth "
            f"({inputs.terminal_growth:.2%})"
        ))
    if inputs.base_fcff <= 0:
        return Err(InvalidInput(
            "base FCFF is not positive; a perpetuity DCF on negative flows is "
            "meaningless — consider --model residual-income or relative"
        ))

    core = run_dcf(
        base_flow=inputs.base_fcff,
        growth=inputs.growth,
        terminal_growth=inputs.terminal_growth,
        discount_rate=inputs.wacc,
        years=inputs.horizon_years,
        exit_metric_base=inputs.base_ebitda,
        exit_multiple=inputs.exit_ev_ebitda,
    )
    equity = core.pv_perpetuity - inputs.net_debt
    fair = equity / inputs.shares_diluted
    fair_alt = None
    if core.pv_exit is not None:
        fair_alt = (core.pv_exit - inputs.net_debt) / inputs.shares_diluted

    return Ok(ValuationOutcome(
        model="dcf-fcff",
        fair_value_per_share=fair,
        fair_value_alt=fair_alt,
        price=inputs.price,
        margin_of_safety=margin_of_safety(inputs.price, fair),
        assumptions={
            "base_fcff": inputs.base_fcff,
            "growth_initial": inputs.growth,
            "terminal_growth": inputs.terminal_growth,
            "wacc": inputs.wacc,
            "horizon_years": inputs.horizon_years,
            "exit_ev_ebitda": inputs.exit_ev_ebitda,
            "net_debt": inputs.net_debt,
            "shares_diluted": inputs.shares_diluted,
        },
        details={
            "projected_fcff": core.projected_flows,
            "terminal_value_perpetuity": core.tv_perpetuity,
            "terminal_value_exit": core.tv_exit,
            "enterprise_value": core.pv_perpetuity,
            "equity_value": equity,
        },
    ))
