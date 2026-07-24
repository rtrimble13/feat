"""Sensitivity grid: fair value across WACC x terminal-growth combinations.

Cells where the model degenerates (r <= g, or the model errors) are None
and render as "—" — never a fabricated number.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from feat.domain.errors import Ok
from feat.domain.valuation import ValuationInputs
from feat.domain.valuation.factory import ValuationModel


@dataclass(frozen=True, slots=True)
class SensitivityGrid:
    wacc_values: list[float]
    growth_values: list[float]
    #: rows indexed by wacc, columns by terminal growth
    fair_values: list[list[float | None]]


def wacc_growth_grid(
    model: ValuationModel,
    inputs: ValuationInputs,
    wacc_step: float = 0.005,
    growth_step: float = 0.005,
    steps: int = 2,
) -> SensitivityGrid:
    wacc_values = [inputs.wacc + wacc_step * i for i in range(-steps, steps + 1)]
    growth_values = [inputs.terminal_growth + growth_step * i for i in range(-steps, steps + 1)]
    rows: list[list[float | None]] = []
    for w in wacc_values:
        row: list[float | None] = []
        for g in growth_values:
            trial = replace(inputs, wacc=w, cost_of_equity=w, terminal_growth=g)
            result = model(trial)
            row.append(result.value.fair_value_per_share if isinstance(result, Ok) else None)
        rows.append(row)
    return SensitivityGrid(wacc_values=wacc_values, growth_values=growth_values, fair_values=rows)
