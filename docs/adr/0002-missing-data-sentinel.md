# ADR 0002: Missing data is a first-class sentinel, never zero

## Status
Accepted

## Context
FMP returns `[]` for unknown symbols and omits fields for some issuers.
Coercing an absent EBITDA to 0 silently corrupts every ratio and model
downstream (a 0 EBITDA makes debt/EBITDA infinite and margins nonsense) —
the single worst failure mode for an analysis tool.

## Decision
- The adapter maps absent/null fields to a `MISSING` sentinel wrapped in the
  domain type; entities carry `MoneyLike = Money | MissingType`.
- The `amount_of()` bridge turns MISSING into `None`; all pure math is
  None-propagating (`div`, `avg`), and a zero denominator is also `None`.
- Renderers display gaps as "—"; JSON emits `null`.
- Aggregates are poisoned by gaps (a TTM sum with a missing quarter is
  missing, a Beneish score with a missing index is no score).
- Quality scores report how many signals were evaluable instead of scoring
  missing signals as failures.

## Consequences
Every consumer must handle `None`, which is verbose but makes data gaps
visible at every level — the analyst always knows what the number is *not*
built on.
