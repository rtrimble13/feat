"""Structured logging: key/value lines, correlation id, secret redaction.

Levels: ERROR needs attention; WARN recoverable (a retried 429); INFO
business events; DEBUG development detail. Secrets and full response
bodies are never logged — the client logs endpoint *names*, not URLs.
"""

from __future__ import annotations

import logging
import re
import sys
import uuid

_APIKEY_RE = re.compile(r"apikey=[^&\s]+", re.IGNORECASE)

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


class _KeyValueFormatter(logging.Formatter):
    """`level=INFO run=abc123 msg="valued AAPL" fair_value=182.4` style."""

    def __init__(self, correlation_id: str) -> None:
        super().__init__()
        self._cid = correlation_id

    def format(self, record: logging.LogRecord) -> str:
        message = _APIKEY_RE.sub("apikey=[REDACTED]", record.getMessage())
        parts = [
            f"level={record.levelname}",
            f"run={self._cid}",
            f"logger={record.name}",
            f'msg="{message}"',
        ]
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            parts.append(f"{key}={_APIKEY_RE.sub('[REDACTED]', str(value))}")
        if record.exc_info:
            parts.append(f'exc="{self.formatException(record.exc_info)}"')
        return " ".join(parts)


def setup_logging(verbose: bool = False) -> str:
    """Configure the root 'feat' logger; returns the correlation id that
    ties all lines of this invocation together."""
    correlation_id = uuid.uuid4().hex[:12]
    logger = logging.getLogger("feat")
    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_KeyValueFormatter(correlation_id))
    logger.addHandler(handler)
    logger.propagate = False
    return correlation_id
