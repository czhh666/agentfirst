import asyncio
import json

import httpx

from agentfirst.app import create_app

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
