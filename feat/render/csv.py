"""CSV renderer: emits each section's table, pipe-friendly."""

from __future__ import annotations

import csv
import io

from feat.render.base import Document


class CsvRenderer:
    def render(self, document: Document) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        for section in document.sections:
            if section.table is None:
                continue
            writer.writerow(["section", section.title])
            writer.writerow(section.table.headers)
            writer.writerows(section.table.rows)
        return buffer.getvalue()
