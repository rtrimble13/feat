"""JSON renderer: the machine-readable payload, stable keys, to stdout."""

from __future__ import annotations

import json

from feat.render.base import Document


class JsonRenderer:
    def render(self, document: Document) -> str:
        return json.dumps(document.data, indent=2, sort_keys=True, default=str) + "\n"
