"""Efficiency / activity ratios.

- asset turnover        = revenue / average total assets
- DSO (days sales)      = receivables / revenue x 365
- DIO (days inventory)  = inventory / COGS x 365
- DPO (days payable)    = payables / COGS x 365
- cash conversion cycle = DSO + DIO - DPO
"""

from __future__ import annotations

from feat.domain.ratios import avg, div


def asset_turnover(
    revenue: float | None,
    total_assets: float | None,
    prior_total_assets: float | None = None,
) -> float | None:
    base = avg(total_assets, prior_total_assets) if prior_total_assets is not None else total_assets
    return div(revenue, base)


def days_sales_outstanding(receivables: float | None, revenue: float | None) -> float | None:
    ratio = div(receivables, revenue)
    return ratio * 365.0 if ratio is not None else None


def days_inventory_outstanding(
    inventory: float | None, cost_of_revenue: float | None
) -> float | None:
    ratio = div(inventory, cost_of_revenue)
    return ratio * 365.0 if ratio is not None else None


def days_payable_outstanding(
    accounts_payable: float | None, cost_of_revenue: float | None
) -> float | None:
    ratio = div(accounts_payable, cost_of_revenue)
    return ratio * 365.0 if ratio is not None else None


def cash_conversion_cycle(
    dso: float | None, dio: float | None, dpo: float | None
) -> float | None:
    if dso is None or dio is None or dpo is None:
        return None
    return dso + dio - dpo
