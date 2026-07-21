"""Value objects: small, immutable, self-validating types.

The goal is to make invalid states unrepresentable ("parse, don't
validate"): a ``Ticker`` cannot hold shell metacharacters, ``Money``
refuses to mix currencies, ``Percent`` cannot be confused between
0.15 and 15.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Union


class MissingType:
    """Sentinel for a value the data source did not report.

    A gap must stay *visible* downstream — it is never coerced to zero,
    because a silent zero corrupts every ratio and model built on it.
    """

    _instance: "MissingType | None" = None

    def __new__(cls) -> "MissingType":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "MISSING"

    def __bool__(self) -> bool:
        return False


MISSING = MissingType()


def is_missing(value: object) -> bool:
    """True when *value* is the MISSING sentinel or ``None``."""
    return value is None or isinstance(value, MissingType)


_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")


@dataclass(frozen=True, slots=True)
class Ticker:
    """An exchange ticker symbol, uppercased and format-validated.

    Constrained so it can never smuggle shell, path or URL payloads.
    """

    symbol: str

    def __post_init__(self) -> None:
        normalized = self.symbol.strip().upper()
        if not _TICKER_RE.match(normalized):
            raise ValueError(
                f"invalid ticker {self.symbol!r}: expected 1-12 chars of "
                "A-Z, 0-9, '.' or '-'"
            )
        object.__setattr__(self, "symbol", normalized)

    def __str__(self) -> str:
        return self.symbol


@dataclass(frozen=True, slots=True)
class Money:
    """An amount in a specific currency.

    Arithmetic refuses to mix currencies without explicit FX conversion.
    """

    amount: float
    currency: str = "USD"

    def __post_init__(self) -> None:
        if not isinstance(self.amount, (int, float)) or isinstance(self.amount, bool):
            raise TypeError(f"Money amount must be numeric, got {type(self.amount).__name__}")
        if not self.currency or not self.currency.isalpha() or len(self.currency) != 3:
            raise ValueError(f"invalid currency code {self.currency!r}")
        object.__setattr__(self, "amount", float(self.amount))
        object.__setattr__(self, "currency", self.currency.upper())

    def _check(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"cannot mix currencies {self.currency} and {other.currency} "
                "without explicit FX conversion"
            )

    def __add__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, scalar: float) -> "Money":
        return Money(self.amount * scalar, self.currency)

    __rmul__ = __mul__

    def __truediv__(self, divisor: Union[float, "Money"]) -> Union["Money", float]:
        if isinstance(divisor, Money):
            self._check(divisor)
            if divisor.amount == 0:
                raise ZeroDivisionError("division by zero Money")
            return self.amount / divisor.amount
        if divisor == 0:
            raise ZeroDivisionError("division by zero")
        return Money(self.amount / divisor, self.currency)

    def __neg__(self) -> "Money":
        return Money(-self.amount, self.currency)

    def __str__(self) -> str:
        return f"{self.amount:,.2f} {self.currency}"


MoneyLike = Union[Money, MissingType]


@dataclass(frozen=True, slots=True)
class Percent:
    """A rate stored unambiguously as a *fraction* (0.15 == 15%).

    Construct via :meth:`from_fraction` or :meth:`from_percent` to avoid
    the classic 0.15-vs-15 confusion.
    """

    fraction: float

    @classmethod
    def from_fraction(cls, fraction: float) -> "Percent":
        return cls(float(fraction))

    @classmethod
    def from_percent(cls, percent: float) -> "Percent":
        return cls(float(percent) / 100.0)

    @property
    def as_percent(self) -> float:
        return self.fraction * 100.0

    def __str__(self) -> str:
        return f"{self.as_percent:.2f}%"


@dataclass(frozen=True, slots=True)
class Ratio:
    """A dimensionless ratio (e.g. current ratio of 1.8x)."""

    value: float

    def __str__(self) -> str:
        return f"{self.value:.2f}x"


class PeriodType(Enum):
    ANNUAL = "annual"
    QUARTER = "quarter"


@dataclass(frozen=True, slots=True)
class FiscalPeriod:
    """A fiscal reporting period: fiscal year, type and period end date.

    Off-cycle year-ends (e.g. AAPL's September FY) are handled by keeping
    the reported end date; calendarization keys off ``end_date``.
    """

    fiscal_year: int
    period_type: PeriodType
    end_date: date
    quarter: int | None = None  # 1-4 when period_type is QUARTER

    def __post_init__(self) -> None:
        if self.fiscal_year < 1900 or self.fiscal_year > 2200:
            raise ValueError(f"implausible fiscal year {self.fiscal_year}")
        if self.period_type is PeriodType.QUARTER:
            if self.quarter not in (1, 2, 3, 4):
                raise ValueError("quarterly period requires quarter in 1-4")
        elif self.quarter is not None:
            raise ValueError("annual period must not carry a quarter number")

    @property
    def calendar_year(self) -> int:
        return self.end_date.year

    def label(self) -> str:
        if self.period_type is PeriodType.ANNUAL:
            return f"FY{self.fiscal_year}"
        return f"{self.fiscal_year}Q{self.quarter}"


class ShareBasis(Enum):
    BASIC = "basic"
    DILUTED = "diluted"


@dataclass(frozen=True, slots=True)
class ShareCount:
    """A number of shares, with basic vs diluted distinguished by type."""

    count: float
    basis: ShareBasis

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError(f"share count cannot be negative: {self.count}")

    def __str__(self) -> str:
        return f"{self.count:,.0f} ({self.basis.value})"


def amount_of(value: MoneyLike | None) -> float | None:
    """Extract a raw float from a possibly-missing Money, or ``None``.

    The single bridge between typed entity fields and the pure numeric
    math in ratio/valuation modules. Missing stays ``None`` — never 0.
    """
    if is_missing(value):
        return None
    assert isinstance(value, Money)
    return value.amount
