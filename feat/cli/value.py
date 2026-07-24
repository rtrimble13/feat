"""`feat value` — intrinsic and relative valuation with a chosen model."""

from __future__ import annotations

import argparse
import sys

from feat.cli import format as fmt
from feat.render.base import Document, Section, Table
from feat.services.value_company import (
    ValuationOverrides,
    ValuationReport,
    ValueCompany,
)

MODEL_CHOICES = ["dcf-fcff", "dcf-fcfe", "ddm", "residual-income", "relative", "reverse-dcf"]


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "value",
        parents=[common],
        help="value a company with DCF, DDM, residual income, relative or reverse DCF",
        description=(
            "Every model prints its assumptions; feat's own DCF is shown beside "
            "FMP's reference DCF as an independent cross-check."
        ),
    )
    parser.add_argument("tickers", nargs="+", metavar="TICKER",
                        help="one or more tickers, or '-' to read from stdin")
    parser.add_argument("--model", choices=MODEL_CHOICES, default="dcf-fcff")
    parser.add_argument("--wacc", type=float, metavar="X",
                        help="override WACC as a fraction (0.09 = 9%%)")
    parser.add_argument("--cost-of-equity", type=float, metavar="X",
                        help="override CAPM cost of equity (fraction)")
    parser.add_argument("--growth", type=float, metavar="X",
                        help="override initial growth (fraction; default: revenue CAGR)")
    parser.add_argument("--terminal-growth", type=float, metavar="X",
                        help="override terminal growth (fraction)")
    parser.add_argument("--horizon", type=int, metavar="N", help="explicit forecast years")
    parser.add_argument("--exit-multiple", type=float, metavar="X",
                        help="EV/EBITDA exit multiple for the alternate terminal value")
    parser.add_argument("--scenario", choices=["bull", "base", "bear"], default="base")
    parser.add_argument("--mc", type=int, default=0, metavar="N",
                        help="Monte Carlo draws over key inputs (0 = off)")
    parser.add_argument("--seed", type=int, default=42, help="Monte Carlo RNG seed")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace, ctx) -> int:
    from feat.cli.main import emit, read_tickers, report_error

    tickers = read_tickers(args.tickers)
    for frac_flag in ("wacc", "cost_of_equity", "growth", "terminal_growth"):
        value = getattr(args, frac_flag)
        if value is not None and not -0.5 <= value <= 1.0:
            print(f"feat: --{frac_flag.replace('_', '-')} is a fraction (0.09 = 9%), got {value}",
                  file=sys.stderr)
            return 2
    if args.horizon is not None and not 1 <= args.horizon <= 20:
        print("feat: --horizon must be between 1 and 20 years", file=sys.stderr)
        return 2
    if args.mc and args.mc < 100:
        print("feat: --mc needs at least 100 draws for meaningful percentiles", file=sys.stderr)
        return 2

    overrides = ValuationOverrides(
        wacc=args.wacc,
        cost_of_equity=args.cost_of_equity,
        growth=args.growth,
        terminal_growth=args.terminal_growth,
        horizon_years=args.horizon,
        exit_ev_ebitda=args.exit_multiple,
    )
    service = ValueCompany(ctx.adapter, ctx.config)

    exit_code = 0
    for ticker in tickers:
        result = service.run(
            ticker, args.model, overrides=overrides, scenario=args.scenario,
            monte_carlo_draws=args.mc, monte_carlo_seed=args.seed,
        )
        if result.is_err():
            code = report_error(ctx, result.error)  # type: ignore[union-attr]
            exit_code = exit_code or code
            continue
        emit(ctx, _document(result.unwrap()))
    return exit_code


def _document(report: ValuationReport) -> Document:
    company, outcome = report.company, report.outcome
    sections: list[Section] = []

    headline = [
        f"model {outcome.model} · scenario {report.scenario}",
        f"fair value/share: {fmt.money(outcome.fair_value_per_share)} {company.currency}",
    ]
    if outcome.fair_value_alt is not None:
        alt_label = "exit-multiple TV" if outcome.model.startswith("dcf") else "H-model"
        gap = None
        if outcome.fair_value_per_share:
            gap = outcome.fair_value_alt / outcome.fair_value_per_share - 1.0
        headline.append(
            f"fair value ({alt_label}): {fmt.money(outcome.fair_value_alt)}"
            + (f"  (gap {gap:+.1%} — sanity-check the terminal assumptions)" if gap is not None else "")
        )
    if outcome.price is not None:
        headline.append(f"market price: {fmt.money(outcome.price)}")
    if outcome.margin_of_safety is not None:
        headline.append(f"margin of safety: {outcome.margin_of_safety:+.1%}")
    if outcome.model == "reverse-dcf":
        implied = outcome.details.get("implied_growth")
        headline.append(
            f"implied FCFF growth to justify today's price: {implied:+.1%}"
            if implied is not None else "implied growth: not solvable in bracket"
        )
    if report.fmp_reference_dcf is not None:
        headline.append(
            f"FMP reference DCF (cross-check only): {fmt.money(report.fmp_reference_dcf)}"
        )
    sections.append(Section(title="Valuation", lines=headline))

    sections.append(Section(
        title="Assumptions (override with flags)",
        lines=[f"{key} = {_fmt_value(value)}" for key, value in outcome.assumptions.items()],
    ))

    if outcome.model == "relative":
        own = outcome.details.get("own_multiples", {})
        med = outcome.details.get("peer_median_multiples", {})
        keys = [k for k in own if own.get(k) is not None or med.get(k) is not None]
        table = Table(
            headers=["Multiple", company.ticker.symbol, "Peer median"],
            rows=[[k, fmt.times(own.get(k)), fmt.times(med.get(k))] for k in keys],
        )
        sections.append(Section(title="Multiples vs peers", table=table))

    if report.sensitivity is not None:
        grid = report.sensitivity
        table = Table(
            headers=["WACC \\ g"] + [f"{g:.1%}" for g in grid.growth_values],
            rows=[
                [f"{w:.1%}"] + [fmt.money(v) for v in row]
                for w, row in zip(grid.wacc_values, grid.fair_values)
            ],
        )
        sections.append(Section(
            title="Sensitivity (fair value/share)", table=table,
            lines=["note: — marks degenerate cells (discount rate ≤ growth)"],
        ))

    if report.monte_carlo is not None:
        mc = report.monte_carlo
        lines = [
            f"draws: {mc.valid_draws}/{mc.draws} valid",
            "intrinsic value percentiles: "
            + "  ".join(f"P{p}={fmt.money(v)}" for p, v in sorted(mc.percentiles.items())),
        ]
        if mc.prob_below_price is not None:
            lines.append(f"P(fair value < market price) = {mc.prob_below_price:.0%}")
        sections.append(Section(title="Monte Carlo", lines=lines))

    data = {
        "ticker": company.ticker.symbol,
        "model": outcome.model,
        "scenario": report.scenario,
        "fair_value_per_share": outcome.fair_value_per_share,
        "fair_value_alt": outcome.fair_value_alt,
        "price": outcome.price,
        "margin_of_safety": outcome.margin_of_safety,
        "fmp_reference_dcf": report.fmp_reference_dcf,
        "assumptions": outcome.assumptions,
        "details": outcome.details,
        "monte_carlo": (
            {"percentiles": report.monte_carlo.percentiles,
             "prob_below_price": report.monte_carlo.prob_below_price}
            if report.monte_carlo else None
        ),
    }
    return Document(
        title=f"feat value — {company.ticker.symbol}", sections=sections, data=data
    )


def _fmt_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)
