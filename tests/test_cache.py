import time

from agentfirst.cache import Cache, cache_key


def test_cache_key_stable_and_sorted():
    a = cache_key("w", "get", "/forecast", {"b": "1", "a": "2"})
    b = cache_key("w", "GET", "/forecast", {"a": "2", "b": "1"})
    c = cache_key("w", "get", "/forecast", {"b": "1", "a": "3"})
    assert a == b
    assert a != c


def test_cache_set_get_expire(tmp_path):
    cache = Cache(str(tmp_path / "c.db"))
    key = cache_key("w", "get", "/x", {})
    assert cache.get(key) is None
    cache.set(key, b"data", 60)
    assert cache.get(key) == b"data"
    cache.set(key, b"data2", 0)
    cache.close()


def test_cache_ttl_expiry(tmp_path):
    cache = Cache(str(tmp_path / "c.db"))
    key = cache_key("w", "get", "/x", {})
    cache.set(key, b"data", 1)
    time.sleep(1.1)
    assert cache.get(key) is None
    cache.close()


def test_cache_overwrite(tmp_path):
    cache = Cache(str(tmp_path / "c.db"))
    key = cache_key("w", "get", "/x", {})
    cache.set(key, b"old", 60)
    cache.set(key, b"new", 60)
    assert cache.get(key) == b"new"
    cache.close()
