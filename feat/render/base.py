"""Renderer strategy interface and the Document model it consumes.

CLI commands map service reports into a ``Document`` (sections of
tables + a machine-readable payload); a ``Renderer`` turns that into
text. Adding an output format means adding a renderer, not touching
business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

#: Placeholder for missing values in human-readable output. Missing is
#: always shown as a gap, never rendered as zero.
GAP = "—"


@dataclass(frozen=True, slots=True)
class Table:
    headers: list[str]
    rows: list[list[str]]


@dataclass(frozen=True, slots=True)
class Section:
    title: str
    table: Table | None = None
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Document:
    title: str
    sections: list[Section]
    #: machine-readable payload for --json (and --csv key/value fallback)
    data: dict[str, Any]


class Renderer(Protocol):
    def render(self, document: Document) -> str: ...
