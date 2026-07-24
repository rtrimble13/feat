"""Domain entities: Company, financial statements and their history.

Statement fields are typed as ``MoneyLike`` (Money or the MISSING
sentinel). The adapter at the FMP boundary decides what is missing;
nothing in the domain ever turns a gap into a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from feat.domain.values import (
    MISSING,
    FiscalPeriod,
    MoneyLike,
    Ticker,
    amount_of,
)


@dataclass(frozen=True, slots=True)
class Company:
    """Identity, profile and classification of an issuer."""

    ticker: Ticker
    name: str
    sector: str | None = None
    industry: str | None = None
    currency: str = "USD"
    exchange: str | None = None
    beta: float | None = None
    market_cap: MoneyLike = MISSING
    shares_outstanding: float | None = None
    price: MoneyLike = MISSING
    description: str | None = None


@dataclass(frozen=True, slots=True)
class IncomeStatement:
    period: FiscalPeriod
    currency: str = "USD"
    revenue: MoneyLike = MISSING
    cost_of_revenue: MoneyLike = MISSING
    gross_profit: MoneyLike = MISSING
    sga_expense: MoneyLike = MISSING
    operating_expenses: MoneyLike = MISSING
    operating_income: MoneyLike = MISSING
    depreciation_amortization: MoneyLike = MISSING
    ebitda: MoneyLike = MISSING
    interest_expense: MoneyLike = MISSING
    income_before_tax: MoneyLike = MISSING
    income_tax_expense: MoneyLike = MISSING
    net_income: MoneyLike = MISSING
    eps_basic: float | None = None
    eps_diluted: float | None = None
    weighted_shares_basic: float | None = None
    weighted_shares_diluted: float | None = None


@dataclass(frozen=True, slots=True)
class BalanceSheet:
    period: FiscalPeriod
    currency: str = "USD"
    cash_and_equivalents: MoneyLike = MISSING
    short_term_investments: MoneyLike = MISSING
    receivables: MoneyLike = MISSING
    inventory: MoneyLike = MISSING
    total_current_assets: MoneyLike = MISSING
    ppe_net: MoneyLike = MISSING
    goodwill_and_intangibles: MoneyLike = MISSING
    total_assets: MoneyLike = MISSING
    accounts_payable: MoneyLike = MISSING
    short_term_debt: MoneyLike = MISSING
    total_current_liabilities: MoneyLike = MISSING
    long_term_debt: MoneyLike = MISSING
    total_debt: MoneyLike = MISSING
    total_liabilities: MoneyLike = MISSING
    total_equity: MoneyLike = MISSING
    retained_earnings: MoneyLike = MISSING
    minority_interest: MoneyLike = MISSING
    net_debt: MoneyLike = MISSING


@dataclass(frozen=True, slots=True)
class CashFlowStatement:
    period: FiscalPeriod
    currency: str = "USD"
    operating_cash_flow: MoneyLike = MISSING
    depreciation_amortization: MoneyLike = MISSING
    change_in_working_capital: MoneyLike = MISSING
    stock_based_compensation: MoneyLike = MISSING
    capital_expenditure: MoneyLike = MISSING
    dividends_paid: MoneyLike = MISSING
    share_repurchases: MoneyLike = MISSING
    debt_issued_net: MoneyLike = MISSING
    free_cash_flow: MoneyLike = MISSING
    net_change_in_cash: MoneyLike = MISSING


@dataclass(frozen=True, slots=True)
class StatementSet:
    """The three statements for a single fiscal period."""

    period: FiscalPeriod
    income: IncomeStatement
    balance: BalanceSheet
    cash_flow: CashFlowStatement


class FinancialHistory:
    """An ordered series of statement sets, most recent first.

    Provides TTM roll-ups and common-size / trend transforms as pure
    methods. Ordering is normalized at construction so callers can rely
    on ``history.periods[0]`` being the latest period.
    """

    def __init__(self, statements: Sequence[StatementSet]) -> None:
        self._statements = sorted(
            statements, key=lambda s: s.period.end_date, reverse=True
        )

    @property
    def statements(self) -> list[StatementSet]:
        return list(self._statements)

    @property
    def periods(self) -> list[FiscalPeriod]:
        return [s.period for s in self._statements]

    def __len__(self) -> int:
        return len(self._statements)

    @property
    def latest(self) -> StatementSet:
        if not self._statements:
            raise ValueError("empty financial history")
        return self._statements[0]

    def trend(self, field_name: str) -> list[float | None]:
        """Horizontal analysis: a single income line across periods, oldest first."""
        series: list[float | None] = []
        for s in reversed(self._statements):
            series.append(amount_of(getattr(s.income, field_name)))
        return series
