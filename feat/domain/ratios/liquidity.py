"""Liquidity ratios.

- current ratio       = current assets / current liabilities
- quick ratio         = (cash + short-term investments + receivables) / current liabilities
- cash ratio          = (cash + short-term investments) / current liabilities
- defensive interval  = quick assets / daily operating expenses, in days
"""

from __future__ import annotations

from feat.domain.ratios import div


def current_ratio(
    total_current_assets: float | None, total_current_liabilities: float | None
) -> float | None:
    return div(total_current_assets, total_current_liabilities)


def _quick_assets(
    cash: float | None, short_term_investments: float | None, receivables: float | None
) -> float | None:
    if cash is None:
        return None
    total = cash
    if short_term_investments is not None:
        total += short_term_investments
    if receivables is not None:
        total += receivables
    return total


def quick_ratio(
    cash: float | None,
    short_term_investments: float | None,
    receivables: float | None,
    total_current_liabilities: float | None,
) -> float | None:
    return div(_quick_assets(cash, short_term_investments, receivables), total_current_liabilities)


def cash_ratio(
    cash: float | None,
    short_term_investments: float | None,
    total_current_liabilities: float | None,
) -> float | None:
    if cash is None:
        return None
    sti = short_term_investments if short_term_investments is not None else 0.0
    return div(cash + sti, total_current_liabilities)


def defensive_interval_days(
    cash: float | None,
    short_term_investments: float | None,
    receivables: float | None,
    operating_expenses_annual: float | None,
    depreciation_amortization: float | None,
) -> float | None:
    """Days the quick assets cover cash operating expenses (opex ex-D&A)."""
    quick = _quick_assets(cash, short_term_investments, receivables)
    if quick is None or operating_expenses_annual is None:
        return None
    cash_opex = operating_expenses_annual - (depreciation_amortization or 0.0)
    return div(quick, cash_opex / 365.0) if cash_opex > 0 else None
