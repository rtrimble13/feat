"""Beneish M-score (8-variable) for earnings-manipulation risk.

    M = -4.84 + 0.920 DSRI + 0.528 GMI + 0.404 AQI + 0.892 SGI
        + 0.115 DEPI - 0.172 SGAI + 4.679 TATA - 0.327 LVGI

M > -1.78 flags a likely manipulator. Requires two consecutive periods;
returns None if any index cannot be computed (no silent substitution of
neutral values — a partial M-score is not an M-score).
"""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.ratios import div


@dataclass(frozen=True, slots=True)
class BeneishPeriod:
    receivables: float | None
    revenue: float | None
    gross_profit: float | None
    total_assets: float | None
    current_assets: float | None
    ppe_net: float | None
    depreciation_amortization: float | None
    sga_expense: float | None
    total_debt: float | None
    net_income: float | None
    operating_cash_flow: float | None


@dataclass(frozen=True, slots=True)
class BeneishResult:
    m_score: float
    flag: bool  # True when M > -1.78
    indices: dict[str, float]


def beneish_m(current: BeneishPeriod, prior: BeneishPeriod) -> BeneishResult | None:
    dsri = div(div(current.receivables, current.revenue), div(prior.receivables, prior.revenue))
    gmi = div(div(prior.gross_profit, prior.revenue), div(current.gross_profit, current.revenue))

    def asset_quality(p: BeneishPeriod) -> float | None:
        if p.total_assets is None or p.current_assets is None or p.ppe_net is None:
            return None
        if p.total_assets == 0:
            return None
        return 1.0 - (p.current_assets + p.ppe_net) / p.total_assets

    aqi = div(asset_quality(current), asset_quality(prior))
    sgi = div(current.revenue, prior.revenue)

    def depr_rate(p: BeneishPeriod) -> float | None:
        if p.depreciation_amortization is None or p.ppe_net is None:
            return None
        denom = p.depreciation_amortization + p.ppe_net
        return p.depreciation_amortization / denom if denom else None

    depi = div(depr_rate(prior), depr_rate(current))
    sgai = div(div(current.sga_expense, current.revenue), div(prior.sga_expense, prior.revenue))
    tata = (
        div(current.net_income - current.operating_cash_flow, current.total_assets)
        if current.net_income is not None and current.operating_cash_flow is not None
        else None
    )
    lvgi = div(div(current.total_debt, current.total_assets), div(prior.total_debt, prior.total_assets))

    indices = {
        "DSRI": dsri, "GMI": gmi, "AQI": aqi, "SGI": sgi,
        "DEPI": depi, "SGAI": sgai, "TATA": tata, "LVGI": lvgi,
    }
    if any(v is None for v in indices.values()):
        return None
    m = (
        -4.84
        + 0.920 * indices["DSRI"]
        + 0.528 * indices["GMI"]
        + 0.404 * indices["AQI"]
        + 0.892 * indices["SGI"]
        + 0.115 * indices["DEPI"]
        - 0.172 * indices["SGAI"]
        + 4.679 * indices["TATA"]
        - 0.327 * indices["LVGI"]
    )
    return BeneishResult(m_score=m, flag=m > -1.78, indices=indices)  # type: ignore[arg-type]
