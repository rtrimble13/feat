"""Relative valuation: multiples for a company and vs peer medians.

Multiples computed (None when an input is missing or non-positive where
positivity is required):

- P/E = price / EPS (diluted)          - EV/EBITDA = EV / EBITDA
- P/B = price / BVPS                   - EV/EBIT   = EV / EBIT
- P/S = market cap / revenue           - EV/Sales  = EV / revenue
- PEG = P/E / (growth x 100)           - EV/FCF    = EV / FCFF
- dividend yield = DPS / price
where EV = market cap + net debt.
"""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.ratios import div


@dataclass(frozen=True, slots=True)
class MultipleInputs:
    price: float | None = None
    market_cap: float | None = None
    net_debt: float | None = None
    eps_diluted: float | None = None
    book_value_per_share: float | None = None
    revenue: float | None = None
    ebitda: float | None = None
    ebit: float | None = None
    fcf: float | None = None
    dividends_per_share: float | None = None
    growth: float | None = None


def enterprise_value(market_cap: float | None, net_debt: float | None) -> float | None:
    if market_cap is None or net_debt is None:
        return None
    return market_cap + net_debt


def _positive(value: float | None) -> float | None:
    """Multiples over a non-positive denominator are meaningless, not huge."""
    return value if value is not None and value > 0 else None


def compute_multiples(m: MultipleInputs) -> dict[str, float | None]:
    ev = enterprise_value(m.market_cap, m.net_debt)
    pe = div(m.price, _positive(m.eps_diluted))
    return {
        "pe": pe,
        "peg": div(pe, m.growth * 100.0 if m.growth and m.growth > 0 else None),
        "pb": div(m.price, _positive(m.book_value_per_share)),
        "ps": div(m.market_cap, _positive(m.revenue)),
        "ev_ebitda": div(ev, _positive(m.ebitda)),
        "ev_ebit": div(ev, _positive(m.ebit)),
        "ev_sales": div(ev, _positive(m.revenue)),
        "ev_fcf": div(ev, _positive(m.fcf)),
        "dividend_yield": div(m.dividends_per_share, _positive(m.price)),
    }


def median(values: list[float | None]) -> float | None:
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    n = len(clean)
    mid = n // 2
    return clean[mid] if n % 2 else (clean[mid - 1] + clean[mid]) / 2.0


def peer_median_multiples(peer_multiples: list[dict[str, float | None]]) -> dict[str, float | None]:
    if not peer_multiples:
        return {}
    keys = peer_multiples[0].keys()
    return {
        k: median([pm.get(k) for pm in peer_multiples if pm.get(k) is not None])
        for k in keys
    }


def implied_value_per_share(
    peer_multiple: float | None,
    per_share_metric: float | None,
) -> float | None:
    """Fair value implied by applying a peer-median multiple to the
    company's own per-share metric (e.g. median P/E x EPS)."""
    if peer_multiple is None or per_share_metric is None or per_share_metric <= 0:
        return None
    return peer_multiple * per_share_metric
