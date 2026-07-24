"""Profitability and value-creation ratios.

Definitions (see docs/formulas.md):

- gross margin      = gross profit / revenue
- operating margin  = operating income / revenue
- EBITDA margin     = EBITDA / revenue
- net margin        = net income / revenue
- ROA               = net income / average total assets (ending when no prior)
- ROE               = net income / average total equity (ending when no prior)
- NOPAT             = operating income x (1 - effective tax rate)
- invested capital  = total debt + total equity - cash & equivalents
- ROIC              = NOPAT / average invested capital (ending when no prior)

Averages use (current + prior) / 2 only when a prior period is supplied;
with no prior the ending balance is used. See ``docs/formulas.md``.
- ROCE              = EBIT / (total assets - current liabilities)
- ROIC-WACC spread  = ROIC - WACC (the headline value-creation signal)
"""

from __future__ import annotations

from feat.domain.ratios import avg, div


def gross_margin(gross_profit: float | None, revenue: float | None) -> float | None:
    return div(gross_profit, revenue)


def operating_margin(operating_income: float | None, revenue: float | None) -> float | None:
    return div(operating_income, revenue)


def ebitda_margin(ebitda: float | None, revenue: float | None) -> float | None:
    return div(ebitda, revenue)


def net_margin(net_income: float | None, revenue: float | None) -> float | None:
    return div(net_income, revenue)


def return_on_assets(
    net_income: float | None,
    total_assets: float | None,
    prior_total_assets: float | None = None,
) -> float | None:
    base = avg(total_assets, prior_total_assets) if prior_total_assets is not None else total_assets
    return div(net_income, base)


def return_on_equity(
    net_income: float | None,
    total_equity: float | None,
    prior_total_equity: float | None = None,
) -> float | None:
    base = avg(total_equity, prior_total_equity) if prior_total_equity is not None else total_equity
    return div(net_income, base)


def effective_tax_rate(
    income_tax_expense: float | None, income_before_tax: float | None
) -> float | None:
    rate = div(income_tax_expense, income_before_tax)
    if rate is None:
        return None
    # Clamp pathological rates (tax benefits on losses, one-off charges) so
    # NOPAT stays interpretable; the raw rate is still reported separately.
    return min(max(rate, 0.0), 1.0)


def nopat(operating_income: float | None, tax_rate: float | None) -> float | None:
    if operating_income is None or tax_rate is None:
        return None
    return operating_income * (1.0 - tax_rate)


def invested_capital(
    total_debt: float | None,
    total_equity: float | None,
    cash_and_equivalents: float | None,
) -> float | None:
    if total_debt is None or total_equity is None:
        return None
    cash = cash_and_equivalents if cash_and_equivalents is not None else 0.0
    return total_debt + total_equity - cash


def return_on_invested_capital(
    nopat_value: float | None,
    invested_capital_now: float | None,
    invested_capital_prior: float | None = None,
) -> float | None:
    base = (
        avg(invested_capital_now, invested_capital_prior)
        if invested_capital_prior is not None
        else invested_capital_now
    )
    return div(nopat_value, base)


def return_on_capital_employed(
    operating_income: float | None,
    total_assets: float | None,
    total_current_liabilities: float | None,
) -> float | None:
    if total_assets is None or total_current_liabilities is None:
        return None
    return div(operating_income, total_assets - total_current_liabilities)


def roic_wacc_spread(roic: float | None, wacc: float | None) -> float | None:
    if roic is None or wacc is None:
        return None
    return roic - wacc
