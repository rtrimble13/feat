"""`feat screen` — filter a universe via FMP's screener."""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from feat.cli import format as fmt
from feat.render.base import Document, Section, Table
from feat.services.screen_universe import ScreenFilters, ScreenReport, ScreenUniverse


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "screen",
        parents=[common],
        help="screen a universe with composable filters",
    )
    parser.add_argument("--sector")
    parser.add_argument("--industry")
    parser.add_argument("--exchange")
    parser.add_argument("--country")
    parser.add_argument("--min-mcap", type=float, metavar="N")
    parser.add_argument("--max-mcap", type=float, metavar="N")
    parser.add_argument("--min-price", type=float, metavar="N")
    parser.add_argument("--max-price", type=float, metavar="N")
    parser.add_argument("--min-beta", type=float, metavar="N")
    parser.add_argument("--max-beta", type=float, metavar="N")
    parser.add_argument("--min-volume", type=float, metavar="N")
    parser.add_argument("--min-dividend", type=float, metavar="N")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--to-watchlist", type=Path, metavar="PATH",
                        help="also write matching symbols, one per line")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, ctx) -> int:
    from feat.cli.main import emit, report_error

    filters = ScreenFilters(
        sector=args.sector,
        industry=args.industry,
        exchange=args.exchange,
        country=args.country,
        min_market_cap=args.min_mcap,
        max_market_cap=args.max_mcap,
        min_price=args.min_price,
        max_price=args.max_price,
        min_beta=args.min_beta,
        max_beta=args.max_beta,
        min_volume=args.min_volume,
        min_dividend=args.min_dividend,
        limit=args.limit,
    )
    result = ScreenUniverse(ctx.adapter).run(filters)
    if result.is_err():
        return report_error(ctx, result.error)  # type: ignore[union-attr]
    report = result.unwrap()
    emit(ctx, _document(report))

    if args.to_watchlist is not None:
        path = args.to_watchlist.expanduser().resolve()
        if path.exists() and not path.is_file():
            print(f"feat: refusing to write watchlist to non-file path {path}", file=sys.stderr)
            return 2
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(r.symbol for r in report.rows) + "\n", encoding="utf-8")
        print(f"feat: wrote {len(report.rows)} symbols to {path}", file=sys.stderr)
    return 0


def _document(report: ScreenReport) -> Document:
    table = Table(
        headers=["Symbol", "Name", "Sector", "Mkt cap", "Price", "Beta", "Div", "Exch"],
        rows=[
            [
                r.symbol,
                (r.name or "")[:32],
                r.sector or "—",
                fmt.big(r.market_cap),
                fmt.money(r.price),
                fmt.num(r.beta),
                fmt.num(r.dividend),
                r.exchange or "—",
            ]
            for r in report.rows
        ],
    )
    active = {k: v for k, v in report.filters.to_fmp_params().items() if k != "limit"}
    lines = [f"{len(report.rows)} matches" + (f" · filters: {active}" if active else "")]
    data = {
        "filters": report.filters.to_fmp_params(),
        "matches": [asdict(r) for r in report.rows],
    }
    return Document(
        title="feat screen",
        sections=[Section(title="Results", table=table, lines=lines)],
        data=data,
    )
