"""Cash-flow quality diagnostics.

- OCF / NI          = operating cash flow / net income (accrual check)
- FCF conversion    = free cash flow / net income
- capex intensity   = capex / revenue
- accruals ratio    = (NI - OCF) / average total assets  (Sloan)
"""

from __future__ import annotations

from feat.domain.ratios import avg, div


def ocf_to_net_income(
    operating_cash_flow: float | None, net_income: float | None
) -> float | None:
    return div(operating_cash_flow, net_income)


def fcf_conversion(free_cash_flow: float | None, net_income: float | None) -> float | None:
    return div(free_cash_flow, net_income)


def capex_intensity(capital_expenditure: float | None, revenue: float | None) -> float | None:
    if capital_expenditure is not None:
        capital_expenditure = abs(capital_expenditure)
    return div(capital_expenditure, revenue)


def accruals_ratio(
    net_income: float | None,
    operating_cash_flow: float | None,
    total_assets: float | None,
    prior_total_assets: float | None = None,
) -> float | None:
    if net_income is None or operating_cash_flow is None:
        return None
    base = avg(total_assets, prior_total_assets) if prior_total_assets is not None else total_assets
    return div(net_income - operating_cash_flow, base)
