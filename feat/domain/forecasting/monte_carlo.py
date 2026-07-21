"""Monte Carlo over key valuation inputs.

Draws growth, terminal growth and the discount rate from independent
normal distributions centered on the point assumptions, runs the model
per draw, and reports the *distribution* of intrinsic value (percentiles),
not a falsely precise point. The RNG is seeded by the caller so runs are
reproducible and testable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from feat.domain.valuation import ValuationInputs
from feat.domain.valuation.factory import ValuationModel


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    draws: int
    valid_draws: int
    percentiles: dict[int, float]  # 5, 25, 50, 75, 95
    prob_below_price: float | None  # P(fair value < current price)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        raise ValueError("empty sample")
    k = (len(sorted_values) - 1) * pct / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_values) - 1)
    frac = k - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def simulate(
    model: ValuationModel,
    inputs: ValuationInputs,
    draws: int,
    seed: int,
    growth_vol: float = 0.02,
    terminal_growth_vol: float = 0.005,
    discount_vol: float = 0.01,
) -> MonteCarloResult:
    if draws < 100:
        raise ValueError("need at least 100 draws for meaningful percentiles")
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(draws):
        trial = replace(
            inputs,
            growth=rng.gauss(inputs.growth, growth_vol),
            terminal_growth=rng.gauss(inputs.terminal_growth, terminal_growth_vol),
            wacc=rng.gauss(inputs.wacc, discount_vol),
            cost_of_equity=rng.gauss(inputs.cost_of_equity, discount_vol),
        )
        result = model(trial)
        if result.is_ok():
            values.append(result.value.fair_value_per_share)
    if not values:
        raise ValueError("no valid Monte Carlo draws — assumptions too close to degenerate")
    values.sort()
    prob_below = None
    if inputs.price is not None:
        prob_below = sum(1 for v in values if v < inputs.price) / len(values)
    return MonteCarloResult(
        draws=draws,
        valid_draws=len(values),
        percentiles={p: _percentile(values, p) for p in (5, 25, 50, 75, 95)},
        prob_below_price=prob_below,
    )
