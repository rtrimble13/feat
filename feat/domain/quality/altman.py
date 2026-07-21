"""Altman Z-score (original 1968 form, public manufacturers):

    Z = 1.2 A + 1.4 B + 3.3 C + 0.6 D + 1.0 E

    A = working capital / total assets
    B = retained earnings / total assets
    C = EBIT / total assets
    D = market value of equity / total liabilities
    E = revenue / total assets

Zones: Z > 2.99 safe; 1.81-2.99 grey; < 1.81 distress.
Returns None when any component input is missing.
"""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.ratios import div


@dataclass(frozen=True, slots=True)
class AltmanResult:
    z: float
    zone: str
    components: dict[str, float]


def altman_z(
    total_current_assets: float | None,
    total_current_liabilities: float | None,
    total_assets: float | None,
    retained_earnings: float | None,
    ebit: float | None,
    market_cap: float | None,
    total_liabilities: float | None,
    revenue: float | None,
) -> AltmanResult | None:
    if total_current_assets is None or total_current_liabilities is None:
        return None
    working_capital = total_current_assets - total_current_liabilities
    a = div(working_capital, total_assets)
    b = div(retained_earnings, total_assets)
    c = div(ebit, total_assets)
    d = div(market_cap, total_liabilities)
    e = div(revenue, total_assets)
    if any(x is None for x in (a, b, c, d, e)):
        return None
    z = 1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e  # type: ignore[operator]
    zone = "safe" if z > 2.99 else ("grey" if z >= 1.81 else "distress")
    return AltmanResult(z=z, zone=zone, components={"A": a, "B": b, "C": c, "D": d, "E": e})
