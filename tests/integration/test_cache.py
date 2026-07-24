"""Disk cache: TTL policy, corruption handling, key hashing."""

import threading

import pytest

from feat.infra.cache import CacheCorruption, DiskCache


def test_roundtrip_within_ttl(tmp_path):
    clock = [1000.0]
    cache = DiskCache(tmp_path, clock=lambda: clock[0])
    cache.put("profile|symbol=TEST", {"a": 1})
    assert cache.get("profile|symbol=TEST", ttl_seconds=60) == {"a": 1}


def test_expired_entry_is_a_miss(tmp_path):
    clock = [1000.0]
    cache = DiskCache(tmp_path, clock=lambda: clock[0])
    cache.put("k", {"a": 1})
    clock[0] += 3600
    assert cache.get("k", ttl_seconds=60) is None


def test_none_ttl_serves_any_age(tmp_path):
    clock = [1000.0]
    cache = DiskCache(tmp_path, clock=lambda: clock[0])
    cache.put("k", {"a": 1})
    clock[0] += 10 * 365 * 24 * 3600
    assert cache.get("k", ttl_seconds=None) == {"a": 1}


def test_corrupt_file_fails_loudly(tmp_path):
    cache = DiskCache(tmp_path)
    cache.put("k", {"a": 1})
    victim = next(tmp_path.glob("*.json"))
    victim.write_text("{not json")
    with pytest.raises(CacheCorruption, match="delete the file"):
        cache.get("k", ttl_seconds=60)


def test_keys_never_become_path_components(tmp_path):
    cache = DiskCache(tmp_path)
    cache.put("../../etc/passwd|sneaky", {"a": 1})
    # everything stays inside the cache dir as a hashed filename
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    assert files[0].parent == tmp_path
    assert files[0].suffix == ".json"


def test_concurrent_writers_to_same_key_do_not_collide(tmp_path):
    # Simulates parallel `feat` processes fetching the same endpoint at once
    # (e.g. `xargs -P4 feat analyze`). With a shared "<key>.tmp" name the racing
    # replace() would raise FileNotFoundError or leave a corrupt file; with a
    # per-writer temp file it never does.
    cache = DiskCache(tmp_path)
    errors: list[BaseException] = []

    def hammer(worker: int) -> None:
        try:
            for _ in range(50):
                cache.put("same-key", {"worker": worker})
        except BaseException as exc:  # record and assert in the test thread
            errors.append(exc)

    workers = [threading.Thread(target=hammer, args=(i,)) for i in range(8)]
    for t in workers:
        t.start()
    for t in workers:
        t.join()

    assert errors == []                                   # no racing replace() failures
    assert cache.get("same-key", ttl_seconds=None) in [{"worker": i} for i in range(8)]
    assert list(tmp_path.glob("*.tmp")) == []             # no leaked temp files
