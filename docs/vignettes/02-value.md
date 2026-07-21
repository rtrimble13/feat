# 2 — Valuing a company with `feat value`

> **Scenario.** You've read the business (vignette 1) and it's clean and
> growing. Now: what is it worth, how confident are you, and what would have
> to be true for today's price to make sense? `feat value` is built so you
> never mistake a single point estimate for an answer.

Six models, one interface. Every run prints the assumptions it used and, for
the DCF family, sets `feat`'s own number **beside FMP's reference DCF** as an
independent cross-check.

```
dcf-fcff   firm free cash flow discounted at WACC → enterprise → equity/share
dcf-fcfe   equity free cash flow discounted at the cost of equity
ddm        dividend discount (two-stage headline, H-model alternate)
residual-income   book value + PV of excess returns (for financials/asset-heavy)
relative   peer-median multiples applied to your own metrics
reverse-dcf   solve for the growth the current price already implies
```

## Start with the default DCF

```sh
$ feat value AAPL --model dcf-fcff
```

```
feat value — AAPL

── Valuation ──────────────────────────────────
model dcf-fcff · scenario base
fair value/share: 182.44 USD
market price: 195.89
margin of safety: -7.4%
FMP reference DCF (cross-check only): 178.10

── Assumptions (override with flags) ──────────
base_fcff = 9.958e+10
growth_initial = 0.0721
terminal_growth = 0.025
wacc = 0.0912
horizon_years = 5
exit_ev_ebitda = None
net_debt = -4.9e+10
shares_diluted = 1.55e+10

── Sensitivity (fair value/share) ─────────────
WACC \ g    1.5%     2.0%     2.5%     3.0%     3.5%
8.1%        188.10   194.02   200.71   208.34   217.14
8.6%        179.44   184.52   190.22   196.67   204.02
9.1%        171.62   176.02   180.92   186.41   192.63
9.6%        164.52   168.35   172.59   177.30   182.58
10.1%       158.03   161.39   165.08   169.16   173.70
note: — marks degenerate cells (discount rate ≤ growth)
```

Everything you need to argue with the number is on screen:

- **Margin of safety** is `1 − price/fair value`: negative here means the
  price sits *above* `feat`'s fair value — a −7.4% margin, i.e. slightly
  rich.
- **The FMP reference DCF** is a completely separate calculation. When the
  two land close (182 vs 178), the estimate is at least not idiosyncratic to
  one set of assumptions. A large gap is a prompt to check your inputs.
- **The sensitivity grid** is the real output. A DCF *is* its WACC and
  terminal-growth assumptions; the grid shows fair value across a
  neighbourhood of both so you read a *range*, not a false-precision point.
  Cells where the discount rate would fall to or below growth render `—`
  rather than a nonsense number.

## Stress it with scenarios

The same model under a disclosed, symmetric shift of growth and discount
assumptions:

```sh
$ feat value AAPL --model dcf-fcff --scenario bear
```

`bear` trims growth, nudges terminal growth down and lifts the discount rate;
`bull` does the reverse; `base` is neutral. The shift is printed in the
assumptions block so it's never hidden. Run all three to bracket the name:

```sh
$ for s in bear base bull; do feat value AAPL --scenario $s --json \
    | jq -r "\"$s \\(.fair_value_per_share|round)\""; done
bear 151
base 182
bull 219
```

## Put a distribution around it: Monte Carlo

A point estimate hides how fragile it is. Draw the key inputs from
distributions and look at the spread:

```sh
$ feat value AAPL --model dcf-fcff --mc 5000
```

```
── Monte Carlo ────────────────────────────────
draws: 5000/5000 valid
intrinsic value percentiles: P5=148.20  P25=168.05  P50=182.10  P75=197.44  P95=221.83
P(fair value < market price) = 63%
```

`P(fair value < market price) = 63%` is the honest headline: under your
assumptions and their uncertainty, the stock is above intrinsic value in
about two of every three simulated worlds. The RNG is seeded (`--seed`, default
42) so the run is reproducible; `--mc` needs at least 100 draws to mean
anything. Monte Carlo applies to the two DCF models.

## Invert the question: reverse DCF

Instead of asking "what is it worth", ask "what is the market already
assuming?"

```sh
$ feat value AAPL --model reverse-dcf
```

```
── Valuation ──────────────────────────────────
model reverse-dcf · scenario base
fair value/share: 195.89 USD
market price: 195.89
implied FCFF growth to justify today's price: +9.4%
```

`feat` holds every other assumption fixed and solves for the initial FCFF
growth rate that reproduces the current price. Now the judgement is concrete:
*is 9.4% per year for five years achievable for this business?* That's a far
easier question to answer honestly than "what's the right multiple". If no
growth between −50% and +100% reproduces the price, `feat` says so rather
than guessing.

## Match the model to the business

**Dividend payers** — the two-stage DDM headline with an H-model alternate:

```sh
$ feat value KO --model ddm --scenario bear
```

**Financials and asset-heavy names**, where free cash flow is noisy — the
residual income model builds value from book value plus the present value of
returns above the cost of equity:

```sh
$ feat value JPM --model residual-income
```

**A market cross-check** — relative valuation applies peer-median multiples
(P/E, P/B, EV/EBITDA) to your own metrics and averages the implied values:

```sh
$ feat value AAPL --model relative
```

```
── Multiples vs peers ─────────────────────────
Multiple      AAPL      Peer median
pe            29.14x    24.80x
pb            45.51x    9.20x
ev_ebitda     22.90x    16.10x
```

Each model refuses gracefully when its precondition fails — a DCF on negative
base FCFF, a DDM on a non-payer — and points you at a model that fits, with
exit code `4`, instead of printing a meaningless number.

## Override anything

Derived defaults are a starting point, not a straitjacket. Every assumption
has a flag, and flags are validated as fractions (`0.09`, not `9`):

```sh
$ feat value AAPL --model dcf-fcff \
    --wacc 0.085 --terminal-growth 0.03 --growth 0.10 \
    --horizon 7 --exit-multiple 18
```

`--exit-multiple` turns on the **alternate terminal value**: `feat` computes
the terminal value a second way (EV/EBITDA exit) and prints both fair values
with the gap between them —

```
fair value (exit-multiple TV): 201.55  (gap +10.5% — sanity-check the terminal assumptions)
```

— because a wide gap between the perpetuity and exit-multiple terminal values
is telling you the terminal assumption is doing too much of the work.

## Getting the most out of it

- **Bracket, don't pinpoint.** The sensitivity grid, three scenarios and a
  Monte Carlo together describe a *range*; quote the range.
- **Cross-check reflexively.** If `feat`'s DCF and FMP's reference DCF
  disagree sharply, resolve *why* before trusting either.
- **Batch a book** and dump the machine-readable payload:
  ```sh
  $ cat holdings.txt | feat value - --model dcf-fcff --json \
    | jq -r '[.ticker, .fair_value_per_share, .margin_of_safety] | @csv'
  ```
- **Freeze a valuation** for a memo with `--snapshot` so the numbers don't
  drift between writing and review.

---

Next: [3 — Building a shortlist](03-screen.md).
