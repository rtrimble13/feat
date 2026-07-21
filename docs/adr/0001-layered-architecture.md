# ADR 0001: Layered (hexagonal) architecture with domain-owned ports

## Status
Accepted

## Context
`feat`'s core value is finance math that must be correct, testable and
auditable. FMP is a third-party API with schema quirks that change; the CLI
surface and output formats will evolve independently of the math.

## Decision
Four layers with dependencies pointing inward only:
presentation (`cli`, `render`) → application (`services`) → domain
(`domain`) ← infrastructure (`infra`). The domain defines
`FundamentalsRepository` / `PriceRepository` ports; `FmpAdapter` implements
them. The domain performs no I/O and imports nothing from other layers.

## Consequences
- All ratio/valuation math is pure and unit-testable with no mocks, no
  network, no clock — the widest tier of the test pyramid.
- FMP schema changes (or a second data vendor) touch only `infra/fmp`.
- Output formats are a Strategy (`TableRenderer`, `JsonRenderer`,
  `CsvRenderer`); adding one touches no business logic.
- The cost is some mapping boilerplate at the adapter/`derive` seams,
  accepted deliberately.
