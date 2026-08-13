import asyncio
import json

import httpx
import pytest
import yaml

from agentfirst.app import create_app
from agentfirst.config import ApiConfig, Config

import conftest


def _make_transport(handler):
    counter = {"calls": 0}

    async def wrapped(request: httpx.Request):
        counter["calls"] += 1
        result = handler(request)
        if asyncio.iscoroutine(result):
            return await result
        return result

    transport = httpx.MockTransport(wrapped)
    transport.counter = counter
    return transport


def _run(app, method, path, headers=None, params=None):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            return await ac.request(method, path, headers=headers, params=params or {})
    return asyncio.run(scenario())


def test_retry_transient_503_succeeds(config):
    calls = []

    async def flaky(request):
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json=conftest.FULL_RESPONSE)

    transport = _make_transport(flaky)
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(config, client=upstream)

    r = _run(app, "GET", "/v1/proxy/weather/forecast",
             headers={"X-Api-Key": "sk-test"}, params={"latitude": 1, "longitude": 2})

    assert r.status_code == 200
    assert len(calls) == 3, f"expected 3 upstream attempts, got {len(calls)}"
    asyncio.run(upstream.aclose())


def test_retry_gives_up_after_final_attempt(config):
    calls = []

    async def always_503(request):
        calls.append(1)
        return httpx.Response(503, text="busy")

    transport = _make_transport(always_503)
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(config, client=upstream)

    r = _run(app, "GET", "/v1/proxy/weather/forecast",
             headers={"X-Api-Key": "sk-test"}, params={"latitude": 1, "longitude": 2})

    assert r.status_code == 503
    assert len(calls) == 3
    asyncio.run(upstream.aclose())


def test_skip_cache_header_bypasses_cache(config):
    transport = _make_transport(lambda req: httpx.Response(200, json=conftest.FULL_RESPONSE))
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(config, client=upstream)

    h = {"X-Api-Key": "sk-test", "X-Skip-Cache": "true"}
    r1 = _run(app, "GET", "/v1/proxy/weather/forecast", headers=h, params={"latitude": 1, "longitude": 2})
    r2 = _run(app, "GET", "/v1/proxy/weather/forecast", headers=h, params={"latitude": 1, "longitude": 2})

    assert r1.headers["X-Cache"] == "MISS"
    assert r2.headers["X-Cache"] == "MISS"
    assert transport.counter["calls"] == 2, "X-Skip-Cache must bypass cache reads AND writes"
    asyncio.run(upstream.aclose())


def test_force_slim_header_overrides_mode(config):
    transport = _make_transport(lambda req: httpx.Response(200, json=conftest.FULL_RESPONSE))
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(config, client=upstream)

    r = _run(app, "GET", "/v1/proxy/weather/forecast",
             headers={"X-Api-Key": "sk-test", "X-Force-Slim": "safe"},
             params={"latitude": 1, "longitude": 2})

    assert r.headers["X-Slim"] == "safe"
    data = r.json()
    renamed = dict(conftest.FULL_RESPONSE)
    renamed["u"] = renamed.pop("current_units")
    assert set(data.keys()) == set(renamed.keys()), "safe mode keeps full structure (short_map still applies)"
    asyncio.run(upstream.aclose())


def test_cache_ttl_header_overrides_ttl(config):
    transport = _make_transport(lambda req: httpx.Response(200, json=conftest.FULL_RESPONSE))
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(config, client=upstream)

    h = {"X-Api-Key": "sk-test", "X-Cache-TTL": "0"}
    r1 = _run(app, "GET", "/v1/proxy/weather/forecast", headers=h, params={"latitude": 1, "longitude": 2})
    r2 = _run(app, "GET", "/v1/proxy/weather/forecast", headers=h, params={"latitude": 1, "longitude": 2})

    assert r2.headers["X-Cache"] == "MISS", "X-Cache-TTL: 0 must disable caching for this request"
    assert transport.counter["calls"] == 2
    asyncio.run(upstream.aclose())


def _config_with_post(tmp_path):
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(
        yaml.safe_dump({
            "openapi": "3.0.0",
            "servers": [{"url": "https://upstream.test/v1/"}],
            "paths": {
                "/orders": {"post": {"operationId": "createOrder"}},
                "/forecast": {"get": {"operationId": "getForecast"}},
            },
        }, allow_unicode=True),
        encoding="utf-8",
    )
    return Config(
        db_path=str(tmp_path / "test.db"),
        users={"sk-test": "alice"},
        models={"claude-sonnet-4-5": {"input": 3.0, "output": 15.0}},
        pricing={"miss": 0.0005, "hit": 0.00025},
        apis={"weather": ApiConfig(
            api_id="weather", spec_path=str(spec_file),
            base_url="https://upstream.test/v1/",
            cache_ttl=60, cache_methods=("GET",), slim_mode="safe",
        )},
    )


def test_idempotency_key_replays_without_duplicate_call(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"order_id": 123})

    transport = _make_transport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(_config_with_post(tmp_path), client=upstream)

    h = {"X-Api-Key": "sk-test", "Idempotency-Key": "abc-123"}
    r1 = _run(app, "POST", "/v1/proxy/weather/orders", headers=h)
    r2 = _run(app, "POST", "/v1/proxy/weather/orders", headers=h)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.headers.get("X-Idempotent-Replay") == "true"
    assert len(calls) == 1, f"upstream called {len(calls)} times, expected once"
    assert r1.content == r2.content

    r3 = _run(app, "POST", "/v1/proxy/weather/orders",
              headers={"X-Api-Key": "sk-test", "Idempotency-Key": "xyz-456"})
    assert len(calls) == 2, "different idempotency key must trigger a new call"
    assert "X-Idempotent-Replay" not in r3.headers

    asyncio.run(upstream.aclose())


def test_idempotency_without_key_does_not_dedupe(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(200, json={"order_id": 123})

    transport = _make_transport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    app = create_app(_config_with_post(tmp_path), client=upstream)

    h = {"X-Api-Key": "sk-test"}
    _run(app, "POST", "/v1/proxy/weather/orders", headers=h)
    _run(app, "POST", "/v1/proxy/weather/orders", headers=h)

    assert len(calls) == 2, "no idempotency key = no dedup, each POST hits upstream"

    asyncio.run(upstream.aclose())
