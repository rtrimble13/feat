"""Beta estimation.

- ``regression_beta``: OLS slope of stock returns on market returns
  (both computed from *adjusted* closes upstream).
- ``unlever`` / ``relever``: Hamada equations for bottom-up beta:
      beta_u = beta_l / (1 + (1 - t) x D/E)
      beta_l = beta_u x (1 + (1 - t) x D/E)
"""

from __future__ import annotations

from typing import Sequence


def simple_returns(prices: Sequence[float]) -> list[float]:
    """Period-over-period simple returns from a price series (oldest first)."""
    if len(prices) < 2:
        raise ValueError("need at least two prices to compute returns")
    out = []
    for prev, cur in zip(prices, prices[1:]):
        if prev <= 0:
            raise ValueError("non-positive price in series")
        out.append(cur / prev - 1.0)
    return out


def regression_beta(stock_returns: Sequence[float], market_returns: Sequence[float]) -> float:
    """OLS beta: cov(stock, market) / var(market)."""
    if len(stock_returns) != len(market_returns):
        raise ValueError("return series must be the same length")
    n = len(stock_returns)
    if n < 12:
        raise ValueError(f"need at least 12 observations for a stable beta, got {n}")
    mean_s = sum(stock_returns) / n
    mean_m = sum(market_returns) / n
    cov = sum((s - mean_s) * (m - mean_m) for s, m in zip(stock_returns, market_returns))
    var = sum((m - mean_m) ** 2 for m in market_returns)
    if var == 0:
        raise ValueError("market return variance is zero")
    return cov / var


def unlever(levered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    if debt_to_equity < 0:
        raise ValueError("debt/equity must be non-negative")
    return levered_beta / (1.0 + (1.0 - tax_rate) * debt_to_equity)


def relever(unlevered_beta: float, debt_to_equity: float, tax_rate: float) -> float:
    if debt_to_equity < 0:
        raise ValueError("debt/equity must be non-negative")
    return unlevered_beta * (1.0 + (1.0 - tax_rate) * debt_to_equity)
