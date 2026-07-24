"""Use-case: ScreenUniverse — filter FMP's screener into a clean table."""

from __future__ import annotations

from dataclasses import dataclass

from feat.domain.errors import AnalysisError, Err, InvalidInput, Ok, Result
from feat.domain.ports import FundamentalsRepository


@dataclass(frozen=True, slots=True)
class ScreenFilters:
    sector: str | None = None
    industry: str | None = None
    exchange: str | None = None
    country: str | None = None
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_beta: float | None = None
    max_beta: float | None = None
    min_volume: float | None = None
    min_dividend: float | None = None
    limit: int = 50

    def to_fmp_params(self) -> dict[str, str | float | int]:
        mapping: dict[str, str | float | None] = {
            "sector": self.sector,
            "industry": self.industry,
            "exchange": self.exchange,
            "country": self.country,
            "marketCapMoreThan": self.min_market_cap,
            "marketCapLowerThan": self.max_market_cap,
            "priceMoreThan": self.min_price,
            "priceLowerThan": self.max_price,
            "betaMoreThan": self.min_beta,
            "betaLowerThan": self.max_beta,
            "volumeMoreThan": self.min_volume,
            "dividendMoreThan": self.min_dividend,
        }
        params: dict[str, str | float | int] = {
            k: v for k, v in mapping.items() if v is not None
        }
        params["limit"] = self.limit
        return params


@dataclass(frozen=True, slots=True)
class ScreenRow:
    symbol: str
    name: str | None
    sector: str | None
    industry: str | None
    market_cap: float | None
    price: float | None
    beta: float | None
    dividend: float | None
    exchange: str | None


@dataclass(frozen=True, slots=True)
class ScreenReport:
    filters: ScreenFilters
    rows: list[ScreenRow]


class ScreenUniverse:
    def __init__(self, fundamentals: FundamentalsRepository) -> None:
        self._fundamentals = fundamentals

    def run(self, filters: ScreenFilters) -> Result[ScreenReport, AnalysisError]:
        if filters.limit < 1 or filters.limit > 1000:
            return Err(InvalidInput("screen limit must be between 1 and 1000"))
        raw_result = self._fundamentals.screen(filters.to_fmp_params())
        if isinstance(raw_result, Err):
            return raw_result
        rows = []
        for record in raw_result.unwrap():
            symbol = record.get("symbol")
            if not symbol:
                continue
            rows.append(ScreenRow(
                symbol=str(symbol),
                name=record.get("companyName"),
                sector=record.get("sector"),
                industry=record.get("industry"),
                market_cap=_num(record.get("marketCap")),
                price=_num(record.get("price")),
                beta=_num(record.get("beta")),
                dividend=_num(record.get("lastAnnualDividend")),
                exchange=record.get("exchangeShortName") or record.get("exchange"),
            ))
        return Ok(ScreenReport(filters=filters, rows=rows))


def _num(value: object) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)
