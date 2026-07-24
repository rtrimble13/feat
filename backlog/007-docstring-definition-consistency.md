# Reconcile docstrings and definitions with actual behavior

- **Lens:** Refactoring (documentation correctness / internal consistency)
- **Priority:** P3
- **Impact:** Low
- **Effort:** Low
- **Confidence:** Medium
- **Severity:** —

## Problem

Several docstrings/definitions promise behavior the code doesn't deliver, or are
internally inconsistent. None produces a wrong number in the current shipped
flow, but each is contract drift waiting to become a real bug:

1. **"Average" balances that are only sometimes averaged.**
   `profitability.py:9-14,39-54,85-95` and `efficiency.py:3,15-21` document
   ROA/ROE/ROIC/asset-turnover as using *average* balances, but the code averages
   only when the optional `prior_*` argument is supplied and otherwise uses the
   *ending* balance (e.g. `return_on_assets(100, 1000)` → 0.10 on ending assets).
2. **Two different "ROE".** `dupont.py` 3-way/5-way telescopes to
   NI / **ending** equity, while `return_on_equity` (`profitability.py:48-54`)
   uses **average** equity when a prior is present — so the DuPont-decomposed ROE
   and the headline ROE disagree for any year in which equity changed.
3. **A documented ratio that isn't implemented.** `leverage.py:6` documents
   `fixed-charge coverage = (EBIT + fixed charges) / (interest + fixed charges)`,
   but no such function exists in the module.
4. **Undocumented 0-fill.** `cashflows.py:22-23` silently defaults a missing
   `interest_expense`/`tax_rate` to 0 in FCFF. This is stated in
   `docs/formulas.md` but not in the module docstring, which only mentions the
   OCF/capex → None rule.

## Why it matters

The shipped numbers are correct, but the stated contracts are not — the moment
someone calls `return_on_assets` without a prior expecting an average, or builds
on the DuPont ROE assuming it equals `return_on_equity`, they get a subtly wrong
result that the docstring told them was fine. This is exactly how a clean
codebase acquires its first real bug.

## Proposed change

- Make the ratio docstrings state the actual rule: "average of current and prior
  when a prior period is supplied, else the ending balance."
- Reconcile DuPont vs `return_on_equity` on a single equity basis (pick average
  or ending, document it, and make both agree — or explicitly document why the
  decomposition uses ending equity).
- Either implement `fixed_charge_coverage` (even the interest-only v1
  approximation the docstring describes) or remove it from the docstring.
- Add the interest/tax 0-fill note to the `cashflows.py` module docstring so it
  matches `formulas.md`.

## Acceptance criteria

- Each docstring matches the function's actual behavior (verified by reading).
- DuPont ROE and `return_on_equity` either agree for a changed-equity fixture or
  the divergence is documented deliberately.
- `fixed_charge_coverage` is either implemented-and-tested or absent from docs.

## Risk / blast radius

If the fix is docs-only, zero runtime risk. If you choose to *unify* the ROE
basis (change DuPont or `return_on_equity` to match), that shifts a displayed
number — cover it with a test and call it out in review. Coordinate with backlog
004, which touches some of the same modules.
