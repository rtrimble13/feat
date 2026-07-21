"""Shared derivations: entity statements -> plain numbers for the domain math.

This is the seam between typed entities (Money / MISSING) and the pure
float functions in ``feat.domain``. Missing stays None throughout.
"""

from __future__ import annotations

from feat.domain import cashflows
from feat.domain.entities import StatementSet
from feat.domain.ratios import (
    cashflow_quality,
    div,
    dupont,
    efficiency,
    leverage,
    liquidity,
    pershare,
    profitability,
)
from feat.domain.values import amount_of


def tax_rate_of(s: StatementSet) -> float | None:
    return profitability.effective_tax_rate(
        amount_of(s.income.income_tax_expense), amount_of(s.income.income_before_tax)
    )


def fcff_of(s: StatementSet) -> float | None:
    return cashflows.fcff(
        operating_cash_flow=amount_of(s.cash_flow.operating_cash_flow),
        interest_expense=amount_of(s.income.interest_expense),
        tax_rate=tax_rate_of(s),
        capital_expenditure=amount_of(s.cash_flow.capital_expenditure),
    )


def fcfe_of(s: StatementSet) -> float | None:
    return cashflows.fcfe(
        operating_cash_flow=amount_of(s.cash_flow.operating_cash_flow),
        capital_expenditure=amount_of(s.cash_flow.capital_expenditure),
        net_debt_issued=amount_of(s.cash_flow.debt_issued_net),
    )


def net_debt_of(s: StatementSet) -> float | None:
    reported = amount_of(s.balance.net_debt)
    if reported is not None:
        return reported
    return leverage.net_debt(
        amount_of(s.balance.total_debt), amount_of(s.balance.cash_and_equivalents)
    )


def ratio_rows(current: StatementSet, prior: StatementSet | None) -> dict[str, float | None]:
    """All ratio families for one period (prior period enables averages
    and change-based metrics). Keys are stable identifiers used by the
    renderers and by tests."""
    inc, bal, cf = current.income, current.balance, current.cash_flow
    p_bal = prior.balance if prior else None

    revenue = amount_of(inc.revenue)
    net_income = amount_of(inc.net_income)
    op_income = amount_of(inc.operating_income)
    total_assets = amount_of(bal.total_assets)
    prior_assets = amount_of(p_bal.total_assets) if p_bal else None
    equity = amount_of(bal.total_equity)
    prior_equity = amount_of(p_bal.total_equity) if p_bal else None
    total_debt = amount_of(bal.total_debt)
    cash = amount_of(bal.cash_and_equivalents)
    ocf = amount_of(cf.operating_cash_flow)
    fcf = amount_of(cf.free_cash_flow)
    if fcf is None:
        fcf = fcfe_of(current)
    shares_dil = inc.weighted_shares_diluted
    prior_shares_dil = prior.income.weighted_shares_diluted if prior else None

    tax_rate = tax_rate_of(current)
    nopat = profitability.nopat(op_income, tax_rate)
    ic_now = profitability.invested_capital(total_debt, equity, cash)
    ic_prior = (
        profitability.invested_capital(
            amount_of(p_bal.total_debt), prior_equity, amount_of(p_bal.cash_and_equivalents)
        )
        if p_bal
        else None
    )

    dso = efficiency.days_sales_outstanding(amount_of(bal.receivables), revenue)
    dio = efficiency.days_inventory_outstanding(
        amount_of(bal.inventory), amount_of(inc.cost_of_revenue)
    )
    dpo = efficiency.days_payable_outstanding(
        amount_of(bal.accounts_payable), amount_of(inc.cost_of_revenue)
    )

    d3 = dupont.dupont_3way(net_income, revenue, total_assets, equity)
    d5 = dupont.dupont_5way(net_income, amount_of(inc.income_before_tax), op_income,
                            revenue, total_assets, equity)

    return {
        # profitability
        "gross_margin": profitability.gross_margin(amount_of(inc.gross_profit), revenue),
        "operating_margin": profitability.operating_margin(op_income, revenue),
        "ebitda_margin": profitability.ebitda_margin(amount_of(inc.ebitda), revenue),
        "net_margin": profitability.net_margin(net_income, revenue),
        "roa": profitability.return_on_assets(net_income, total_assets, prior_assets),
        "roe": profitability.return_on_equity(net_income, equity, prior_equity),
        "roic": profitability.return_on_invested_capital(nopat, ic_now, ic_prior),
        "roce": profitability.return_on_capital_employed(
            op_income, total_assets, amount_of(bal.total_current_liabilities)
        ),
        "effective_tax_rate": tax_rate,
        # DuPont
        "dupont3_net_margin": d3.net_margin,
        "dupont3_asset_turnover": d3.asset_turnover,
        "dupont3_equity_multiplier": d3.equity_multiplier,
        "dupont5_tax_burden": d5.tax_burden,
        "dupont5_interest_burden": d5.interest_burden,
        # liquidity
        "current_ratio": liquidity.current_ratio(
            amount_of(bal.total_current_assets), amount_of(bal.total_current_liabilities)
        ),
        "quick_ratio": liquidity.quick_ratio(
            cash, amount_of(bal.short_term_investments), amount_of(bal.receivables),
            amount_of(bal.total_current_liabilities),
        ),
        "cash_ratio": liquidity.cash_ratio(
            cash, amount_of(bal.short_term_investments),
            amount_of(bal.total_current_liabilities),
        ),
        # leverage
        "net_debt": net_debt_of(current),
        "debt_to_ebitda": leverage.debt_to_ebitda(total_debt, amount_of(inc.ebitda)),
        "net_debt_to_ebitda": leverage.net_debt_to_ebitda(
            net_debt_of(current), amount_of(inc.ebitda)
        ),
        "debt_to_equity": leverage.debt_to_equity(total_debt, equity),
        "interest_coverage": leverage.interest_coverage(
            op_income, amount_of(inc.interest_expense)
        ),
        # efficiency
        "asset_turnover": efficiency.asset_turnover(revenue, total_assets, prior_assets),
        "dso": dso,
        "dio": dio,
        "dpo": dpo,
        "cash_conversion_cycle": efficiency.cash_conversion_cycle(dso, dio, dpo),
        # per-share
        "eps_basic": inc.eps_basic,
        "eps_diluted": inc.eps_diluted,
        "book_value_per_share": pershare.book_value_per_share(equity, shares_dil),
        "fcf_per_share": pershare.fcf_per_share(fcf, shares_dil),
        "dividends_per_share": pershare.dividends_per_share(
            amount_of(cf.dividends_paid), shares_dil
        ),
        "dilution_rate": pershare.dilution_rate(shares_dil, prior_shares_dil),
        # cash-flow quality
        "ocf_to_net_income": cashflow_quality.ocf_to_net_income(ocf, net_income),
        "fcf_conversion": cashflow_quality.fcf_conversion(fcf, net_income),
        "capex_intensity": cashflow_quality.capex_intensity(
            amount_of(cf.capital_expenditure), revenue
        ),
        "accruals_ratio": cashflow_quality.accruals_ratio(
            net_income, ocf, total_assets, prior_assets
        ),
        # reconstruction
        "fcff": fcff_of(current),
        "fcfe": fcfe_of(current),
        # growth
        "revenue_growth": (
            div(revenue, amount_of(prior.income.revenue)) - 1.0
            if prior and div(revenue, amount_of(prior.income.revenue)) is not None
            else None
        ),
    }


def payout_ratio_of(s: StatementSet) -> float | None:
    dividends = amount_of(s.cash_flow.dividends_paid)
    net_income = amount_of(s.income.net_income)
    if dividends is None or net_income is None or net_income <= 0:
        return None
    return min(abs(dividends) / net_income, 1.0)


def historical_growth(values: list[float | None], max_years: int = 5) -> float | None:
    """CAGR over up to ``max_years`` of a series (oldest first); None if
    endpoints are missing or non-positive."""
    clean = [v for v in values if v is not None]
    if len(clean) < 2:
        return None
    window = clean[-(max_years + 1):]
    first, last = window[0], window[-1]
    if first <= 0 or last <= 0:
        return None
    years = len(window) - 1
    return (last / first) ** (1.0 / years) - 1.0
