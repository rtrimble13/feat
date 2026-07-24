# Project Review — feat (Fundamental Equity Analysis Tool) — 2026-07-24

## Verdict & summary

`feat` is a genuinely well-engineered codebase — one of the cleaner small
projects I've reviewed. It uses disciplined hexagonal layering (cli → services
→ domain → infra/render, dependencies pointing inward), a rigorous
missing-data-is-never-zero policy enforced end-to-end, expected failures modeled
as `Result` values with stable exit codes, and a deterministic test suite
(injected clocks/sleepers, seeded RNG, mocked HTTP). I traced every financial
formula and found **no arithmetic or sign-inversion bugs** — the domain math is
correct and unusually careful about sign conventions and zero denominators.

The backlog is therefore not about firefighting; it's about closing the gap
between the code's high internal quality and what's actually *verified and
reachable*. The themes that matter: (1) two entire user-facing commands
(`compare`, `screen`) have **zero test coverage** and can regress silently;
(2) the resilience layer that is the whole point of the FMP client
(circuit-breaker recovery, rate-limiter timing, retry backoff) is **untested**
despite the seams being built for it; (3) CI runs tests but enforces **no lint,
type-check, or coverage gate** even though the code is heavily typed; (4) a
sizable, partly-tested subsystem (beta estimation, price history, TTM /
common-size, batching, six endpoints) is **built but unreachable** from any
command. None of these is a live Critical/High defect — there are no P0s — but
they are exactly the debt that lets a healthy codebase quietly rot.

## How this review was scoped

- **Language/stack:** Python 3.11+, standard library + `requests` + `tabulate`;
  ~5,200 LOC across 86 source files. Git history was available and used for
  churn (the churn-heavy files — `value_company.py`, `derive.py`, the FMP
  client/adapter, `beneish.py` — were all deep-read).
- **Read in full and traced:** the composition root (`cli/main.py`); the entire
  FMP infra (`client.py` retry/breaker/limiter, `adapter.py` schema mapping,
  `cache.py`, `config.py`, `endpoints.py`); the domain value objects and
  entities (`values.py`, `entities.py`); the services (`value_company.py`,
  `derive.py`, `analyze_company.py`, `compare_peers.py`, `screen_universe.py`,
  `build_tearsheet.py`); all valuation models (dcf/dcf_fcff/dcf_fcfe/ddm/
  residual_income/reverse_dcf/relative/factory) and forecasting
  (monte_carlo/sensitivity/scenarios); the render layer; and all five CLI
  command modules.
- **Verified independently via sub-agents:** all 13 financial-math modules
  (quality scores, ratio families, cash-flow reconstruction, CAPM/WACC/beta,
  DuPont telescoping) were cross-checked against their docstrings and standard
  definitions; and the full test suite was mapped for coverage gaps and test
  quality (skips/xfails/wall-clock/network/unseeded-random — none found).
- **Sampled, not exhaustively read:** the ADRs, vignettes, `formulas.md`,
  `scripts/bump_version.py`, and the test bodies themselves (read enough to
  judge quality and coverage, not line-by-line).
- **Confidence:** high on the infra/domain/services findings (deep-read +
  greps for call sites); the math is high-confidence clean.

## Findings

Ordered by priority tier (P0 → P3), then severity within tier. There are **no
P0 findings** — no Critical/High defects were found.

### [P1] `compare` and `screen` have zero test coverage — two dark features — [#3](https://github.com/rtrimble13/feat/issues/3)
- **Lens:** Refactoring (test coverage)
- **Priority:** P1 · **Impact:** High · **Effort:** Medium · **Severity:** — · **Confidence:** High
- **Evidence:** `feat/services/compare_peers.py` (103 lines), `feat/services/screen_universe.py` (100 lines), `feat/cli/compare.py`, `feat/cli/screen.py` — no unit tests; neither command is invoked anywhere in `tests/e2e/test_cli.py`.
- **Why it matters:** Two of the five shipped commands — including all peer-selection, median/multiple aggregation, and screener filter-mapping logic — are entirely unverified. A regression in `to_fmp_params`, peer dedup, or median math ships silently.
- **Recommendation:** Add unit tests for both services against a fake `FundamentalsRepository`, and e2e journeys for both commands (mirroring the existing `analyze`/`value` e2e style with `responses` fixtures).

### [P1] FMP resilience layer (breaker recovery, limiter timing, backoff) is untested — [#4](https://github.com/rtrimble13/feat/issues/4)
- **Lens:** Refactoring (test coverage) / Robustness
- **Priority:** P1 · **Impact:** High · **Effort:** Low · **Severity:** — · **Confidence:** High
- **Evidence:** `feat/infra/fmp/client.py:99` (`CircuitBreaker.allow` half-open), `:106` (`record_success` reset), `:72` (`RateLimiter.acquire` refill/throttle), `:191` (backoff delay + `Retry-After` override), `:260` (`_parse_retry_after`). Existing tests use a no-op sleeper and a 600 s real-clock cooldown, so recovery/timing paths never execute.
- **Why it matters:** These paths *are* the reason the client exists (surviving an FMP outage/rate-limit without amplifying it). A broken breaker-reset (stuck open) or a miscomputed token refill (over-throttle or blow the plan limit) would be a real production availability bug that today's suite cannot catch. The `clock`/`sleeper` seams to test this already exist and are unused.
- **Recommendation:** Fake-clock tests for: breaker open → cooldown elapse → half-open probe → `record_success` reset; token-bucket refill/throttle/burst and the `rate<=0` guard; backoff cap + jitter bounds + `Retry-After` override; and `_parse_retry_after` numeric and HTTP-date-fallback branches.

### [P1] CI has no lint, type-check, or coverage gate — [#5](https://github.com/rtrimble13/feat/issues/5)
- **Lens:** Enhancement (CI/DX)
- **Priority:** P1 · **Impact:** Medium · **Effort:** Low · **Severity:** — · **Confidence:** High
- **Evidence:** `.github/workflows/ci.yml:22-23` runs only `python -m pytest -q`; `pyproject.toml:19-23` dev deps are just `pytest` + `responses`. The code is pervasively typed and littered with `# type: ignore[...]` (e.g. `cli/main.py:93`, `services/build_tearsheet.py:52`), implying an intended-but-absent type checker.
- **Why it matters:** Nothing prevents untested code (like the two services above) or a type regression from merging. The `# type: ignore` comments are unverifiable claims without mypy in CI. This is the highest-leverage, lowest-effort structural improvement available.
- **Recommendation:** Add `ruff` (lint+format), `mypy` (the `# type: ignore` markers show it was designed for strict typing), and `pytest-cov` with a threshold, as CI steps and dev extras. Introduce mypy at the current passing level and ratchet.

### [P2] Dead / unwired subsystems inflate the surface — [#6](https://github.com/rtrimble13/feat/issues/6)
- **Lens:** Refactoring (dead code / over-engineering)
- **Priority:** P2 · **Impact:** Medium · **Effort:** Medium · **Severity:** — · **Confidence:** High
- **Evidence:** `feat/domain/costofcapital/beta.py` (all four functions), `FmpAdapter.get_adjusted_closes`/`get_quote` and the whole `PriceRepository` port, `FinancialHistory.ttm_income`/`common_size_income` (`entities.py:159,195`), `chunk_symbols` (`adapter.py:316`), and six endpoints (`KEY_METRICS`, `RATIOS`, `EARNINGS_SURPRISES`, `INSTITUTIONAL_HOLDERS`, `SHARES_FLOAT`, `SECTOR_PE`) have **no production call site** (verified by grep). `ValueCompany.__init__` stores `self._prices` (`value_company.py:67`) but never uses it.
- **Why it matters:** ~250+ lines of implemented, partly-tested code is unreachable from any command. It misleads maintainers about what the tool does, and `ValueCompany` advertises a price dependency it doesn't use. This is low-risk (it's tested) but real maintenance drag.
- **Recommendation:** Decide per subsystem: either **wire it** (see New feature ideas — bottom-up beta and TTM are genuinely valuable) or **delete it** and drop the unused `prices` parameter and endpoints. Don't leave it dangling.

### [P2] Cache temp-file collision under parallel same-symbol invocations — [#7](https://github.com/rtrimble13/feat/issues/7)
- **Lens:** Robustness (hidden bug)
- **Priority:** P2 · **Impact:** Medium · **Effort:** Low · **Severity:** Medium · **Confidence:** High
- **Evidence:** `feat/infra/cache.py:66-68` — `tmp = path.with_suffix(".tmp")` is a deterministic `<sha256>.tmp` per cache key, shared across processes; `tmp.replace(path)` follows.
- **Why it matters:** The README markets batch/pipe use, and users will naturally parallelize (`xargs -P4 feat analyze`). Two concurrent processes fetching the *same* endpoint write the same `.tmp`: one `replace()` can raise `FileNotFoundError` (→ generic exit 1) or a reader can parse a half-written file (→ `CacheCorruption`). The single-process happy path is fine.
- **Recommendation:** Make the temp name unique per writer — `tempfile.mkstemp(dir=self._dir)` or `<digest>.<pid>.<counter>.tmp` — then `os.replace` onto the final path (still atomic). Add a test simulating two writers to the same key.

### [P3] `historical_growth` miscounts the CAGR horizon on interior gaps — [#8](https://github.com/rtrimble13/feat/issues/8)
- **Lens:** Hidden bug
- **Priority:** P3 · **Impact:** Low · **Effort:** Low · **Severity:** Low · **Confidence:** High
- **Evidence:** `feat/services/derive.py:189-200` — `clean = [v for v in values if v is not None]` drops interior `None`s, then `years = len(window) - 1` and `(last/first)**(1/years)-1`. A missing middle year shortens the exponent's denominator.
- **Why it matters:** This CAGR seeds the default DCF `growth` in `value_company.py:186`. With a gap in the revenue series it computes growth over the wrong number of years, biasing the default forecast. Blast radius is limited: growth is clamped to [-20%, 25%] and is override-able via `--growth`, and complete series are the common case.
- **Recommendation:** Compute the span from the actual calendar distance between the first and last *present* points (or require a contiguous tail), not the count of non-null values.

### [P3] Docstrings/definitions promise behavior the code doesn't deliver — [#9](https://github.com/rtrimble13/feat/issues/9)
- **Lens:** Refactoring (correctness of documentation / internal consistency)
- **Priority:** P3 · **Impact:** Low · **Effort:** Low · **Severity:** — · **Confidence:** Medium
- **Evidence:** `profitability.py:9-10,39-54` and `efficiency.py:3,15-21` docstrings say ROA/ROE/ROIC/asset-turnover use *average* balances, but the code uses the *ending* balance when the optional `prior_*` arg is omitted. `dupont.py` ROE telescopes to NI/**ending** equity while `return_on_equity` uses **average** equity — two different "ROE"s for the same firm-year. `leverage.py:6` documents a `fixed-charge coverage` ratio that isn't implemented. `cashflows.py:22-23` silently 0-fills missing interest/tax (documented in `formulas.md` but not the module docstring).
- **Why it matters:** No wrong *numbers* in the shipped flow, but the definitions are internally inconsistent and the docstrings overstate the API — the kind of drift that becomes a real bug once someone builds on the stated contract.
- **Recommendation:** Make the docstrings match behavior (or vice-versa): state "average when a prior period is supplied, else ending"; reconcile DuPont vs `return_on_equity` on one equity basis; either implement `fixed_charge_coverage` or remove it from the docstring; note the FCFF 0-fill in the module docstring.

### [P3] Redundant full ratio-panel recompute for one metric — [#10](https://github.com/rtrimble13/feat/issues/10)
- **Lens:** Enhancement (performance / clarity)
- **Priority:** P3 · **Impact:** Low · **Effort:** Low · **Severity:** — · **Confidence:** High
- **Evidence:** `feat/services/analyze_company.py:124` calls `derive.ratio_rows(current, prior)` a second time solely to read `["accruals_ratio"]`, recomputing the entire ~40-metric panel already produced at `:62` for the latest period.
- **Why it matters:** Pure waste (recomputes every ratio family to pull one value). Trivial, but it also muddies intent. CPU cost is negligible at current scale.
- **Recommendation:** Compute `accruals_ratio` once (or read it from the already-computed `ratios[0]` dict) and pass it into `_quality`.

## New feature ideas

Quarantined and evidence-backed — no backlog docs generated (per the review
process). These are all motivated by code that already exists but isn't wired,
so they double as the "wire it" resolution to finding 004.

- **Bottom-up / regression beta as a cross-check to the profile beta** (P3) —
  *Evidence:* `domain/costofcapital/beta.py` (`regression_beta`, `simple_returns`,
  `unlever`/`relever`) and `FmpAdapter.get_adjusted_closes` are fully
  implemented **and unit/integration-tested**, and `ValueCompany` already
  receives a `PriceRepository` it never calls (`value_company.py:67`). CAPM
  currently trusts FMP's single `beta` field (`value_company.py:159`). Wiring a
  regression beta from adjusted closes (with a peer-median unlevered fallback)
  as a displayed cross-check matches the project's stated "never trust a number
  you can't trace" philosophy.
- **TTM and common-size views in `analyze`** (P3) — *Evidence:*
  `FinancialHistory.ttm_income` and `common_size_income` (`entities.py:159,195`)
  are implemented and tested but surfaced by no command. A `--ttm` and
  `--common-size` flag on `analyze` would expose existing capability.
- **Batched peer/compare fetching** (P3) — *Evidence:* `chunk_symbols`
  (`adapter.py:316`) exists and is tested for comma-batching, but `ComparePeers`
  fetches tickers one at a time (`compare_peers.py:45-51`). Using the batch path
  would cut API calls on large comparison sets.

If the intent is *not* to build these, fold them into finding 004 and delete the
dead code instead — the one thing to avoid is leaving them half-wired.

## What's done well

Name these so they're preserved:

- **Missing-data discipline (ADR 0002), enforced end-to-end.** A `MISSING`
  sentinel at the adapter boundary, `amount_of()` as the single bridge to
  `None`, None-propagating `div`/`avg`, gap-poisoned aggregates
  (`entities.py:114` `_sum_flow`), and "how many signals were evaluable" quality
  scores. This is the single most important correctness property for an analysis
  tool and it's applied consistently.
- **Correct, careful financial math.** Independent verification of all 13 math
  modules found zero sign or arithmetic errors — capex/dividends/interest are
  `abs()`-normalized, `net_debt_issued` is deliberately left signed, DuPont 3-
  and 5-way both telescope to ROE, and zero denominators are guarded everywhere.
- **Errors-as-values with stable exit codes** (`errors.py`, `cli/main.py:1-7`):
  expected vendor failures are returned and mapped to script-friendly exit codes
  (3/4/5/6/7), while genuinely unexpected errors fail loudly (`main.py:155`).
- **A properly deterministic test suite.** Injected clocks/sleepers, seeded
  Monte Carlo, `responses`-mocked HTTP — no wall-clock, network, or unseeded
  randomness, and no skips/xfails. The gaps are about *what* is tested, not
  *how*.
- **Security-conscious boundaries:** SSRF-defended endpoint templates
  (`endpoints.py:1-10`), path-traversal-safe cache keys via SHA-256
  (`cache.py:40-42`), API key from env only and never logged (`config.py`), a
  `Ticker` value object that rejects shell/path/URL payloads (`values.py:47`),
  and HTML output that escapes and `<pre>`-wraps untrusted issuer text
  (`build_tearsheet.py:144`).
