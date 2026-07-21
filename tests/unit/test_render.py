"""Renderers and sparklines: format-only behavior."""

import csv
import io
import json

from feat.render.base import Document, Section, Table
from feat.render.csv import CsvRenderer
from feat.render.json import JsonRenderer
from feat.render.sparkline import sparkline
from feat.render.table import TableRenderer


def document() -> Document:
    return Document(
        title="feat test",
        sections=[Section(
            title="Metrics",
            table=Table(headers=["Metric", "FY2024"], rows=[["ROIC", "28.6%"]]),
            lines=["note: missing shown as —"],
        )],
        data={"roic": 0.286, "missing": None},
    )


class TestSparkline:
    def test_monotone_series(self):
        line = sparkline([1.0, 2.0, 3.0, 4.0])
        assert line[0] == "▁" and line[-1] == "█"

    def test_missing_points_render_as_gap(self):
        assert sparkline([1.0, None, 3.0]) == "▁·█"

    def test_all_missing(self):
        assert sparkline([None, None]) == "··"

    def test_flat_series_mid_block(self):
        assert sparkline([5.0, 5.0]) == "▄▄"


class TestRenderers:
    def test_json_is_parseable_and_preserves_null(self):
        payload = json.loads(JsonRenderer().render(document()))
        assert payload["roic"] == 0.286
        assert payload["missing"] is None

    def test_csv_round_trips(self):
        rows = list(csv.reader(io.StringIO(CsvRenderer().render(document()))))
        assert ["Metric", "FY2024"] in rows
        assert ["ROIC", "28.6%"] in rows

    def test_table_contains_data_and_no_color_when_disabled(self):
        text = TableRenderer(color=False).render(document())
        assert "ROIC" in text and "28.6%" in text
        assert "\033[" not in text

    def test_table_color_toggle(self):
        text = TableRenderer(color=True).render(document())
        assert "\033[1m" in text
