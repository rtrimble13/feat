"""CAPM cost of equity.

    r_e = r_f + beta x ERP

where r_f is the risk-free rate and ERP the equity risk premium, both
supplied via config (they are analyst assumptions, not data).
"""

from __future__ import annotations


def cost_of_equity(risk_free_rate: float, beta: float, equity_risk_premium: float) -> float:
    if equity_risk_premium < 0:
        raise ValueError("equity risk premium must be non-negative")
    return risk_free_rate + beta * equity_risk_premium
