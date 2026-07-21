"""`feat compare` — cross-sectional metrics for explicit tickers or a peer set."""

from __future__ import annotations

import argparse
import sys

from feat.cli import format as fmt
from feat.domain.values import Ticker
from feat.render.base import Document, Section, Table
from feat.services.compare_peers import DEFAULT_METRICS, ComparePeers, ComparisonReport

_FORMATTERS = {
    "revenue": fmt.big, "market_cap": fmt.big, "net_debt": fmt.big,
    "revenue_growth": fmt.pct, "gross_margin": fmt.pct, "operating_margin": fmt.pct,
    "net_margin": fmt.pct, "roic": fmt.pct, "roe": fmt.pct, "roa": fmt.pct,
    "dividend_yield": fmt.pct, "accruals_ratio": fmt.pct, "capex_intensity": fmt.pct,
    "dilution_rate": fmt.pct,
}


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "compare",
        parents=[common],
        help="compare metrics across tickers or an FMP peer set",
    )
    parser.add_argument("tickers", nargs="*", metavar="TICKER",
                        help="tickers to compare, or '-' for stdin")
    parser.add_argument("--peers", metavar="TICKER",
                        help="seed the set from FMP's peer list for this ticker")
    parser.add_argument("--metrics", metavar="LIST",
                        help=f"comma-separated metric keys (default: {','.join(DEFAULT_METRICS[:4])},...)")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, ctx) -> int:
    from feat.cli.main import emit, read_tickers, report_error

    service = ComparePeers(ctx.adapter)
    if args.peers:
        seed_result = service.expand_peers(Ticker(args.peers))
        if seed_result.is_err():
            return report_error(ctx, seed_result.error)  # type: ignore[union-attr]
        tickers = seed_result.unwrap()
        if args.tickers:
            tickers += read_tickers(args.tickers)
    else:
        if not args.tickers:
            print("feat: compare needs tickers or --peers TICKER", file=sys.stderr)
            return 2
        tickers = read_tickers(args.tickers)

    metrics = None
    if args.metrics:
        metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]
        unknown = [m for m in metrics if m not in _known_metrics()]
        if unknown:
            print(f"feat: unknown metrics: {', '.join(unknown)}", file=sys.stderr)
            return 2

    result = service.run(tickers, metrics=metrics)
    if result.is_err():
        return report_error(ctx, result.error)  # type: ignore[union-attr]
    report = result.unwrap()
    for symbol, error in report.failures.items():
        print(f"feat: skipped {symbol}: {error.message}", file=sys.stderr)
    emit(ctx, _document(report))
    return 0


def _known_metrics() -> set[str]:
    from feat.services.compare_peers import DEFAULT_METRICS
    return set(DEFAULT_METRICS) | set(_FORMATTERS) | {
        "pe", "peg", "pb", "ps", "ev_ebitda", "ev_ebit", "ev_sales", "ev_fcf",
        "current_ratio", "quick_ratio", "debt_to_equity", "debt_to_ebitda",
        "net_debt_to_ebitda", "interest_coverage", "asset_turnover",
        "ocf_to_net_income", "fcf_conversion", "eps_diluted",
        "book_value_per_share", "fcf_per_share", "dividends_per_share",
        "dso", "dio", "dpo", "cash_conversion_cycle", "roce", "ebitda_margin",
    }


def _document(report: ComparisonReport) -> Document:
    symbols = list(report.rows)
    table = Table(
        headers=["Metric"] + symbols + ["Median"],
        rows=[
            [metric]
            + [_fmt(metric, report.rows[s].get(metric)) for s in symbols]
            + [_fmt(metric, report.medians.get(metric))]
            for metric in report.metrics
        ],
    )
    data = {
        "metrics": report.metrics,
        "rows": report.rows,
        "medians": report.medians,
        "failures": {s: e.message for s, e in report.failures.items()},
    }
    return Document(
        title="feat compare — " + ", ".join(symbols),
        sections=[Section(title="Comparison", table=table)],
        data=data,
    )


def _fmt(metric: str, value: float | None) -> str:
    formatter = _FORMATTERS.get(metric, fmt.times)
    if metric in {"dso", "dio", "dpo", "cash_conversion_cycle"}:
        formatter = fmt.days
    if metric in {"eps_diluted", "book_value_per_share", "fcf_per_share", "dividends_per_share"}:
        formatter = fmt.num
    return formatter(value)
