# feat — Fundamental Equity Analysis Tool

A composable, terminal-native CLI for CFA-grade fundamental equity analysis,
powered by the [Financial Modeling Prep](https://financialmodelingprep.com)
(FMP) API.

`feat` pulls a company's financials, computes the ratios and valuation models
a charterholder actually uses, screens a universe, and produces a defensible
tearsheet — without leaving the shell and without trusting any number you
can't trace back to its inputs. It is **not** a black-box fair-value oracle:
every derived figure is traceable to reported line items and disclosed
assumptions, missing data is flagged (never silently zeroed), and `feat`'s
own DCF is displayed beside FMP's pre-computed DCF as an independent
cross-check.

## Install

Requires Python 3.11+.

```sh
pip install .            # runtime
pip install .[dev]       # + pytest / responses for the test suite
```

## Configure

The API key comes from the environment only — never a file, never logged:

```sh
export FMP_API_KEY=your_key   # https://site.financialmodelingprep.com/developer/docs
```

Optional analyst defaults live in `~/.config/feat/config.toml`
(or pass `--config PATH`). All values are validated at startup:

```toml
risk_free_rate          = 0.042   # fractions, not percents
equity_risk_premium     = 0.05
default_tax_rate        = 0.21
default_terminal_growth = 0.025
default_horizon_years   = 5
default_years_history   = 10
rate_limit_per_minute   = 300     # match your FMP plan
cache_dir               = "~/.cache/feat"
output_format           = "table" # table | json | csv
```

## Use

```sh
feat analyze AAPL --ratios --statements     # three statements, full ratio panel, quality scores
feat value   AAPL --model dcf-fcff          # FCFF DCF w/ dual terminal value + sensitivity grid
feat value   AAPL --model reverse-dcf       # growth the current price implies
feat value   AAPL --model ddm --scenario bear
feat value   AAPL --mc 2000                 # Monte Carlo distribution of intrinsic value
feat screen  --sector Technology --min-mcap 1e10 --to-watchlist tech.txt
feat compare --peers AAPL                   # metric table vs FMP's peer set
feat report  AAPL --format html --out ./    # one-page tearsheet
cat tech.txt | feat analyze - --json        # batch from stdin, JSON to pipes
```

Global flags: `--json` / `--csv` (machine-readable stdout), `--no-color`,
`--offline` (cache only), `--snapshot` (replay cached responses regardless of
age, for reproducible reports), `--config PATH`, `-v` (debug logging with
API-call, cache and retry visibility).

Exit codes: `0` success · `1` unexpected · `2` usage · `3` symbol not found ·
`4` insufficient data · `5` rate limited · `6` FMP unavailable · `7` config
error. Batch runs report failed tickers on stderr and keep going.

## Architecture

Layered (hexagonal); dependencies point inward. The domain knows nothing
about FMP, HTTP or argparse.

```
feat/cli, feat/render      presentation: argparse, table/json/csv renderers
feat/services              use-cases: AnalyzeCompany, ValueCompany, ...
feat/domain                pure finance: ratios, DCF/DDM/RI, WACC, scores
feat/infra                 FmpClient (timeouts/retry/breaker/limiter),
                           FmpAdapter (JSON -> domain), cache, config, logging
```

Every ratio and model formula is documented in [`docs/formulas.md`](docs/formulas.md);
design decisions are recorded in [`docs/adr/`](docs/adr).

## Test

```sh
python -m pytest             # unit + integration (recorded fixtures) + e2e
```

No test touches the network: domain math is pure; the adapter runs against
recorded FMP fixtures; e2e invokes the CLI with stubbed HTTP.

## Not investment advice

`feat` presents analysis with disclosed assumptions. The user decides.
