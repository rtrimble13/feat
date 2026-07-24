# Make DiskCache temp-file writes unique per writer (parallel-safe)

- **Lens:** Robustness (hidden bug)
- **Priority:** P2
- **Impact:** Medium
- **Effort:** Low
- **Confidence:** High
- **Severity:** Medium

## Problem

`feat/infra/cache.py:63-68`:

```python
def put(self, key: str, body: Any) -> None:
    envelope = {"stored_at": self._clock(), "key": key, "body": body}
    path = self._path(key)
    tmp = path.with_suffix(".tmp")          # -> "<sha256>.tmp", deterministic per key
    tmp.write_text(json.dumps(envelope), encoding="utf-8")
    tmp.replace(path)                        # atomic on POSIX
```

The temp filename is a deterministic `<digest>.tmp` derived only from the cache
key, so it is **shared across processes**. Two `feat` processes writing the same
cache key concurrently both target the same `.tmp` file.

## Why it matters

The README explicitly markets batch/pipe usage, and users will naturally
parallelize across symbols (e.g. `cat tickers.txt | xargs -P4 -n1 feat analyze`).
When two such processes fetch the *same* endpoint at once:

- process A `write_text`s the tmp, process B `write_text`s (truncating/rewriting
  the same file), then A calls `tmp.replace(path)` and B's `tmp.replace(path)`
  raises `FileNotFoundError` — surfacing as a generic unexpected error (exit 1);
  **or**
- a concurrent `get()` reads the tmp-then-replaced target mid-write on some
  filesystems, or a partial write is promoted, yielding `CacheCorruption`.

The single-process path (including the sequential stdin-batch the tests cover)
is fine — this only bites under real parallel invocation, which is why it's
Medium severity rather than High.

## Proposed change

Give each writer a unique temp file in the same directory, then atomically
replace onto the final path:

```python
import os, tempfile
fd, tmp_name = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh)
    os.replace(tmp_name, self._path(key))
except BaseException:
    os.unlink(tmp_name)  # don't leak temp files on failure
    raise
```

`os.replace` is still atomic; only the transient temp name changes, so two
writers no longer collide.

## Acceptance criteria

- Concurrent `put()` calls for the same key never raise `FileNotFoundError` and
  never leave a partially-written file at the final path.
- A test simulates two writers racing on the same key (e.g. two `put`s with
  interleaved temp creation) and asserts the final file is a complete, valid
  envelope; failed writes leave no stray `.tmp` files.
- Existing cache tests (TTL, corruption, path-traversal) still pass.

## Risk / blast radius

Confined to `DiskCache.put`. The atomicity guarantee the comment relies on is
preserved (`os.replace`). Watch for temp-file leakage on the error path — the
`try/except/unlink` above handles it. No cache-key or on-disk format change, so
existing cache entries remain valid.
