"""FCFE DCF: equity cash flows discounted at the cost of equity.

    Equity value = PV(FCFE explicit) + PV(terminal value)
    Value/sh     = Equity / diluted shares

FCFE is reconstructed upstream as
    FCFE = OCF - capex + net debt issued.
"""

from __future__ import annotations

from feat.domain.errors import AnalysisError, Err, InvalidInput, MissingRequiredField, Ok, Result
from feat.domain.valuation import ValuationInputs, ValuationOutcome, margin_of_safety
from feat.domain.valuation.dcf import run_dcf


def value(inputs: ValuationInputs) -> Result[ValuationOutcome, AnalysisError]:
    if inputs.base_fcfe is None:
        return Err(MissingRequiredField(
            "FCFE could not be reconstructed (missing operating cash flow, "
            "capex or net borrowing in the reported statements)"
        ))
    if inputs.shares_diluted is None or inputs.shares_diluted <= 0:
        return Err(MissingRequiredField("diluted share count unavailable"))
    if inputs.cost_of_equity <= inputs.terminal_growth:
        return Err(InvalidInput(
            f"cost of equity ({inputs.cost_of_equity:.2%}) must exceed terminal "
            f"growth ({inputs.terminal_growth:.2%})"
        ))
    if inputs.base_fcfe <= 0:
        return Err(InvalidInput(
            "base FCFE is not positive; a perpetuity DCF on negative flows is "
            "meaningless — consider --model residual-income or relative"
        ))

    core = run_dcf(
        base_flow=inputs.base_fcfe,
        growth=inputs.growth,
        terminal_growth=inputs.terminal_growth,
        discount_rate=inputs.cost_of_equity,
        years=inputs.horizon_years,
    )
    fair = core.pv_perpetuity / inputs.shares_diluted

    return Ok(ValuationOutcome(
        model="dcf-fcfe",
        fair_value_per_share=fair,
        price=inputs.price,
        margin_of_safety=margin_of_safety(inputs.price, fair),
        assumptions={
            "base_fcfe": inputs.base_fcfe,
            "growth_initial": inputs.growth,
            "terminal_growth": inputs.terminal_growth,
            "cost_of_equity": inputs.cost_of_equity,
            "horizon_years": inputs.horizon_years,
            "shares_diluted": inputs.shares_diluted,
        },
        details={
            "projected_fcfe": core.projected_flows,
            "terminal_value_perpetuity": core.tv_perpetuity,
            "equity_value": core.pv_perpetuity,
        },
    ))
