"""Use-case: ComparePeers — cross-sectional metrics for a set of tickers.

Partial failure is expected in batch work: a bad ticker is reported in
``failures`` and the run continues with the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from feat.domain.errors import AnalysisError, Err, InsufficientHistory, Ok, Result
from feat.domain.ports import FundamentalsRepository
from feat.domain.valuation.relative import MultipleInputs, compute_multiples, median
from feat.domain.values import PeriodType, Ticker, amount_of
from feat.services import derive

DEFAULT_METRICS = [
    "revenue", "revenue_growth", "gross_margin", "operating_margin", "net_margin",
    "roic", "roe", "net_debt_to_ebitda", "fcf_conversion",
    "pe", "ev_ebitda", "pb", "dividend_yield",
]


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    metrics: list[str]
    #: ticker -> metric -> value (None = missing, flagged in render)
    rows: dict[str, dict[str, float | None]]
    medians: dict[str, float | None]
    failures: dict[str, AnalysisError] = field(default_factory=dict)


class ComparePeers:
    def __init__(self, fundamentals: FundamentalsRepository) -> None:
        self._fundamentals = fundamentals

    def run(
        self,
        tickers: list[Ticker],
        metrics: list[str] | None = None,
    ) -> Result[ComparisonReport, AnalysisError]:
        metrics = metrics or DEFAULT_METRICS
        rows: dict[str, dict[str, float | None]] = {}
        failures: dict[str, AnalysisError] = {}
        for ticker in tickers:
            result = self._one(ticker)
            if result.is_err():
                failures[ticker.symbol] = result.error  # type: ignore[union-attr]
                continue
            all_metrics = result.unwrap()
            rows[ticker.symbol] = {m: all_metrics.get(m) for m in metrics}
        if not rows:
            first = next(iter(failures.values()), None)
            return Err(first or InsufficientHistory("no tickers could be compared"))
        medians = {
            m: median([row[m] for row in rows.values() if row[m] is not None])
            for m in metrics
        }
        return Ok(ComparisonReport(
            metrics=metrics, rows=rows, medians=medians, failures=failures
        ))

    def expand_peers(self, ticker: Ticker) -> Result[list[Ticker], AnalysisError]:
        """Seed a comparison set from FMP's peer list, anchored on the ticker."""
        peers_result = self._fundamentals.get_peers(ticker)
        if peers_result.is_err():
            return peers_result
        return Ok([ticker] + [p for p in peers_result.unwrap() if p != ticker])

    def _one(self, ticker: Ticker) -> Result[dict[str, float | None], AnalysisError]:
        company_result = self._fundamentals.get_company(ticker)
        if company_result.is_err():
            return company_result
        company = company_result.unwrap()
        history_result = self._fundamentals.get_history(ticker, PeriodType.ANNUAL, 2)
        if history_result.is_err():
            return history_result
        history = history_result.unwrap()
        if len(history) == 0:
            return Err(InsufficientHistory(f"no statements for {ticker}"))
        latest = history.statements[0]
        prior = history.statements[1] if len(history) > 1 else None
        rows = derive.ratio_rows(latest, prior)
        multiples = compute_multiples(MultipleInputs(
            price=amount_of(company.price),
            market_cap=amount_of(company.market_cap),
            net_debt=derive.net_debt_of(latest),
            eps_diluted=latest.income.eps_diluted,
            book_value_per_share=rows["book_value_per_share"],
            revenue=amount_of(latest.income.revenue),
            ebitda=amount_of(latest.income.ebitda),
            ebit=amount_of(latest.income.operating_income),
            fcf=derive.fcff_of(latest),
            dividends_per_share=rows["dividends_per_share"],
            growth=rows["revenue_growth"],
        ))
        merged: dict[str, float | None] = {
            **rows,
            **multiples,
            "revenue": amount_of(latest.income.revenue),
            "market_cap": amount_of(company.market_cap),
        }
        return Ok(merged)
