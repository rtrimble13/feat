# Add lint, type-check, and coverage gates to CI

- **Lens:** Enhancement (CI / developer experience)
- **Priority:** P1
- **Impact:** Medium
- **Effort:** Low
- **Confidence:** High
- **Severity:** —

## Problem

CI (`.github/workflows/ci.yml:22-23`) runs only `python -m pytest -q`. There is:

- **no linter/formatter** (no `ruff`/`flake8`/`black`);
- **no type checker**, despite the code being pervasively typed with
  `from __future__ import annotations` and carrying many precise
  `# type: ignore[...]` suppressions (e.g. `cli/main.py:93,94`,
  `services/build_tearsheet.py:52`, `domain/quality/beneish.py:93`) — those
  suppressions are unverifiable claims without a checker;
- **no coverage measurement or threshold** (`pyproject.toml:19-23` dev deps are
  only `pytest` and `responses`; no `.coveragerc`/`pytest-cov`).

## Why it matters

Nothing mechanically prevents a merge that adds untested code (see backlog 001,
two whole untested services) or breaks a type contract. The `# type: ignore`
markers strongly imply the project was written *for* mypy — but without it in
CI, the annotations and suppressions can drift out of correctness silently.
This is the highest-leverage, lowest-effort structural improvement available.

## Proposed change

- Add dev extras: `ruff`, `mypy`, `pytest-cov`.
- Add CI steps (same matrix): `ruff check .`, `mypy feat`, and
  `pytest --cov=feat --cov-report=term-missing --cov-fail-under=<N>`.
- Introduce mypy at whatever strictness currently passes, then ratchet up
  (`disallow_untyped_defs`, etc.) in follow-ups. Set the initial coverage
  threshold at or just below the current measured level so it only ratchets
  upward.
- Add a minimal `[tool.ruff]` / `[tool.mypy]` config block to `pyproject.toml`.

## Acceptance criteria

- CI fails on a lint error, a type error, or a coverage regression below the
  threshold.
- The current tree passes all three gates (fix or explicitly baseline any
  existing violations rather than disabling the check wholesale).
- `pip install .[dev]` installs the new tools.

## Risk / blast radius

CI/config only — no runtime code. The main effort is getting the existing tree
to a green baseline for mypy/ruff; do that in the same PR so `main` stays green.
Avoid a blanket `ignore_errors` — baseline specific findings instead.
