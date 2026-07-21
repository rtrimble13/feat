# 1 — Reading a company with `feat analyze`

> **Scenario.** A name landed on your desk. Before you value anything, you
> want the shape of the business: is it growing, is it profitable, is it
> solvent, and — the part most tools skip — is the accounting clean? One
> command answers all four.

## The thirty-second read

```sh
$ feat analyze AAPL
```

```
feat analyze — AAPL

── Company ───────────────────────────────────
Apple Inc. · Technology / Consumer Electronics · NASDAQ
price 195.89 USD · mkt cap 3.01T · beta 1.28

── Trends (oldest → latest) ───────────────────
Revenue      ▁▂▃▄▅▆▆▇██  latest 383.29B
Net income   ▁▂▃▄▄▆▆▇▇█  latest 97.00B

── Core metrics ───────────────────────────────
Metric              FY2023   FY2022   FY2021   FY2020   FY2019   FY2018
Revenue growth      -2.8%    7.8%     33.3%    5.5%     -2.0%    15.9%
Gross margin        44.1%    43.3%    41.8%    38.2%    37.8%    38.3%
Operating margin    29.8%    30.3%    29.8%    24.1%    24.6%    26.7%
Net margin          25.3%    25.3%    25.9%    20.9%    21.2%    22.4%
ROE                 156.1%   197.0%   150.1%   87.9%    61.1%    55.6%
ROIC                55.3%    61.7%    51.7%    34.0%    29.8%    28.9%
FCFF                99.58B   111.44B  92.95B   73.37B   58.90B   64.12B
FCFE                99.58B   90.22B   80.67B   66.31B   58.24B   64.12B
note: — marks values FMP did not report; nothing is silently zeroed
```

Read it top to bottom:

- **Trends** are sparklines over your full history window (default 10 years).
  You see the *direction* of revenue and earnings at a glance before any
  ratio.
- **Core metrics** put growth, margins, returns and the two reconstructed
  free-cash-flow figures side by side, newest period first. FCFF and FCFE
  are rebuilt from raw statements (`OCF + interest×(1−tax) − capex` and
  `OCF − capex + net borrowing`), not lifted from a vendor field — so you can
  trace them.

That `156.1%` ROE isn't a bug; Apple's equity base is small after years of
buybacks. Which is exactly why you never read one ratio alone — turn on the
full panel.

## The full ratio panel

```sh
$ feat analyze AAPL --ratios
```

`--ratios` adds a **Full ratio panel** section: EBITDA margin, ROA, ROCE,
effective tax rate, the liquidity trio (current/quick/cash), the leverage
and coverage stack (net debt, debt/EBITDA, net-debt/EBITDA, debt/equity,
interest coverage), the efficiency block (asset turnover, DSO/DIO/DPO, cash
conversion cycle), per-share figures (EPS, BVPS, FCF/share, DPS, dilution
rate) and the cash-flow-quality diagnostics (OCF/NI, FCF conversion, capex
intensity, accruals ratio) — every one across the same period columns.

The **dilution rate** row is the one to watch on a serial repurchaser: a
persistently negative value confirms buybacks are actually shrinking the
share count, not just offsetting grants.

## The raw statements

```sh
$ feat analyze AAPL --statements
```

`--statements` adds a **Statements** section — the three financial
statements as reported line items (revenue through free cash flow),
compact-formatted (`383.29B`). Combine with `--ratios` to get the numerator,
the denominator, and the ratio all in one screen. Nothing is derived here;
it's the audit trail under everything above.

## The part that earns its keep: quality & forensics

When at least two periods exist, `feat` runs three forensic models and the
Sloan accruals ratio:

```
── Quality & forensics ────────────────────────
Piotroski F-score: 8/9 (9 signals evaluable)
Altman Z-score: 9.14 (safe)
Beneish M-score: -2.71 (not flagged)
Sloan accruals ratio: -1.86%
```

- **Piotroski F-score (0–9)** — nine fundamental-momentum signals. Crucially,
  a signal with missing inputs is *skipped and counted*, never scored 0, so
  `8/9 (9 evaluable)` and `8/9 (7 evaluable)` mean very different things.
- **Altman Z-score** — distress zones (`safe` / `grey` / `distress`). A
  falling Z over successive years is the story, not the level.
- **Beneish M-score** — earnings-manipulation likelihood. Above −1.78 it
  prints `FLAGGED — earnings-manipulation risk`. It requires two clean
  consecutive periods; if any of the eight indices can't be computed, `feat`
  returns *no* M-score rather than a misleading partial one.
- **Sloan accruals ratio** — how far earnings run ahead of cash. Large
  positive accruals are a classic predictor of future underperformance.

This section is why `analyze` is the first stop: a name can look cheap on
every multiple and still be flagged here.

## Getting the most out of it

**Quarterly view.** Switch cadence and window when you're tracking a recent
inflection:

```sh
$ feat analyze NVDA --period quarter --years 3
```

**Feed the machine.** `--json` emits the whole report — company, every
period's ratios, and the quality block — as one document:

```sh
$ feat analyze AAPL --ratios --json | jq '.quality.beneish'
{ "m": -2.71, "flagged": false }
```

**Batch a watchlist**, keep going past bad tickers, and pull one number each:

```sh
$ cat tech.txt | feat analyze - --json \
  | jq -r '[.ticker, (.quality.piotroski.score|tostring)] | @tsv'
AAPL	8
MSFT	7
NVDA	9
```

**Reproduce a read later** without the market moving under you:

```sh
$ feat analyze AAPL --ratios --snapshot   # replays the warmed cache
```

## Interpreting, honestly

`analyze` describes; it does not judge. A high F-score on a name with a
deteriorating Altman Z and rising accruals is a contradiction worth chasing,
not a verdict. The tool's job is to surface all four dimensions from traceable
inputs and flag every gap — the read is yours.

---

Next: [2 — Valuing a company](02-value.md).
