"""Ratio modules: profitability, liquidity, leverage, efficiency, per-share,
cash-flow quality and DuPont decomposition.

Every function is pure, takes plain floats (or ``None`` for missing
inputs) and returns ``None`` whenever an input is missing or a
denominator is zero — a gap is flagged, never silently zeroed.
Formulas are documented in ``docs/formulas.md``.
"""

from __future__ import annotations


def div(numerator: float | None, denominator: float | None) -> float | None:
    """Safe division: None-in → None-out; zero denominator → None."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def avg(*values: float | None) -> float | None:
    """Average of the given values; any missing input poisons the result."""
    if not values or any(v is None for v in values):
        return None
    return sum(v for v in values if v is not None) / len(values)
