"""Use-case: AnalyzeCompany — statements, ratios, quality scores."""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.entities import FinancialHistory, Company
from feat.domain.errors import AnalysisError, Err, InsufficientHistory, Ok, Result
from feat.domain.ports import FundamentalsRepository
from feat.domain.quality.altman import AltmanResult, altman_z
from feat.domain.quality.beneish import BeneishPeriod, BeneishResult, beneish_m
from feat.domain.quality.piotroski import PiotroskiInputs, PiotroskiScore, piotroski_f
from feat.domain.values import PeriodType, Ticker, amount_of
from feat.services import derive


@dataclass(frozen=True, slots=True)
class QualitySummary:
    piotroski: PiotroskiScore | None
    altman: AltmanResult | None
    beneish: BeneishResult | None
    accruals_ratio: float | None


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    company: Company
    history: FinancialHistory
    #: (period label, ratio dict) most recent first
    ratios: list[tuple[str, dict[str, float | None]]]
    quality: QualitySummary | None


class AnalyzeCompany:
    def __init__(self, fundamentals: FundamentalsRepository) -> None:
        self._fundamentals = fundamentals

    def run(
        self,
        ticker: Ticker,
        period: PeriodType = PeriodType.ANNUAL,
        years: int = 10,
    ) -> Result[AnalysisReport, AnalysisError]:
        company_result = self._fundamentals.get_company(ticker)
        if isinstance(company_result, Err):
            return company_result
        company = company_result.unwrap()

        history_result = self._fundamentals.get_history(ticker, period, years)
        if isinstance(history_result, Err):
            return history_result
        history = history_result.unwrap()
        if len(history) == 0:
            return Err(InsufficientHistory(
                f"no {period.value} statements available for {ticker}"
            ))

        statements = history.statements
        ratios: list[tuple[str, dict[str, float | None]]] = []
        for idx, current in enumerate(statements):
            prior = statements[idx + 1] if idx + 1 < len(statements) else None
            ratios.append((current.period.label(), derive.ratio_rows(current, prior)))

        # accruals_ratio was already computed for the latest period in `ratios`
        # above (ratios[0] is statements[0] vs statements[1]); reuse it rather
        # than recomputing the whole panel inside _quality.
        quality = (
            self._quality(company, history, ratios[0][1]["accruals_ratio"])
            if len(history) >= 2
            else None
        )
        return Ok(AnalysisReport(
            company=company, history=history, ratios=ratios, quality=quality
        ))

    def _quality(
        self, company: Company, history: FinancialHistory, accruals: float | None
    ) -> QualitySummary:
        current, prior = history.statements[0], history.statements[1]
        c_inc, c_bal, c_cf = current.income, current.balance, current.cash_flow
        p_inc, p_bal, p_cf = prior.income, prior.balance, prior.cash_flow

        pio = piotroski_f(PiotroskiInputs(
            net_income=amount_of(c_inc.net_income),
            operating_cash_flow=amount_of(c_cf.operating_cash_flow),
            total_assets=amount_of(c_bal.total_assets),
            prior_total_assets=amount_of(p_bal.total_assets),
            prior_net_income=amount_of(p_inc.net_income),
            long_term_debt=amount_of(c_bal.long_term_debt),
            prior_long_term_debt=amount_of(p_bal.long_term_debt),
            current_assets=amount_of(c_bal.total_current_assets),
            current_liabilities=amount_of(c_bal.total_current_liabilities),
            prior_current_assets=amount_of(p_bal.total_current_assets),
            prior_current_liabilities=amount_of(p_bal.total_current_liabilities),
            shares_out=c_inc.weighted_shares_diluted,
            prior_shares_out=p_inc.weighted_shares_diluted,
            gross_profit=amount_of(c_inc.gross_profit),
            revenue=amount_of(c_inc.revenue),
            prior_gross_profit=amount_of(p_inc.gross_profit),
            prior_revenue=amount_of(p_inc.revenue),
        ))

        altman = altman_z(
            total_current_assets=amount_of(c_bal.total_current_assets),
            total_current_liabilities=amount_of(c_bal.total_current_liabilities),
            total_assets=amount_of(c_bal.total_assets),
            retained_earnings=amount_of(c_bal.retained_earnings),
            ebit=amount_of(c_inc.operating_income),
            market_cap=amount_of(company.market_cap),
            total_liabilities=amount_of(c_bal.total_liabilities),
            revenue=amount_of(c_inc.revenue),
        )

        def beneish_period(inc, bal, cf) -> BeneishPeriod:
            return BeneishPeriod(
                receivables=amount_of(bal.receivables),
                revenue=amount_of(inc.revenue),
                gross_profit=amount_of(inc.gross_profit),
                total_assets=amount_of(bal.total_assets),
                current_assets=amount_of(bal.total_current_assets),
                ppe_net=amount_of(bal.ppe_net),
                depreciation_amortization=amount_of(cf.depreciation_amortization),
                sga_expense=amount_of(inc.sga_expense),
                total_debt=amount_of(bal.total_debt),
                total_liabilities=amount_of(bal.total_liabilities),
                net_income=amount_of(inc.net_income),
                operating_cash_flow=amount_of(cf.operating_cash_flow),
            )

        beneish = beneish_m(
            beneish_period(c_inc, c_bal, c_cf), beneish_period(p_inc, p_bal, p_cf)
        )
        return QualitySummary(
            piotroski=pio, altman=altman, beneish=beneish, accruals_ratio=accruals
        )
