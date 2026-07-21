"""Shared test builders: consistent StatementSet fixtures for domain tests."""

from __future__ import annotations

from datetime import date

import pytest

from feat.domain.entities import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
    StatementSet,
)
from feat.domain.values import MISSING, FiscalPeriod, Money, PeriodType


def m(value: float | None):
    return Money(value) if value is not None else MISSING


def annual_period(year: int) -> FiscalPeriod:
    return FiscalPeriod(fiscal_year=year, period_type=PeriodType.ANNUAL,
                        end_date=date(year, 12, 31))


def quarter_period(year: int, quarter: int) -> FiscalPeriod:
    month = quarter * 3
    return FiscalPeriod(fiscal_year=year, period_type=PeriodType.QUARTER,
                        end_date=date(year, month, 28), quarter=quarter)


def make_statement_set(
    year: int = 2024,
    *,
    period: FiscalPeriod | None = None,
    revenue: float | None = 100.0,
    cost_of_revenue: float | None = 60.0,
    gross_profit: float | None = 40.0,
    operating_income: float | None = 25.0,
    ebitda: float | None = 30.0,
    interest_expense: float | None = 1.0,
    income_before_tax: float | None = 24.0,
    income_tax_expense: float | None = 4.8,
    net_income: float | None = 19.2,
    eps_diluted: float | None = 1.92,
    shares_diluted: float | None = 10.0,
    cash: float | None = 20.0,
    receivables: float | None = 10.0,
    inventory: float | None = 5.0,
    total_current_assets: float | None = 45.0,
    total_assets: float | None = 120.0,
    accounts_payable: float | None = 8.0,
    total_current_liabilities: float | None = 20.0,
    long_term_debt: float | None = 28.0,
    total_debt: float | None = 30.0,
    total_liabilities: float | None = 60.0,
    total_equity: float | None = 60.0,
    retained_earnings: float | None = 40.0,
    operating_cash_flow: float | None = 28.0,
    capex: float | None = -8.0,
    dividends_paid: float | None = -3.0,
    free_cash_flow: float | None = 20.0,
    debt_issued_net: float | None = -1.0,
    ppe_net: float | None = 30.0,
    depreciation: float | None = 5.0,
    sga: float | None = 10.0,
) -> StatementSet:
    p = period or annual_period(year)
    income = IncomeStatement(
        period=p,
        revenue=m(revenue),
        cost_of_revenue=m(cost_of_revenue),
        gross_profit=m(gross_profit),
        sga_expense=m(sga),
        operating_income=m(operating_income),
        depreciation_amortization=m(depreciation),
        ebitda=m(ebitda),
        interest_expense=m(interest_expense),
        income_before_tax=m(income_before_tax),
        income_tax_expense=m(income_tax_expense),
        net_income=m(net_income),
        eps_diluted=eps_diluted,
        weighted_shares_basic=shares_diluted,
        weighted_shares_diluted=shares_diluted,
    )
    balance = BalanceSheet(
        period=p,
        cash_and_equivalents=m(cash),
        short_term_investments=m(5.0),
        receivables=m(receivables),
        inventory=m(inventory),
        total_current_assets=m(total_current_assets),
        ppe_net=m(ppe_net),
        total_assets=m(total_assets),
        accounts_payable=m(accounts_payable),
        total_current_liabilities=m(total_current_liabilities),
        long_term_debt=m(long_term_debt),
        total_debt=m(total_debt),
        total_liabilities=m(total_liabilities),
        total_equity=m(total_equity),
        retained_earnings=m(retained_earnings),
    )
    cash_flow = CashFlowStatement(
        period=p,
        operating_cash_flow=m(operating_cash_flow),
        depreciation_amortization=m(depreciation),
        capital_expenditure=m(capex),
        dividends_paid=m(dividends_paid),
        debt_issued_net=m(debt_issued_net),
        free_cash_flow=m(free_cash_flow),
    )
    return StatementSet(period=p, income=income, balance=balance, cash_flow=cash_flow)


@pytest.fixture
def statement_set() -> StatementSet:
    return make_statement_set()
