"""Expected failures as return values: the Result type and AnalysisError.

Not-found, insufficient-data and rate-limited are *expected* outcomes of
talking to a market-data vendor; they are returned, mapped to specific
CLI messages and exit codes. Truly unexpected errors (bugs, corrupt
state) raise and fail loudly — they are never caught-and-continued.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self.value


@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        raise RuntimeError(f"unwrap() on Err: {self.error}")


Result = Union[Ok[T], Err[E]]


@dataclass(frozen=True)
class AnalysisError:
    """Base class for expected analysis failures."""

    message: str

    #: CLI exit code for this error class (0 = success, 1 = unexpected).
    exit_code: int = field(default=1, init=False)


@dataclass(frozen=True)
class SymbolNotFound(AnalysisError):
    exit_code: int = field(default=3, init=False)


@dataclass(frozen=True)
class InsufficientHistory(AnalysisError):
    exit_code: int = field(default=4, init=False)


@dataclass(frozen=True)
class MissingRequiredField(AnalysisError):
    exit_code: int = field(default=4, init=False)


@dataclass(frozen=True)
class RateLimited(AnalysisError):
    exit_code: int = field(default=5, init=False)


@dataclass(frozen=True)
class UpstreamUnavailable(AnalysisError):
    exit_code: int = field(default=6, init=False)


@dataclass(frozen=True)
class InvalidInput(AnalysisError):
    exit_code: int = field(default=2, init=False)


@dataclass(frozen=True)
class ConfigError(AnalysisError):
    exit_code: int = field(default=7, init=False)
