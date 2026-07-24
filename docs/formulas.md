# feat — formula reference

Every derived figure in `feat` follows a documented definition. Inputs are
reported FMP line items; missing inputs propagate as gaps ("—"), never zeros.
Rates are fractions throughout (0.15 = 15%).

## Free cash flow reconstruction (`feat/domain/cashflows.py`)

- **FCFF** = OCF + interest expense × (1 − effective tax rate) − capex
- **FCFE** = OCF − capex + net debt issued
- Capex sign is normalized (FMP reports it as a negative investing outflow).
- Missing OCF or capex ⇒ FCF is missing. Missing interest/borrowing is an
  adjustment leg and treated as 0.

## Profitability (`domain/ratios/profitability.py`)

- gross / operating / EBITDA / net margin = line item ÷ revenue
- ROA = net income ÷ average total assets (single-period assets when no prior)
- ROE = net income ÷ average total equity (single-period when no prior)
- effective tax rate = income tax expense ÷ pre-tax income, clamped to [0, 1]
- NOPAT = operating income × (1 − effective tax rate)
- **invested capital = total debt + total equity − cash & equivalents**
- ROIC = NOPAT ÷ average invested capital (single-period when no prior)
- ROCE = EBIT ÷ (total assets − current liabilities)
- value-creation spread = ROIC − WACC

## DuPont (`domain/ratios/dupont.py`)

- 3-way: ROE = net margin × asset turnover × equity multiplier
- 5-way: ROE = tax burden × interest burden × operating margin × asset
  turnover × equity multiplier, with tax burden = NI ÷ pre-tax income and
  interest burden = pre-tax income ÷ EBIT

## Liquidity (`domain/ratios/liquidity.py`)

- current = current assets ÷ current liabilities
- quick = (cash + short-term investments + receivables) ÷ current liabilities
- cash = (cash + short-term investments) ÷ current liabilities
- defensive interval (days) = quick assets ÷ (cash opex ÷ 365)

## Leverage (`domain/ratios/leverage.py`)

- net debt = total debt − cash & equivalents
- debt/EBITDA, net debt/EBITDA, debt/equity
- interest coverage = EBIT ÷ |interest expense|

## Efficiency (`domain/ratios/efficiency.py`)

- asset turnover = revenue ÷ average total assets
- DSO = receivables ÷ revenue × 365, DIO = inventory ÷ COGS × 365,
  DPO = payables ÷ COGS × 365
- cash conversion cycle = DSO + DIO − DPO

## Per-share (`domain/ratios/pershare.py`)

- BVPS = total equity ÷ diluted shares; FCF/share; DPS = |dividends paid| ÷
  diluted shares; dilution rate = YoY growth of diluted share count

## Cash-flow quality (`domain/ratios/cashflow_quality.py`)

- OCF/NI, FCF conversion = FCF ÷ NI, capex intensity = |capex| ÷ revenue
- Sloan accruals ratio = (NI − OCF) ÷ average total assets

## Cost of capital (`domain/costofcapital/`)

- CAPM: r_e = r_f + β × ERP
- Beta: taken from the FMP company profile (β = 1.0 when absent)
- Cost of debt: |interest expense| ÷ total debt, else r_f + 200 bps
- WACC = E/(D+E) × r_e + D/(D+E) × r_d × (1 − t), market-value weights
  (market cap for E, book total debt as the standard proxy for D)

## Valuation (`domain/valuation/`)

Common machinery: growth fades **linearly** from the initial rate to the
terminal rate over the horizon. Terminal value is computed **two ways** and
both are surfaced:

- perpetuity: TV = CF_n × (1 + g) ÷ (r − g), requires r > g
- exit multiple: TV = terminal metric × multiple (EV/EBITDA for FCFF)

Models:

- **dcf-fcff**: EV = PV(FCFF) + PV(TV) at WACC; equity = EV − net debt
- **dcf-fcfe**: equity = PV(FCFE) + PV(TV) at cost of equity
- **ddm**: Gordon V = D1/(r−g); two-stage (explicit dividends then Gordon);
  H-model V = [D0(1+g_L) + D0·H·(g_S−g_L)] ÷ (r−g_L), H = horizon/2
- **residual-income**: V = B0 + Σ PV((ROE − r_e)·B_{t−1}) + PV(terminal RI),
  clean-surplus book value growth B_t = B_{t−1}(1 + ROE·(1−payout)),
  terminal RI faded by persistence ω = 0.6: TV = RI_{n+1} ÷ (1 + r_e − ω)
- **relative**: P/E, PEG, P/B, P/S, EV/EBITDA, EV/EBIT, EV/Sales, EV/FCF,
  dividend yield vs peer medians; fair value = mean of implied values
  (median P/E × EPS, median P/B × BVPS, median EV/EBITDA ⇒ equity/share).
  Multiples over non-positive denominators are meaningless ⇒ gap.
- **reverse-dcf**: bisection on initial growth in [−50%, +100%] until the
  FCFF DCF reproduces the market price; result is the implied growth hurdle
- margin of safety = 1 − price ÷ fair value

## Scenarios, sensitivity, Monte Carlo (`domain/forecasting/`)

- bull/base/bear shift growth ±3 pp, terminal growth ±0.5 pp, discount
  −0.5/+1.0 pp (disclosed in output; override with flags)
- sensitivity grid: fair value over WACC × terminal growth (±2 steps of
  0.5 pp); degenerate cells (r ≤ g) render as gaps
- Monte Carlo: independent normal draws on growth (σ=2 pp), terminal growth
  (σ=0.5 pp) and discount rate (σ=1 pp); reports P5/P25/P50/P75/P95 and
  P(fair value < price); seeded RNG for reproducibility

## Quality & forensic scores (`domain/quality/`)

- **Piotroski F** (0–9): ROA>0, OCF>0, ΔROA>0, OCF>NI, Δleverage<0,
  Δcurrent ratio>0, no dilution, Δgross margin>0, Δasset turnover>0.
  Unevaluable signals are skipped and reported, not scored 0.
- **Altman Z** (1968): Z = 1.2·WC/TA + 1.4·RE/TA + 3.3·EBIT/TA + 0.6·MVE/TL
  + 1.0·Sales/TA; zones: >2.99 safe, 1.81–2.99 grey, <1.81 distress
- **Beneish M** (8-variable): M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI
  + 0.892·SGI + 0.115·DEPI − 0.172·SGAI + 4.679·TATA − 0.327·LVGI;
  M > −1.78 flags manipulation risk; any missing index ⇒ no score
- **Sloan accruals** = (NI − OCF) ÷ average total assets
