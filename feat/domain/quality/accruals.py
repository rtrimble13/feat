"""Sloan accruals ratio: (net income - operating cash flow) / avg total assets.

High positive accruals mean earnings are running ahead of cash — a
classic predictor of subsequent underperformance.
"""

from __future__ import annotations

from feat.domain.ratios.cashflow_quality import accruals_ratio

__all__ = ["accruals_ratio"]
