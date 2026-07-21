"""Piotroski F-score: nine binary signals, 0-9 (higher is stronger).

Profitability: ROA > 0; OCF > 0; ROA improved YoY; OCF > net income.
Leverage/liquidity: long-term debt ratio fell; current ratio rose;
no new shares issued.
Efficiency: gross margin rose; asset turnover rose.

Signals with missing inputs are skipped and reported, not scored as 0 —
the score is returned with the number of evaluable signals.
"""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.ratios import div


@dataclass(frozen=True, slots=True)
class PiotroskiInputs:
    net_income: float | None
    operating_cash_flow: float | None
    total_assets: float | None
    prior_total_assets: float | None
    prior_net_income: float | None
    long_term_debt: float | None
    prior_long_term_debt: float | None
    current_assets: float | None
    current_liabilities: float | None
    prior_current_assets: float | None
    prior_current_liabilities: float | None
    shares_out: float | None
    prior_shares_out: float | None
    gross_profit: float | None
    revenue: float | None
    prior_gross_profit: float | None
    prior_revenue: float | None


@dataclass(frozen=True, slots=True)
class PiotroskiScore:
    score: int
    evaluated: int  # how many of the 9 signals had data
    signals: dict[str, bool | None]  # None = not evaluable


def piotroski_f(i: PiotroskiInputs) -> PiotroskiScore:
    roa = div(i.net_income, i.total_assets)
    prior_roa = div(i.prior_net_income, i.prior_total_assets)
    lt_ratio = div(i.long_term_debt, i.total_assets)
    prior_lt_ratio = div(i.prior_long_term_debt, i.prior_total_assets)
    cr = div(i.current_assets, i.current_liabilities)
    prior_cr = div(i.prior_current_assets, i.prior_current_liabilities)
    gm = div(i.gross_profit, i.revenue)
    prior_gm = div(i.prior_gross_profit, i.prior_revenue)
    at = div(i.revenue, i.total_assets)
    prior_at = div(i.prior_revenue, i.prior_total_assets)

    def cmp(a: float | None, b: float | None, op: str) -> bool | None:
        if a is None or b is None:
            return None
        return a > b if op == ">" else a < b

    signals: dict[str, bool | None] = {
        "positive_roa": roa > 0 if roa is not None else None,
        "positive_ocf": i.operating_cash_flow > 0 if i.operating_cash_flow is not None else None,
        "roa_improved": cmp(roa, prior_roa, ">"),
        "ocf_exceeds_ni": cmp(i.operating_cash_flow, i.net_income, ">"),
        "leverage_decreased": cmp(lt_ratio, prior_lt_ratio, "<"),
        "current_ratio_improved": cmp(cr, prior_cr, ">"),
        "no_dilution": (
            i.shares_out <= i.prior_shares_out
            if i.shares_out is not None and i.prior_shares_out is not None
            else None
        ),
        "gross_margin_improved": cmp(gm, prior_gm, ">"),
        "asset_turnover_improved": cmp(at, prior_at, ">"),
    }
    evaluated = sum(1 for v in signals.values() if v is not None)
    score = sum(1 for v in signals.values() if v is True)
    return PiotroskiScore(score=score, evaluated=evaluated, signals=signals)
