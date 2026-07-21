"""feat CLI root: argument parsing, composition root, dispatch, exit codes.

Exit codes (stable, script-friendly):
  0 success · 1 unexpected error · 2 usage/invalid input · 3 symbol not
  found · 4 insufficient data · 5 rate limited · 6 FMP unavailable ·
  7 configuration error
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import requests

from feat import __version__
from feat.domain.errors import AnalysisError
from feat.domain.values import Ticker
from feat.infra.cache import DiskCache
from feat.infra.config import FeatConfig, load_config
from feat.infra.fmp.adapter import FmpAdapter
from feat.infra.fmp.client import CircuitBreaker, FmpClient, RateLimiter, Timeouts
from feat.infra.logging import setup_logging
from feat.render.base import Document, Renderer
from feat.render.csv import CsvRenderer
from feat.render.json import JsonRenderer
from feat.render.table import TableRenderer


@dataclass
class CliContext:
    """Everything a command needs, wired once at startup."""

    config: FeatConfig
    adapter: FmpAdapter
    renderer: Renderer
    logger: logging.Logger
    out: "object"  # writable stream
    verbose: bool


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feat",
        description="Fundamental Equity Analysis Tool — CFA-grade analysis from the terminal.",
    )
    parser.add_argument("--version", action="version", version=f"feat {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    output = common.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="machine-readable JSON to stdout")
    output.add_argument("--csv", action="store_true", help="CSV to stdout")
    common.add_argument("--no-color", action="store_true", help="disable ANSI color")
    common.add_argument("--offline", action="store_true",
                        help="serve from cache only; no network calls")
    common.add_argument("--snapshot", action="store_true",
                        help="replay cached responses regardless of age for reproducible reports")
    common.add_argument("--config", type=Path, metavar="PATH",
                        help="config file (default ~/.config/feat/config.toml)")
    common.add_argument("-v", "--verbose", action="store_true",
                        help="debug logging: API calls, cache hits, retries")

    subparsers = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    from feat.cli import analyze, compare, report, screen, value
    for module in (analyze, value, screen, compare, report):
        module.register(subparsers, common)
    return parser


def read_tickers(raw: list[str]) -> list[Ticker]:
    """Expand '-' to stdin lines and parse every symbol into a Ticker."""
    symbols: list[str] = []
    for item in raw:
        if item == "-":
            symbols.extend(line.strip() for line in sys.stdin if line.strip())
        else:
            symbols.append(item)
    return [Ticker(s) for s in symbols]


def build_context(args: argparse.Namespace) -> CliContext | int:
    correlation_id = setup_logging(verbose=args.verbose)
    logger = logging.getLogger("feat.cli")
    logger.debug("invocation", extra={"command": args.command, "correlation": correlation_id})

    config_result = load_config(
        config_path=args.config, require_api_key=not args.offline
    )
    if config_result.is_err():
        print(f"feat: {config_result.error.message}", file=sys.stderr)  # type: ignore[union-attr]
        return config_result.error.exit_code  # type: ignore[union-attr]
    config = config_result.unwrap()

    cache = DiskCache(config.cache_dir)
    client = FmpClient(
        api_key=config.api_key,
        http=requests.Session(),
        limiter=RateLimiter(config.rate_limit_per_minute),
        breaker=CircuitBreaker(),
        timeouts=Timeouts(),
        logger=logging.getLogger("feat.fmp"),
        cache=cache,
        offline=args.offline,
        snapshot=args.snapshot,
    )
    adapter = FmpAdapter(client)

    if args.json:
        renderer: Renderer = JsonRenderer()
    elif args.csv:
        renderer = CsvRenderer()
    elif config.output_format == "json":
        renderer = JsonRenderer()
    elif config.output_format == "csv":
        renderer = CsvRenderer()
    else:
        renderer = TableRenderer(color=not args.no_color and sys.stdout.isatty())
    return CliContext(
        config=config,
        adapter=adapter,
        renderer=renderer,
        logger=logger,
        out=sys.stdout,
        verbose=args.verbose,
    )


def emit(ctx: CliContext, document: Document) -> None:
    ctx.out.write(ctx.renderer.render(document))  # type: ignore[attr-defined]


def report_error(ctx: CliContext, error: AnalysisError) -> int:
    print(f"feat: {error.message}", file=sys.stderr)
    return error.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        context = build_context(args)
        if isinstance(context, int):
            return context
        return args.handler(args, context)
    except ValueError as exc:
        # invalid domain input (bad ticker, bad model name) — usage error
        print(f"feat: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("feat: interrupted", file=sys.stderr)
        return 130
    except Exception:
        # Unexpected: a bug or corrupt state — fail loudly, never swallow.
        if "-v" in (argv or sys.argv) or "--verbose" in (argv or sys.argv):
            raise
        print(
            "feat: unexpected error (run with -v for the full traceback)",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
