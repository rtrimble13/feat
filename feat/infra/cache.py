"""Disk cache with per-endpoint TTL and snapshot support.

Design notes (cache invalidation is a designed policy here, not an
accident):

- The cache key includes endpoint, symbol, period and params; the TTL is
  supplied per lookup from the endpoint definition.
- Entries are JSON envelopes ``{"stored_at": epoch, "body": ...}`` under
  a directory confined at construction; keys are hashed so no external
  string ever becomes a path component (path-traversal defense).
- A malformed cache file raises ``CacheCorruption`` — corrupt state is a
  loud failure, not a silent miss.
- ``ttl_seconds=None`` serves entries regardless of age (offline /
  snapshot replay).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable


class CacheCorruption(Exception):
    """A cache file exists but cannot be parsed/validated."""


class DiskCache:
    def __init__(
        self,
        directory: Path,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._clock = clock

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._dir / f"{digest}.json"

    def get(self, key: str, ttl_seconds: int | None) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            stored_at = envelope["stored_at"]
            body = envelope["body"]
            if not isinstance(stored_at, (int, float)):
                raise TypeError("stored_at must be numeric")
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise CacheCorruption(
                f"corrupt cache entry {path.name} for key {key!r}: {exc}; "
                f"delete the file (or the cache directory) to recover"
            ) from exc
        if ttl_seconds is not None and self._clock() - stored_at > ttl_seconds:
            return None
        return body

    def put(self, key: str, body: Any) -> None:
        envelope = {"stored_at": self._clock(), "key": key, "body": body}
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(envelope), encoding="utf-8")
        tmp.replace(path)  # atomic on POSIX: readers never see a partial file
