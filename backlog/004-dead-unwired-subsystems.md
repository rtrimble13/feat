# Resolve dead / unwired subsystems: wire them or delete them

- **Lens:** Refactoring (dead code / over-engineering)
- **Priority:** P2
- **Impact:** Medium
- **Effort:** Medium
- **Confidence:** High
- **Severity:** —

## Problem

A sizable body of implemented (and in several cases tested) code has **no
production call site**, verified by grepping `feat/` for each symbol excluding
its definition and tests:

- `feat/domain/costofcapital/beta.py` — `regression_beta`, `simple_returns`,
  `unlever`, `relever` (used only in `tests/unit/test_costofcapital.py`).
- `FmpAdapter.get_adjusted_closes` (`adapter.py:292`) and `get_quote`
  (`adapter.py:276`), i.e. the entire `PriceRepository` port — no service calls
  either.
- `FinancialHistory.ttm_income` (`entities.py:159`) and `common_size_income`
  (`entities.py:195`) — tested, surfaced by no command.
- `chunk_symbols` (`adapter.py:316`) — tested, unused in production.
- Six endpoint templates never fetched: `KEY_METRICS`, `RATIOS`,
  `EARNINGS_SURPRISES`, `INSTITUTIONAL_HOLDERS`, `SHARES_FLOAT`, `SECTOR_PE`
  (`endpoints.py:52-63`).
- `ValueCompany.__init__` stores `self._prices` (`value_company.py:67`) but
  never reads it — it advertises a price dependency it doesn't use.

## Why it matters

~250+ lines of code that no command can reach. It misleads maintainers about
the tool's actual behavior, makes `ValueCompany`'s constructor signature lie
about its dependencies, and grows the maintenance/type/lint surface for zero
user value. It's low *risk* (much of it is tested) but real drag.

## Proposed change

Make a deliberate per-subsystem decision — do not leave anything half-wired:

- **Wire** the pieces with clear value (tracked as feature ideas in the review):
  bottom-up/regression beta as a CAPM cross-check (`beta.py` +
  `get_adjusted_closes`), and TTM/common-size views in `analyze`. If wired,
  `ValueCompany` should actually use `self._prices`.
- **Delete** the rest: drop unused endpoints, `chunk_symbols` (unless the
  batched-compare idea is taken), `get_quote`, and — if the price subsystem is
  not wired — the unused `prices` parameter on `ValueCompany` and the
  `PriceRepository` port.

Split into small PRs (one per subsystem) so each decision is reviewable.

## Acceptance criteria

- Every remaining public function/endpoint in the touched modules has a
  production call site (or a documented, tested public-API reason to exist).
- `ValueCompany` no longer takes a dependency it doesn't use, OR it now uses it.
- Tests for any deleted code are removed; tests for any newly-wired code cover
  the new path; suite still passes.

## Risk / blast radius

Deleting truly-dead code is low risk. The main care points: `PriceRepository`
is part of the domain `ports` contract, so removing it touches the port
definition and the adapter's declared bases; and any "wire it" choice is really
a feature (see the New feature ideas section of the review) that needs its own
design + tests. Coordinate this with backlog 007 (which touches the same
docstrings) to avoid churn.
