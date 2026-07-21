"""Shared DCF machinery.

- ``growth_path``: linear fade from the initial growth rate to the
  terminal rate over the explicit horizon (a step-down multi-stage
  profile rather than a cliff).
- ``project_flows``: apply the path to a base flow.
- ``terminal_value_perpetuity``: TV_n = CF_n x (1+g) / (r - g)
- ``terminal_value_exit_multiple``: TV_n = metric_n x multiple
- ``present_value``: discount explicit flows and terminal value at r.

Both terminal-value methods are computed and surfaced; the gap between
them is a built-in sanity check, not an implementation detail.
"""

from __future__ import annotations

from dataclasses import dataclass


def growth_path(initial: float, terminal: float, years: int) -> list[float]:
    if years < 1:
        raise ValueError("horizon must be at least one year")
    if years == 1:
        return [initial]
    step = (terminal - initial) / (years - 1)
    return [initial + step * i for i in range(years)]


def project_flows(base: float, rates: list[float]) -> list[float]:
    flows = []
    level = base
    for r in rates:
        level *= 1.0 + r
        flows.append(level)
    return flows


def terminal_value_perpetuity(final_flow: float, discount_rate: float, terminal_growth: float) -> float:
    if discount_rate <= terminal_growth:
        raise ValueError(
            f"discount rate ({discount_rate:.2%}) must exceed terminal growth "
            f"({terminal_growth:.2%}) for a finite perpetuity value"
        )
    return final_flow * (1.0 + terminal_growth) / (discount_rate - terminal_growth)


def terminal_value_exit_multiple(final_metric: float, multiple: float) -> float:
    if multiple <= 0:
        raise ValueError("exit multiple must be positive")
    return final_metric * multiple


def present_value(flows: list[float], terminal_value: float, discount_rate: float) -> float:
    if discount_rate <= -1.0:
        raise ValueError("discount rate below -100%")
    pv = sum(cf / (1.0 + discount_rate) ** (t + 1) for t, cf in enumerate(flows))
    pv += terminal_value / (1.0 + discount_rate) ** len(flows)
    return pv


@dataclass(frozen=True, slots=True)
class DcfCore:
    """Result of one discounted projection under both TV methods."""

    projected_flows: list[float]
    tv_perpetuity: float
    tv_exit: float | None
    pv_perpetuity: float
    pv_exit: float | None


def run_dcf(
    base_flow: float,
    growth: float,
    terminal_growth: float,
    discount_rate: float,
    years: int,
    exit_metric_base: float | None = None,
    exit_multiple: float | None = None,
) -> DcfCore:
    rates = growth_path(growth, terminal_growth, years)
    flows = project_flows(base_flow, rates)
    tv_perp = terminal_value_perpetuity(flows[-1], discount_rate, terminal_growth)
    tv_exit = None
    pv_exit = None
    if exit_metric_base is not None and exit_multiple is not None:
        final_metric = project_flows(exit_metric_base, rates)[-1]
        tv_exit = terminal_value_exit_multiple(final_metric, exit_multiple)
        pv_exit = present_value(flows, tv_exit, discount_rate)
    return DcfCore(
        projected_flows=flows,
        tv_perpetuity=tv_perp,
        tv_exit=tv_exit,
        pv_perpetuity=present_value(flows, tv_perp, discount_rate),
        pv_exit=pv_exit,
    )
