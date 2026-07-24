"""Vetted FMP endpoint templates.

SSRF defense: outbound URLs are built *only* from these templates against
the known FMP hosts below — never from response bodies or user free-text.
Path parameters are validated domain values (e.g. Ticker) interpolated
into fixed templates.

Cache TTLs are per endpoint: annual statements change quarterly (long
TTL); quotes are short-lived.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

FMP_HOST = "https://financialmodelingprep.com"


class ApiBase(Enum):
    V3 = "/api/v3"
    V4 = "/api/v4"
    STABLE = "/stable"


_HOUR = 3600
_DAY = 24 * _HOUR


@dataclass(frozen=True, slots=True)
class Endpoint:
    name: str
    base: ApiBase
    path_template: str  # e.g. "/profile/{symbol}"
    cache_ttl_seconds: int

    def url(self, **path_params: str) -> str:
        path = self.path_template.format(**path_params)
        return f"{FMP_HOST}{self.base.value}{path}"


PROFILE = Endpoint("profile", ApiBase.V3, "/profile/{symbol}", _DAY)
INCOME_STATEMENT = Endpoint("income_statement", ApiBase.V3, "/income-statement/{symbol}", 7 * _DAY)
BALANCE_SHEET = Endpoint(
    "balance_sheet", ApiBase.V3, "/balance-sheet-statement/{symbol}", 7 * _DAY
)
CASH_FLOW = Endpoint("cash_flow", ApiBase.V3, "/cash-flow-statement/{symbol}", 7 * _DAY)
DCF_REFERENCE = Endpoint("dcf_reference", ApiBase.V3, "/discounted-cash-flow/{symbol}", _DAY)
STOCK_PEERS = Endpoint("stock_peers", ApiBase.V4, "/stock_peers", 7 * _DAY)
SCREENER = Endpoint("screener", ApiBase.STABLE, "/company-screener", _HOUR)
