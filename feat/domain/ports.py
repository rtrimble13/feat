"""Ports: domain-owned interfaces implemented by infrastructure.

The domain and application layers depend only on these abstractions;
``feat.infra.fmp.adapter.FmpAdapter`` implements them. If FMP changes,
or a second vendor is added, only the adapter changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from feat.domain.entities import Company, FinancialHistory
from feat.domain.errors import AnalysisError, Result
from feat.domain.values import PeriodType, Ticker


class FundamentalsRepository(ABC):
    """Access to company profiles and financial statements."""

    @abstractmethod
    def get_company(self, ticker: Ticker) -> Result[Company, AnalysisError]:
        ...

    @abstractmethod
    def get_history(
        self, ticker: Ticker, period: PeriodType, years: int
    ) -> Result[FinancialHistory, AnalysisError]:
        ...

    @abstractmethod
    def get_reference_dcf(self, ticker: Ticker) -> Result[float | None, AnalysisError]:
        """FMP's own DCF fair value, used only as a cross-check."""
        ...

    @abstractmethod
    def get_peers(self, ticker: Ticker) -> Result[list[Ticker], AnalysisError]:
        ...

    @abstractmethod
    def screen(self, filters: dict[str, str | float | int]) -> Result[list[dict], AnalysisError]:
        ...
