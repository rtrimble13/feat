"""FmpAdapter: implements the domain ports against the FMP API.

Schema quirks are quarantined here:

- price/return work uses ``adjClose``, never raw ``close``
- ``period`` is normalized to FMP's required ``annual`` | ``quarter``
- ``[]`` for an unknown symbol becomes ``SymbolNotFound``
- absent/null fields become the MISSING sentinel, never 0
- net borrowing prefers ``netDebtIssuance`` over legacy ``debtRepayment``
- ``YYYY-MM-DD`` strings become ``date`` objects at this boundary
- batch symbol requests are chunked to a reliable size
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from feat.domain.entities import (
    BalanceSheet,
    CashFlowStatement,
    Company,
    FinancialHistory,
    IncomeStatement,
    StatementSet,
)
from feat.domain.errors import (
    AnalysisError,
    Err,
    Ok,
    RateLimited,
    Result,
    SymbolNotFound,
    UpstreamUnavailable,
)
from feat.domain.ports import FundamentalsRepository
from feat.domain.values import MISSING, FiscalPeriod, Money, MoneyLike, PeriodType, Ticker
from feat.infra.fmp import endpoints as ep
from feat.infra.fmp.client import FmpClient, FmpRateLimited, FmpUnavailable


def _money(record: dict, field: str, currency: str) -> MoneyLike:
    value = record.get(field)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return MISSING
    return Money(float(value), currency)


def _number(record: dict, field: str) -> float | None:
    value = record.get(field)
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _money_first(record: dict, fields: tuple[str, ...], currency: str) -> MoneyLike:
    """First present numeric field among ``fields`` as Money, else MISSING.

    Lets a preferred, unambiguous field win over a legacy fallback (e.g.
    net debt *issuance* over the poorly-named ``debtRepayment``).
    """
    for field in fields:
        value = record.get(field)
        if value is not None and not isinstance(value, bool) and isinstance(value, (int, float)):
            return Money(float(value), currency)
    return MISSING


def _parse_date(value: Any) -> date:
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def _fiscal_period(record: dict, period_type: PeriodType) -> FiscalPeriod:
    end = _parse_date(record["date"])
    year_raw = record.get("calendarYear")
    fiscal_year = int(year_raw) if year_raw is not None else end.year
    quarter = None
    if period_type is PeriodType.QUARTER:
        raw = str(record.get("period", "")).upper()  # e.g. "Q3"
        quarter = int(raw[1]) if raw.startswith("Q") and raw[1:].isdigit() else ((end.month - 1) // 3 + 1)
    return FiscalPeriod(
        fiscal_year=fiscal_year, period_type=period_type, end_date=end, quarter=quarter
    )


class FmpAdapter(FundamentalsRepository):
    def __init__(self, client: FmpClient) -> None:
        self._client = client

    # -- plumbing ---------------------------------------------------------

    def _get(self, endpoint: ep.Endpoint, path_params: dict[str, str] | None = None,
             **query: Any) -> Result[Any, AnalysisError]:
        """Translate transport-level expected failures into domain errors."""
        try:
            return Ok(self._client.get(endpoint, path_params, **query))
        except FmpRateLimited as exc:
            return Err(RateLimited(str(exc)))
        except FmpUnavailable as exc:
            return Err(UpstreamUnavailable(str(exc)))

    # -- FundamentalsRepository ------------------------------------------

    def get_company(self, ticker: Ticker) -> Result[Company, AnalysisError]:
        result = self._get(ep.PROFILE, {"symbol": ticker.symbol})
        if result.is_err():
            return result
        body = result.unwrap()
        if not isinstance(body, list) or not body:
            return Err(SymbolNotFound(
                f"symbol {ticker} not found on FMP — check the ticker "
                "(foreign listings may need an exchange suffix, e.g. RY.TO)"
            ))
        record = body[0]
        currency = str(record.get("currency") or "USD")
        return Ok(Company(
            ticker=ticker,
            name=str(record.get("companyName") or ticker.symbol),
            sector=record.get("sector") or None,
            industry=record.get("industry") or None,
            currency=currency,
            exchange=record.get("exchangeShortName") or None,
            beta=_number(record, "beta"),
            market_cap=_money(record, "mktCap", currency),
            shares_outstanding=_number(record, "sharesOutstanding")
                or _number(record, "outstandingShares"),
            price=_money(record, "price", currency),
            description=record.get("description") or None,
        ))

    def get_history(
        self, ticker: Ticker, period: PeriodType, years: int
    ) -> Result[FinancialHistory, AnalysisError]:
        limit = years if period is PeriodType.ANNUAL else years * 4
        symbol = {"symbol": ticker.symbol}
        # FMP requires 'annual' | 'quarter' — never 'quarterly'.
        params = {"period": period.value, "limit": limit}

        statements: dict[str, Any] = {}
        for name, endpoint in (
            ("income", ep.INCOME_STATEMENT),
            ("balance", ep.BALANCE_SHEET),
            ("cash_flow", ep.CASH_FLOW),
        ):
            result = self._get(endpoint, symbol, **params)
            if result.is_err():
                return result
            statements[name] = result.unwrap()

        if not statements["income"]:
            return Err(SymbolNotFound(
                f"no financial statements on FMP for {ticker} — check the ticker"
            ))

        by_date_balance = {r["date"]: r for r in statements["balance"] if "date" in r}
        by_date_cash = {r["date"]: r for r in statements["cash_flow"] if "date" in r}

        sets: list[StatementSet] = []
        for record in statements["income"]:
            if "date" not in record:
                continue
            fiscal = _fiscal_period(record, period)
            currency = str(record.get("reportedCurrency") or "USD")
            income = self._map_income(record, fiscal, currency)
            balance_rec = by_date_balance.get(record["date"], {})
            cash_rec = by_date_cash.get(record["date"], {})
            balance = self._map_balance(balance_rec, fiscal, currency)
            cash = self._map_cash_flow(cash_rec, fiscal, currency)
            sets.append(StatementSet(period=fiscal, income=income, balance=balance, cash_flow=cash))

        return Ok(FinancialHistory(sets))

    def _map_income(self, r: dict, period: FiscalPeriod, cur: str) -> IncomeStatement:
        eps_diluted = _number(r, "epsdiluted")
        if eps_diluted is None:
            eps_diluted = _number(r, "epsDiluted")
        return IncomeStatement(
            period=period,
            currency=cur,
            revenue=_money(r, "revenue", cur),
            cost_of_revenue=_money(r, "costOfRevenue", cur),
            gross_profit=_money(r, "grossProfit", cur),
            sga_expense=_money(r, "sellingGeneralAndAdministrativeExpenses", cur),
            operating_expenses=_money(r, "operatingExpenses", cur),
            operating_income=_money(r, "operatingIncome", cur),
            depreciation_amortization=_money(r, "depreciationAndAmortization", cur),
            ebitda=_money(r, "ebitda", cur),
            interest_expense=_money(r, "interestExpense", cur),
            income_before_tax=_money(r, "incomeBeforeTax", cur),
            income_tax_expense=_money(r, "incomeTaxExpense", cur),
            net_income=_money(r, "netIncome", cur),
            eps_basic=_number(r, "eps"),
            eps_diluted=eps_diluted,
            weighted_shares_basic=_number(r, "weightedAverageShsOut"),
            weighted_shares_diluted=_number(r, "weightedAverageShsOutDil"),
        )

    def _map_balance(self, r: dict, period: FiscalPeriod, cur: str) -> BalanceSheet:
        return BalanceSheet(
            period=period,
            currency=cur,
            cash_and_equivalents=_money(r, "cashAndCashEquivalents", cur),
            short_term_investments=_money(r, "shortTermInvestments", cur),
            receivables=_money(r, "netReceivables", cur),
            inventory=_money(r, "inventory", cur),
            total_current_assets=_money(r, "totalCurrentAssets", cur),
            ppe_net=_money(r, "propertyPlantEquipmentNet", cur),
            goodwill_and_intangibles=_money(r, "goodwillAndIntangibleAssets", cur),
            total_assets=_money(r, "totalAssets", cur),
            accounts_payable=_money(r, "accountPayables", cur),
            short_term_debt=_money(r, "shortTermDebt", cur),
            total_current_liabilities=_money(r, "totalCurrentLiabilities", cur),
            long_term_debt=_money(r, "longTermDebt", cur),
            total_debt=_money(r, "totalDebt", cur),
            total_liabilities=_money(r, "totalLiabilities", cur),
            total_equity=_money(r, "totalStockholdersEquity", cur),
            retained_earnings=_money(r, "retainedEarnings", cur),
            minority_interest=_money(r, "minorityInterest", cur),
            net_debt=_money(r, "netDebt", cur),
        )

    def _map_cash_flow(self, r: dict, period: FiscalPeriod, cur: str) -> CashFlowStatement:
        return CashFlowStatement(
            period=period,
            currency=cur,
            operating_cash_flow=_money(r, "operatingCashFlow", cur),
            depreciation_amortization=_money(r, "depreciationAndAmortization", cur),
            change_in_working_capital=_money(r, "changeInWorkingCapital", cur),
            stock_based_compensation=_money(r, "stockBasedCompensation", cur),
            capital_expenditure=_money(r, "capitalExpenditure", cur),
            dividends_paid=_money(r, "dividendsPaid", cur),
            share_repurchases=_money(r, "commonStockRepurchased", cur),
            # Net borrowing for FCFE: prefer FMP's explicit net-debt-issuance
            # line (issuance net of repayment, correctly signed) and fall back
            # to the legacy, misleadingly-named ``debtRepayment`` field only
            # when it is absent.
            debt_issued_net=_money_first(r, ("netDebtIssuance", "debtRepayment"), cur),
            free_cash_flow=_money(r, "freeCashFlow", cur),
            net_change_in_cash=_money(r, "netChangeInCash", cur),
        )

    def get_reference_dcf(self, ticker: Ticker) -> Result[float | None, AnalysisError]:
        result = self._get(ep.DCF_REFERENCE, {"symbol": ticker.symbol})
        if result.is_err():
            return result
        body = result.unwrap()
        if not isinstance(body, list) or not body:
            return Ok(None)  # no reference DCF is not an error — it's a cross-check
        return Ok(_number(body[0], "dcf"))

    def get_peers(self, ticker: Ticker) -> Result[list[Ticker], AnalysisError]:
        result = self._get(ep.STOCK_PEERS, symbol=ticker.symbol)
        if result.is_err():
            return result
        body = result.unwrap()
        peers: list[Ticker] = []
        if isinstance(body, list) and body:
            for raw in body[0].get("peersList", []) or []:
                try:
                    peers.append(Ticker(str(raw)))
                except ValueError:
                    continue  # FMP occasionally lists malformed symbols; skip them
        return Ok(peers)

    def screen(self, filters: dict[str, str | float | int]) -> Result[list[dict], AnalysisError]:
        # filters are FMP query params; their keys never collide with _get's
        # own parameters, which mypy cannot know when unpacking a typed dict.
        result = self._get(ep.SCREENER, **filters)  # type: ignore[arg-type]
        if result.is_err():
            return result
        body = result.unwrap()
        return Ok(body if isinstance(body, list) else [])
