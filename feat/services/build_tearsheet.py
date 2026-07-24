"""Use-case: BuildTearsheet — one-page markdown/HTML summary of a company:
profile, trend sparklines, key ratios, quality scores and a valuation
summary with the FMP reference DCF cross-check."""

from __future__ import annotations

import html as html_mod
from dataclasses import dataclass

from feat.domain.errors import AnalysisError, Err, Result, Ok
from feat.domain.values import Ticker, amount_of
from feat.render.sparkline import sparkline
from feat.services.analyze_company import AnalysisReport, AnalyzeCompany
from feat.services.value_company import ValuationReport, ValueCompany


@dataclass(frozen=True, slots=True)
class Tearsheet:
    ticker: str
    markdown: str


_PCT_ROWS = [
    ("Gross margin", "gross_margin"),
    ("Operating margin", "operating_margin"),
    ("Net margin", "net_margin"),
    ("ROE", "roe"),
    ("ROIC", "roic"),
    ("Revenue growth", "revenue_growth"),
]
_X_ROWS = [
    ("Current ratio", "current_ratio"),
    ("Debt/EBITDA", "debt_to_ebitda"),
    ("Interest coverage", "interest_coverage"),
    ("OCF / Net income", "ocf_to_net_income"),
]


class BuildTearsheet:
    def __init__(self, analyzer: AnalyzeCompany, valuer: ValueCompany) -> None:
        self._analyzer = analyzer
        self._valuer = valuer

    def run(self, ticker: Ticker, model_name: str = "dcf-fcff") -> Result[Tearsheet, AnalysisError]:
        analysis_result = self._analyzer.run(ticker)
        if isinstance(analysis_result, Err):
            return analysis_result
        analysis = analysis_result.unwrap()

        valuation_result = self._valuer.run(ticker, model_name, with_sensitivity=False)
        valuation = valuation_result.unwrap() if valuation_result.is_ok() else None
        valuation_error = valuation_result.error if valuation_result.is_err() else None  # type: ignore[union-attr]

        markdown = self._markdown(analysis, valuation, valuation_error, model_name)
        return Ok(Tearsheet(ticker=ticker.symbol, markdown=markdown))

    def _markdown(
        self,
        analysis: AnalysisReport,
        valuation: ValuationReport | None,
        valuation_error: AnalysisError | None,
        model_name: str,
    ) -> str:
        company = analysis.company
        lines: list[str] = []
        price = amount_of(company.price)
        mcap = amount_of(company.market_cap)
        lines.append(f"# {company.name} ({company.ticker})")
        lines.append("")
        lines.append(
            f"**Sector:** {company.sector or '—'} · **Industry:** {company.industry or '—'} · "
            f"**Price:** {_fmt(price)} {company.currency} · **Mkt cap:** {_fmt_big(mcap)}"
        )
        lines.append("")

        lines.append("## Trends")
        lines.append("")
        for label, field_name in (("Revenue", "revenue"), ("Operating income", "operating_income"),
                                  ("Net income", "net_income")):
            series = analysis.history.trend(field_name)
            lines.append(f"- {label}: `{sparkline(series)}`  (latest {_fmt_big(series[-1] if series else None)})")
        lines.append("")

        lines.append("## Key ratios (latest fiscal year)")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---|")
        latest_label, latest = analysis.ratios[0]
        for label, key in _PCT_ROWS:
            lines.append(f"| {label} | {_fmt_pct(latest.get(key))} |")
        for label, key in _X_ROWS:
            lines.append(f"| {label} | {_fmt_x(latest.get(key))} |")
        lines.append("")
        lines.append(f"_Period: {latest_label}. '—' marks data FMP did not report._")
        lines.append("")

        if analysis.quality is not None:
            q = analysis.quality
            lines.append("## Quality & forensics")
            lines.append("")
            if q.piotroski:
                lines.append(
                    f"- Piotroski F-score: **{q.piotroski.score}** / {q.piotroski.evaluated} evaluable signals"
                )
            if q.altman:
                lines.append(f"- Altman Z-score: **{q.altman.z:.2f}** ({q.altman.zone})")
            if q.beneish:
                verdict = "flagged" if q.beneish.flag else "not flagged"
                lines.append(f"- Beneish M-score: **{q.beneish.m_score:.2f}** ({verdict})")
            if q.accruals_ratio is not None:
                lines.append(f"- Sloan accruals ratio: **{q.accruals_ratio:+.2%}**")
            lines.append("")

        lines.append(f"## Valuation ({model_name})")
        lines.append("")
        if valuation is not None:
            o = valuation.outcome
            lines.append(f"- Fair value: **{_fmt(o.fair_value_per_share)} {company.currency}**")
            if o.fair_value_alt is not None:
                lines.append(f"- Fair value (alt terminal method): {_fmt(o.fair_value_alt)}")
            if o.price is not None:
                lines.append(f"- Market price: {_fmt(o.price)}")
            if o.margin_of_safety is not None:
                lines.append(f"- Margin of safety: **{o.margin_of_safety:+.1%}**")
            if valuation.fmp_reference_dcf is not None:
                lines.append(
                    f"- FMP reference DCF (cross-check only): {_fmt(valuation.fmp_reference_dcf)}"
                )
            lines.append("")
            lines.append("Assumptions: " + ", ".join(
                f"{k}={_fmt_assumption(v)}" for k, v in o.assumptions.items()
            ))
        else:
            lines.append(f"_Valuation unavailable: {valuation_error.message if valuation_error else 'unknown'}_")
        lines.append("")
        lines.append("---")
        lines.append(
            "_Generated by feat. Every figure derives from reported FMP line items "
            "and the assumptions listed above. Not investment advice._"
        )
        return "\n".join(lines)


def to_html(tearsheet: Tearsheet) -> str:
    """Minimal, dependency-free HTML wrapper around the markdown tearsheet."""
    body = html_mod.escape(tearsheet.markdown)
    return (
        "<!DOCTYPE html>\n<html><head><meta charset='utf-8'>"
        f"<title>{html_mod.escape(tearsheet.ticker)} tearsheet</title>"
        "<style>body{font-family:ui-monospace,Menlo,monospace;max-width:900px;"
        "margin:2rem auto;padding:0 1rem;line-height:1.5;}pre{white-space:pre-wrap;}"
        "</style></head><body><pre>"
        f"{body}"
        "</pre></body></html>\n"
    )


def _fmt(value: float | None) -> str:
    return f"{value:,.2f}" if value is not None else "—"


def _fmt_big(value: float | None) -> str:
    if value is None:
        return "—"
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= threshold:
            return f"{value / threshold:,.2f}{suffix}"
    return f"{value:,.0f}"


def _fmt_pct(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else "—"


def _fmt_x(value: float | None) -> str:
    return f"{value:.2f}x" if value is not None else "—"


def _fmt_assumption(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)
