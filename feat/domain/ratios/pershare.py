"""Per-share figures, tracked against share-count history to expose dilution.

- BVPS       = total equity / diluted shares
- FCF/share  = free cash flow / diluted shares
- DPS        = |dividends paid| / diluted shares
"""

from __future__ import annotations

from feat.domain.ratios import div


def book_value_per_share(
    total_equity: float | None, diluted_shares: float | None
) -> float | None:
    return div(total_equity, diluted_shares)


def fcf_per_share(
    free_cash_flow: float | None, diluted_shares: float | None
) -> float | None:
    return div(free_cash_flow, diluted_shares)


def dividends_per_share(
    dividends_paid: float | None, diluted_shares: float | None
) -> float | None:
    # FMP reports dividends paid as a negative financing outflow.
    if dividends_paid is not None:
        dividends_paid = abs(dividends_paid)
    return div(dividends_paid, diluted_shares)


def dilution_rate(
    diluted_shares_now: float | None, diluted_shares_prior: float | None
) -> float | None:
    """Year-over-year growth in diluted share count (positive = dilution)."""
    ratio = div(diluted_shares_now, diluted_shares_prior)
    return ratio - 1.0 if ratio is not None else None
