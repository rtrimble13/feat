# 4 — Comparing peers with `feat compare`

> **Scenario.** A single company's ratios are noise until you know what
> "normal" looks like for its neighbourhood. Is a 29× P/E rich? Is a 25% ROIC
> exceptional or table stakes? `feat compare` puts a name in cross-sectional
> context — against a list you choose or against the peer set FMP already
> maintains.

## Compare an explicit set

Name the tickers and get a metric-by-metric table with a peer median column:

```sh
$ feat compare AAPL MSFT GOOGL
```

```
feat compare — AAPL, MSFT, GOOGL

── Comparison ─────────────────────────────────
Metric              AAPL      MSFT      GOOGL     Median
revenue             383.29B   211.92B   307.39B   307.39B
revenue_growth      -2.8%     6.9%      8.7%      6.9%
gross_margin        44.1%     69.4%     56.6%     56.6%
operating_margin    29.8%     41.8%     27.4%     29.8%
net_margin          25.3%     34.1%     24.0%     25.3%
roic                55.3%     28.1%     26.5%     28.1%
roe                 156.1%    38.8%     27.4%     38.8%
net_debt_to_ebitda  -0.35x    -0.20x    -0.90x    -0.35x
fcf_conversion      1.03x     0.95x     0.88x     0.95x
pe                  29.14x    35.02x    26.30x    29.14x
ev_ebitda           22.90x    25.10x    16.40x    22.90x
pb                  45.51x    12.30x    6.40x     12.30x
dividend_yield      0.5%      0.8%      0.0%      0.5%
```

The **Median** column is the anchor. Read across a row and each name against
the peer median at once: Apple's ROE towers over the group (buyback-shrunk
equity), but its ROIC — a cleaner return measure — leads too, which is the
more durable signal. Its P/E sits right at the median; the premium narrative
lives in P/B, not earnings.

Any cell FMP couldn't support is `—`, and the median is computed only over
the names that *do* have the metric — one missing value never poisons the
column.

## Let FMP seed the peer set

Don't know the right comparables? Anchor on one ticker and let FMP's peer
list fill the set:

```sh
$ feat compare --peers AAPL
```

This expands to Apple plus its FMP-listed peers, with Apple kept first so
it's easy to find. Add your own names to FMP's set in the same run:

```sh
$ feat compare --peers AAPL DELL HPQ
```

## Pipe a shortlist straight in

The watchlist from vignette 3 drops in via `-`:

```sh
$ cat tech.txt | feat compare -
```

Partial failure is expected in batch work: a ticker with no statements is
reported on stderr (`feat: skipped XYZ: no statements for XYZ`) and the
comparison continues with the rest. You get a table of what *could* be
compared, never an all-or-nothing error.

## Choose your metrics

The default set spans growth, margins, returns, leverage and the headline
multiples. Override it with `--metrics` and a comma-separated list of metric
keys:

```sh
$ feat compare --peers NVDA \
    --metrics roic,gross_margin,revenue_growth,ev_ebitda,peg
```

Valid keys include everything `analyze` computes — the ratio families
(`gross_margin`, `roce`, `current_ratio`, `debt_to_equity`,
`interest_coverage`, `asset_turnover`, `dso`/`dio`/`dpo`,
`cash_conversion_cycle`, `accruals_ratio`, …), the per-share figures
(`eps_diluted`, `book_value_per_share`, `fcf_per_share`,
`dividends_per_share`), and the multiples (`pe`, `peg`, `pb`, `ps`,
`ev_ebitda`, `ev_ebit`, `ev_sales`, `ev_fcf`, `dividend_yield`). An unknown
key fails fast (exit code `2`) and lists what it didn't recognise, so a typo
never silently drops a column.

Each metric is formatted for what it is — percentages as `%`, multiples as
`x`, day-counts as `d`, big currency figures compacted (`383.29B`) — so a
wide table stays readable.

## Getting the most out of it

- **Rank the survivors of a screen.** `screen → compare` is the natural
  funnel: narrow to a universe, then line them up head to head.
  ```sh
  $ cat tech.txt | feat compare - --metrics roic,fcf_conversion,ev_ebitda
  ```
- **Pull the median as a benchmark.** `--json` exposes `rows`, `medians` and
  `failures` separately:
  ```sh
  $ feat compare --peers AAPL --json | jq '.medians.ev_ebitda'
  ```
- **Watch the failures block.** If half your set landed in `failures`, the
  median is thin — check the stderr lines before leaning on it.

## Interpreting, honestly

A peer median is a description of a group, not a fair value. "Below the median
P/E" is a reason to *look*, not a reason to buy — the discount may be
deserved. `compare` tells you where a name sits in its neighbourhood; whether
that spot is a bargain or a warning is what `analyze` and `value` are for.

---

Next: [5 — Producing a tearsheet](05-report.md).
