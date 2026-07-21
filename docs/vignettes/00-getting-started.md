# 0 — Getting started

Before the command walkthroughs, five minutes on setup and on reading what
`feat` gives back. Everything here applies to every subcommand.

## Install

`feat` needs Python 3.11+ and nothing else at runtime beyond two small
libraries.

```sh
$ pip install .            # runtime
$ pip install .[dev]       # + pytest/responses to run the test suite
$ feat --version
feat 1.0.0
```

## Configure

The one thing `feat` requires is an FMP API key, read **from the environment
only** — never a file, never a log line:

```sh
$ export FMP_API_KEY=your_key   # https://site.financialmodelingprep.com/developer/docs
```

Everything else has a sensible default. To pin your analyst assumptions once,
drop a `~/.config/feat/config.toml` (or pass `--config PATH`):

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

The file is validated at startup, before any API call. An out-of-range ERP
or a rate written as `5` instead of `0.05` fails immediately with exit code
`7` and a message telling you which key is wrong — you never discover it
halfway through a valuation.

## Global flags (every command accepts these)

| Flag | Effect |
|------|--------|
| `--json` / `--csv` | Machine-readable output to stdout instead of a table |
| `--no-color` | Disable ANSI color (also auto-off when stdout isn't a TTY) |
| `--offline` | Serve from cache only; never touch the network |
| `--snapshot` | Replay cached responses regardless of age — reproducible reports, no look-ahead |
| `--config PATH` | Use a specific config file |
| `-v` / `--verbose` | Debug logging: API calls, cache hits, retries, and full tracebacks on unexpected errors |

`--offline` and `--snapshot` are what make `feat` reproducible. Run an
analysis once online to warm the cache, then hand a colleague the same
`--snapshot` invocation and they get byte-identical numbers a week later,
even after the market moved.

## Reading the output

A table run is a title, then labelled sections:

```
feat analyze — AAPL

── Company ───────────────────────────────────
Apple Inc. · Technology / Consumer Electronics · NASDAQ
price 195.89 USD · mkt cap 3.01T · beta 1.28
...
```

Three rules hold everywhere:

1. **`—` means missing, not zero.** If FMP didn't report a line item, the
   cell is a gap. A ratio built on a gap is itself a gap — `feat` never
   fabricates a denominator.
2. **Assumptions travel with the number.** Any model that makes a choice
   (a growth rate, a discount rate) prints it, so you can challenge it.
3. **Newest period first** in ratio/statement tables; trend sparklines and
   CAGRs run oldest → latest.

## Exit codes

`feat` is built to script. Every outcome has a stable code:

| Code | Meaning |
|------|---------|
| 0 | success |
| 1 | unexpected error (a bug — rerun with `-v` for the traceback) |
| 2 | usage / invalid input (bad flag, bad ticker, out-of-range fraction) |
| 3 | symbol not found |
| 4 | insufficient data to compute |
| 5 | rate limited by FMP |
| 6 | FMP unavailable |
| 7 | configuration error |

In a batch (`feat analyze AAPL MSFT NVDA`), a failing ticker is reported on
stderr and the run continues; the process exits with the first non-zero
code so `&&` chains still short-circuit correctly.

## Working in pipes

`-` reads tickers from stdin, so commands compose:

```sh
$ printf 'AAPL\nMSFT\n' | feat analyze - --json | jq '.ratios'
```

With `--json`, each ticker emits one JSON document; combine with `jq` to
extract exactly the fields you want. That's the backbone of the multi-step
sessions in the vignettes that follow.

---

Next: [1 — Reading a company](01-analyze.md).
