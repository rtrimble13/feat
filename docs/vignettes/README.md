# feat vignettes

Task-driven walkthroughs of every `feat` command. Each one follows an
analyst through a real question — not a flag reference, but *how you actually
use the tool to reach a defensible answer*. Read them in order the first
time; reach for one by name later.

| # | Vignette | Command | You'll learn to |
|---|----------|---------|-----------------|
| 0 | [Getting started](00-getting-started.md) | — | Install, configure, and read `feat`'s output and exit codes |
| 1 | [Reading a company](01-analyze.md) | `feat analyze` | Pull statements, ratios and forensic scores; spot accounting red flags |
| 2 | [Valuing a company](02-value.md) | `feat value` | Run DCF/DDM/RI/relative, stress it with scenarios, sensitivity and Monte Carlo |
| 3 | [Building a shortlist](03-screen.md) | `feat screen` | Filter a universe into a watchlist you can pipe onward |
| 4 | [Comparing peers](04-compare.md) | `feat compare` | Put a name in cross-sectional context against its peer set |
| 5 | [Producing a tearsheet](05-report.md) | `feat report` | Assemble a one-page markdown/HTML brief for a name |

## The through-line

These vignettes compose. A realistic session looks like:

```sh
# 3 — narrow a universe to a watchlist
feat screen --sector Technology --min-mcap 1e10 --min-dividend 0.5 \
     --to-watchlist tech.txt

# 4 — rank the survivors against each other
cat tech.txt | feat compare -

# 1 — read the most interesting name in depth
feat analyze AAPL --ratios --statements

# 2 — form a value opinion, then stress it
feat value AAPL --model dcf-fcff --scenario bear --mc 5000

# 5 — hand a colleague a one-pager
feat report AAPL --format html --out ./tearsheets/
```

Every number `feat` prints traces back to a reported FMP line item and the
assumptions shown beside it. A gap is always rendered `—`, never a silent
zero — so when you see a number, you can trust it came from somewhere.

## Conventions used in these vignettes

- Output blocks are **illustrative** — real figures depend on live FMP data
  and your config. Structure, columns and labels match what the tool emits.
- Rates are fractions everywhere: `0.09` means 9%, both on input flags and
  in printed assumptions.
- `$ ` precedes a shell command; everything else is program output.
