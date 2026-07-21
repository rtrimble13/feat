"""`feat analyze` — statements, ratios and quality scores for tickers."""

from __future__ import annotations

import argparse
import sys

from feat.cli import format as fmt
from feat.domain.values import PeriodType, amount_of
from feat.render.base import Document, Section, Table
from feat.render.sparkline import sparkline
from feat.services.analyze_company import AnalysisReport, AnalyzeCompany


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "analyze",
        parents=[common],
        help="three-statement view, ratios and quality scores",
        description="Pull statements from FMP and compute ratio and quality analysis.",
    )
    parser.add_argument("tickers", nargs="+", metavar="TICKER",
                        help="one or more tickers, or '-' to read from stdin")
    parser.add_argument("--period", choices=["annual", "quarter"], default="annual")
    parser.add_argument("--years", type=int, default=None,
                        help="years of history (default from config, 10)")
    parser.add_argument("--ratios", action="store_true", help="show the full ratio panel")
    parser.add_argument("--statements", action="store_true", help="show raw statement lines")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, ctx) -> int:
    from feat.cli.main import emit, read_tickers, report_error

    tickers = read_tickers(args.tickers)
    years = args.years if args.years is not None else ctx.config.default_years_history
    if years < 1:
        print("feat: --years must be at least 1", file=sys.stderr)
        return 2
    service = AnalyzeCompany(ctx.adapter)
    period = PeriodType(args.period)

    exit_code = 0
    for ticker in tickers:
        result = service.run(ticker, period=period, years=years)
        if result.is_err():
            code = report_error(ctx, result.error)  # type: ignore[union-attr]
            exit_code = exit_code or code
            continue  # one bad ticker never sinks the batch
        emit(ctx, _document(result.unwrap(), args))
    return exit_code


def _document(report: AnalysisReport, args: argparse.Namespace) -> Document:
    company = report.company
    sections: list[Section] = []

    sections.append(Section(
        title="Company",
        lines=[
            f"{company.name} · {company.sector or '—'} / {company.industry or '—'} "
            f"· {company.exchange or '—'}",
            f"price {fmt.money(amount_of(company.price))} {company.currency} · "
            f"mkt cap {fmt.big(amount_of(company.market_cap))} · beta {fmt.num(company.beta)}",
        ],
    ))

    labels = [label for label, _ in report.ratios]
    show = min(len(labels), 6)

    def ratio_row(name: str, key: str, formatter) -> list[str]:
        return [name] + [formatter(rows.get(key)) for _, rows in report.ratios[:show]]

    trend_lines = []
    for label, field_name in (("Revenue", "revenue"), ("Net income", "net_income")):
        series = report.history.trend(field_name)
        trend_lines.append(f"{label:<12} {sparkline(series)}  latest {fmt.big(series[-1] if series else None)}")
    sections.append(Section(title="Trends (oldest → latest)", lines=trend_lines))

    core = Table(
        headers=["Metric"] + labels[:show],
        rows=[
            ratio_row("Revenue growth", "revenue_growth", fmt.pct),
            ratio_row("Gross margin", "gross_margin", fmt.pct),
            ratio_row("Operating margin", "operating_margin", fmt.pct),
            ratio_row("Net margin", "net_margin", fmt.pct),
            ratio_row("ROE", "roe", fmt.pct),
            ratio_row("ROIC", "roic", fmt.pct),
            ratio_row("FCFF", "fcff", fmt.big),
            ratio_row("FCFE", "fcfe", fmt.big),
        ],
    )
    sections.append(Section(
        title="Core metrics", table=core,
        lines=["note: — marks values FMP did not report; nothing is silently zeroed"],
    ))

    if args.ratios:
        panel = Table(
            headers=["Ratio"] + labels[:show],
            rows=[
                ratio_row("EBITDA margin", "ebitda_margin", fmt.pct),
                ratio_row("ROA", "roa", fmt.pct),
                ratio_row("ROCE", "roce", fmt.pct),
                ratio_row("Effective tax rate", "effective_tax_rate", fmt.pct),
                ratio_row("Current ratio", "current_ratio", fmt.times),
                ratio_row("Quick ratio", "quick_ratio", fmt.times),
                ratio_row("Cash ratio", "cash_ratio", fmt.times),
                ratio_row("Net debt", "net_debt", fmt.big),
                ratio_row("Debt/EBITDA", "debt_to_ebitda", fmt.times),
                ratio_row("Net debt/EBITDA", "net_debt_to_ebitda", fmt.times),
                ratio_row("Debt/equity", "debt_to_equity", fmt.times),
                ratio_row("Interest coverage", "interest_coverage", fmt.times),
                ratio_row("Asset turnover", "asset_turnover", fmt.times),
                ratio_row("DSO", "dso", fmt.days),
                ratio_row("DIO", "dio", fmt.days),
                ratio_row("DPO", "dpo", fmt.days),
                ratio_row("Cash conversion cycle", "cash_conversion_cycle", fmt.days),
                ratio_row("EPS (diluted)", "eps_diluted", fmt.num),
                ratio_row("BVPS", "book_value_per_share", fmt.num),
                ratio_row("FCF/share", "fcf_per_share", fmt.num),
                ratio_row("DPS", "dividends_per_share", fmt.num),
                ratio_row("Dilution rate", "dilution_rate", fmt.pct),
                ratio_row("OCF/NI", "ocf_to_net_income", fmt.times),
                ratio_row("FCF conversion", "fcf_conversion", fmt.times),
                ratio_row("Capex intensity", "capex_intensity", fmt.pct),
                ratio_row("Accruals ratio", "accruals_ratio", fmt.pct),
            ],
        )
        sections.append(Section(title="Full ratio panel", table=panel))

    if args.statements:
        sections.append(_statements_section(report, labels, show))

    if report.quality is not None:
        q = report.quality
        lines = []
        if q.piotroski:
            lines.append(
                f"Piotroski F-score: {q.piotroski.score}/9 "
                f"({q.piotroski.evaluated} signals evaluable)"
            )
        if q.altman:
            lines.append(f"Altman Z-score: {q.altman.z:.2f} ({q.altman.zone})")
        if q.beneish:
            lines.append(
                f"Beneish M-score: {q.beneish.m_score:.2f} "
                f"({'FLAGGED — earnings-manipulation risk' if q.beneish.flag else 'not flagged'})"
            )
        if q.accruals_ratio is not None:
            lines.append(f"Sloan accruals ratio: {q.accruals_ratio:+.2%}")
        if lines:
            sections.append(Section(title="Quality & forensics", lines=lines))

    data = {
        "ticker": company.ticker.symbol,
        "company": {
            "name": company.name, "sector": company.sector,
            "industry": company.industry, "currency": company.currency,
            "price": amount_of(company.price),
            "market_cap": amount_of(company.market_cap), "beta": company.beta,
        },
        "periods": labels,
        "ratios": {label: rows for label, rows in report.ratios},
        "quality": _quality_data(report),
    }
    return Document(
        title=f"feat analyze — {company.ticker.symbol}", sections=sections, data=data
    )


def _statements_section(report: AnalysisReport, labels: list[str], show: int) -> Section:
    def line(name: str, getter) -> list[str]:
        return [name] + [
            fmt.big(amount_of(getter(s))) for s in report.history.statements[:show]
        ]

    table = Table(
        headers=["Line item"] + labels[:show],
        rows=[
            line("Revenue", lambda s: s.income.revenue),
            line("Cost of revenue", lambda s: s.income.cost_of_revenue),
            line("Gross profit", lambda s: s.income.gross_profit),
            line("Operating income", lambda s: s.income.operating_income),
            line("EBITDA", lambda s: s.income.ebitda),
            line("Net income", lambda s: s.income.net_income),
            line("Cash & equivalents", lambda s: s.balance.cash_and_equivalents),
            line("Total current assets", lambda s: s.balance.total_current_assets),
            line("Total assets", lambda s: s.balance.total_assets),
            line("Total debt", lambda s: s.balance.total_debt),
            line("Total liabilities", lambda s: s.balance.total_liabilities),
            line("Total equity", lambda s: s.balance.total_equity),
            line("Operating cash flow", lambda s: s.cash_flow.operating_cash_flow),
            line("Capex", lambda s: s.cash_flow.capital_expenditure),
            line("Free cash flow", lambda s: s.cash_flow.free_cash_flow),
            line("Dividends paid", lambda s: s.cash_flow.dividends_paid),
        ],
    )
    return Section(title="Statements", table=table)


def _quality_data(report: AnalysisReport) -> dict | None:
    q = report.quality
    if q is None:
        return None
    return {
        "piotroski": (
            {"score": q.piotroski.score, "evaluated": q.piotroski.evaluated,
             "signals": q.piotroski.signals}
            if q.piotroski else None
        ),
        "altman": (
            {"z": q.altman.z, "zone": q.altman.zone} if q.altman else None
        ),
        "beneish": (
            {"m": q.beneish.m_score, "flagged": q.beneish.flag} if q.beneish else None
        ),
        "accruals_ratio": q.accruals_ratio,
    }
