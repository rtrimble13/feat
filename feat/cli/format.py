"""Formatting helpers shared by CLI commands (presentation only)."""

from __future__ import annotations

from feat.render.base import GAP


def money(value: float | None) -> str:
    return f"{value:,.2f}" if value is not None else GAP


def big(value: float | None) -> str:
    """Compact large amounts: 1.23B, 45.6M."""
    if value is None:
        return GAP
    for threshold, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= threshold:
            return f"{value / threshold:,.2f}{suffix}"
    return f"{value:,.0f}"


def pct(value: float | None) -> str:
    return f"{value:.1%}" if value is not None else GAP


def times(value: float | None) -> str:
    return f"{value:.2f}x" if value is not None else GAP


def days(value: float | None) -> str:
    return f"{value:.0f}d" if value is not None else GAP


def num(value: float | None, digits: int = 2) -> str:
    return f"{value:,.{digits}f}" if value is not None else GAP
