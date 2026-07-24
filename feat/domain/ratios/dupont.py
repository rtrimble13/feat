"""DuPont ROE decomposition.

3-way: ROE = net margin x asset turnover x equity multiplier
5-way: ROE = tax burden x interest burden x operating margin
             x asset turnover x equity multiplier
where tax burden = NI / pre-tax income, interest burden = pre-tax income / EBIT.

Balances here are point-in-time (period-end), so the factors multiply back to
an exact identity (NI / ending equity). This decomposed ROE can therefore
differ from ``profitability.return_on_equity``, which divides by *average*
equity when a prior period is available — the two answer slightly different
questions and are not expected to match in a year when equity changed.
"""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.ratios import div


@dataclass(frozen=True, slots=True)
class DuPont3:
    net_margin: float | None
    asset_turnover: float | None
    equity_multiplier: float | None

    @property
    def roe(self) -> float | None:
        parts = (self.net_margin, self.asset_turnover, self.equity_multiplier)
        if any(p is None for p in parts):
            return None
        return parts[0] * parts[1] * parts[2]  # type: ignore[operator]


@dataclass(frozen=True, slots=True)
class DuPont5:
    tax_burden: float | None
    interest_burden: float | None
    operating_margin: float | None
    asset_turnover: float | None
    equity_multiplier: float | None

    @property
    def roe(self) -> float | None:
        parts = (
            self.tax_burden,
            self.interest_burden,
            self.operating_margin,
            self.asset_turnover,
            self.equity_multiplier,
        )
        if any(p is None for p in parts):
            return None
        product = 1.0
        for p in parts:
            product *= p  # type: ignore[operator]
        return product


def dupont_3way(
    net_income: float | None,
    revenue: float | None,
    total_assets: float | None,
    total_equity: float | None,
) -> DuPont3:
    return DuPont3(
        net_margin=div(net_income, revenue),
        asset_turnover=div(revenue, total_assets),
        equity_multiplier=div(total_assets, total_equity),
    )


def dupont_5way(
    net_income: float | None,
    income_before_tax: float | None,
    operating_income: float | None,
    revenue: float | None,
    total_assets: float | None,
    total_equity: float | None,
) -> DuPont5:
    return DuPont5(
        tax_burden=div(net_income, income_before_tax),
        interest_burden=div(income_before_tax, operating_income),
        operating_margin=div(operating_income, revenue),
        asset_turnover=div(revenue, total_assets),
        equity_multiplier=div(total_assets, total_equity),
    )
