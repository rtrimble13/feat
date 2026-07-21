"""Named scenario assumption sets (bull / base / bear).

A scenario shifts the growth and discount assumptions of a valuation in
a disclosed, symmetric way. The deltas are deliberately simple defaults;
analysts override any of them with explicit flags.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from feat.domain.valuation import ValuationInputs


@dataclass(frozen=True, slots=True)
class ScenarioShift:
    name: str
    growth_delta: float
    terminal_growth_delta: float
    discount_delta: float


SCENARIOS: dict[str, ScenarioShift] = {
    "base": ScenarioShift("base", 0.0, 0.0, 0.0),
    "bull": ScenarioShift("bull", +0.03, +0.005, -0.005),
    "bear": ScenarioShift("bear", -0.03, -0.005, +0.010),
}


def apply_scenario(inputs: ValuationInputs, name: str) -> ValuationInputs:
    try:
        s = SCENARIOS[name]
    except KeyError:
        raise ValueError(
            f"unknown scenario {name!r}; choose from {', '.join(sorted(SCENARIOS))}"
        ) from None
    return replace(
        inputs,
        growth=inputs.growth + s.growth_delta,
        terminal_growth=inputs.terminal_growth + s.terminal_growth_delta,
        wacc=inputs.wacc + s.discount_delta,
        cost_of_equity=inputs.cost_of_equity + s.discount_delta,
    )
