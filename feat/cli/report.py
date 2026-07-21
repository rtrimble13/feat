"""`feat report` — assemble a tearsheet (markdown or HTML)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from feat.services.analyze_company import AnalyzeCompany
from feat.services.build_tearsheet import BuildTearsheet, to_html
from feat.services.value_company import ValueCompany


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "report",
        parents=[common],
        help="build a one-page tearsheet (markdown or HTML)",
    )
    parser.add_argument("tickers", nargs="+", metavar="TICKER",
                        help="one or more tickers, or '-' for stdin")
    parser.add_argument("--format", choices=["md", "html"], default="md")
    parser.add_argument("--model", default="dcf-fcff",
                        help="valuation model for the valuation section (default dcf-fcff)")
    parser.add_argument("--out", type=Path, metavar="PATH",
                        help="output file (default stdout; a directory for multiple tickers)")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, ctx) -> int:
    from feat.cli.main import read_tickers, report_error

    tickers = read_tickers(args.tickers)
    if args.out is not None:
        out_path = args.out.expanduser().resolve()
        if len(tickers) > 1 and out_path.exists() and not out_path.is_dir():
            print("feat: --out must be a directory when reporting multiple tickers",
                  file=sys.stderr)
            return 2

    analyzer = AnalyzeCompany(ctx.adapter)
    valuer = ValueCompany(ctx.adapter, ctx.adapter, ctx.config)
    service = BuildTearsheet(analyzer, valuer)

    exit_code = 0
    for ticker in tickers:
        result = service.run(ticker, model_name=args.model)
        if result.is_err():
            code = report_error(ctx, result.error)  # type: ignore[union-attr]
            exit_code = exit_code or code
            continue
        tearsheet = result.unwrap()
        content = to_html(tearsheet) if args.format == "html" else tearsheet.markdown + "\n"
        if args.out is None:
            sys.stdout.write(content)
        else:
            target = _target_path(args.out, ticker.symbol, args.format, many=len(tickers) > 1)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            print(f"feat: wrote {target}", file=sys.stderr)
    return exit_code


def _target_path(out: Path, symbol: str, fmt_name: str, many: bool) -> Path:
    out = out.expanduser().resolve()
    if many or out.is_dir():
        return out / f"{symbol.lower()}.{fmt_name}"
    return out
