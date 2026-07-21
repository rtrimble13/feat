"""feat — Fundamental Equity Analysis Tool.

A layered, terminal-native application for CFA-grade fundamental equity
analysis powered by the Financial Modeling Prep (FMP) API.

Layers (dependencies point inward):

- ``feat.cli`` / ``feat.render``  — presentation
- ``feat.services``               — application use-cases (orchestration only)
- ``feat.domain``                 — pure finance logic; no I/O
- ``feat.infra``                  — FMP client/adapter, cache, config, logging
"""

__version__ = "1.0.0"
