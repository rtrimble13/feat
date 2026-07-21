"""Human-readable table renderer (tabulate), with optional ANSI color."""

from __future__ import annotations

from tabulate import tabulate

from feat.render.base import Document

_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


class TableRenderer:
    def __init__(self, color: bool = True) -> None:
        self._color = color

    def _bold(self, text: str) -> str:
        return f"{_BOLD}{text}{_RESET}" if self._color else text

    def _dim(self, text: str) -> str:
        return f"{_DIM}{text}{_RESET}" if self._color else text

    def render(self, document: Document) -> str:
        out: list[str] = [self._bold(document.title), ""]
        for section in document.sections:
            out.append(self._bold(f"── {section.title} " + "─" * max(0, 50 - len(section.title))))
            if section.table is not None:
                out.append(tabulate(
                    section.table.rows,
                    headers=section.table.headers,
                    tablefmt="simple",
                    disable_numparse=True,
                ))
            for line in section.lines:
                out.append(self._dim(line) if line.startswith("note:") else line)
            out.append("")
        return "\n".join(out).rstrip() + "\n"
