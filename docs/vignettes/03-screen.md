# 3 — Building a shortlist with `feat screen`

> **Scenario.** You don't have a name yet — you have a thesis. "Large-cap
> technology, profitable enough to pay a dividend, not a meme." `feat screen`
> turns that sentence into a filtered universe and, more importantly, into a
> watchlist file the rest of the toolkit can consume.

## One filter at a time

Filters compose; add them until the universe is the size you want.

```sh
$ feat screen --sector Technology --min-mcap 1e10
```

```
feat screen

── Results ────────────────────────────────────
Symbol  Name                              Sector      Mkt cap   Price    Beta   Div    Exch
AAPL    Apple Inc.                        Technology  3.01T     195.89   1.28   0.96   NASDAQ
MSFT    Microsoft Corporation             Technology  2.79T     375.28   0.90   3.00   NASDAQ
NVDA    NVIDIA Corporation                Technology  1.20T     485.09   1.75   0.04   NASDAQ
AVGO    Broadcom Inc.                     Technology  462.10B    997.40   1.20   21.00  NASDAQ
...
50 matches · filters: {'sector': 'Technology', 'marketCapMoreThan': 10000000000.0}
```

The footer echoes the exact FMP parameters your flags mapped to — so you can
see that `--min-mcap 1e10` became `marketCapMoreThan: 1e10`, and reproduce or
tweak it with confidence.

## The full filter set

| Flag | Screens on |
|------|-----------|
| `--sector` / `--industry` | Classification |
| `--exchange` / `--country` | Listing venue |
| `--min-mcap` / `--max-mcap` | Market capitalisation band |
| `--min-price` / `--max-price` | Share-price band |
| `--min-beta` / `--max-beta` | Volatility band |
| `--min-volume` | Liquidity floor |
| `--min-dividend` | Minimum last annual dividend |
| `--limit` | Cap the number of matches (default 50, max 1000) |

Scientific notation is fine on the numeric flags (`1e10`, `2.5e9`), which is
far easier to read than `10000000000`.

Tighten the thesis — profitable enough to pay, not too jumpy:

```sh
$ feat screen --sector Technology --min-mcap 1e10 \
    --min-dividend 0.5 --max-beta 1.3 --limit 25
```

## The payoff: a watchlist you can pipe

The single most useful flag is `--to-watchlist`. It writes the matching
symbols, one per line, to a file — while still printing the table:

```sh
$ feat screen --sector Technology --min-mcap 1e10 --min-dividend 0.5 \
    --to-watchlist tech.txt
...
feat: wrote 18 symbols to /home/you/tech.txt
```

```sh
$ cat tech.txt
AAPL
MSFT
AVGO
...
```

That file is the hand-off to every other command. The screen is the top of
your funnel; the watchlist is what flows down it:

```sh
$ cat tech.txt | feat compare -                     # rank them (vignette 4)
$ cat tech.txt | feat value  - --model dcf-fcff --json > val.jsonl   # value them (vignette 2)
$ cat tech.txt | feat analyze - --ratios --json > reads.jsonl        # read them (vignette 1)
```

`feat` refuses to clobber a directory or special file where a watchlist
should go (exit code `2`), and creates parent directories for you — so
`--to-watchlist out/2024/tech.txt` just works.

## Getting the most out of it

- **Screen returns FMP's screener fields, not computed ratios.** It's a
  coarse first cut on classification, size, price, beta, volume and
  dividend. Do the fundamental filtering in `analyze`/`compare` on the
  survivors — that's where the ratios and quality scores live.
- **Machine-readable universe.** `--json` emits the filters and every matched
  row, so you can post-filter in `jq`:
  ```sh
  $ feat screen --sector Technology --min-mcap 1e10 --json \
    | jq -r '.matches[] | select(.beta < 1) | .symbol'
  ```
- **Keep it reproducible.** A screen is a moving target as the market moves;
  `--snapshot` replays the universe you first captured, so a shortlist you
  built for a memo still resolves to the same names later.

## Interpreting, honestly

A screen is a hypothesis generator, not a buy list. Everything it returns
still has to survive `analyze` (is the accounting clean?) and `value` (is it
actually cheap?). Its job is only to get you from *thousands of names* to a
*dozen worth an afternoon* — and to hand that dozen to the next command in a
form it can read.

---

Next: [4 — Comparing peers](04-compare.md).
