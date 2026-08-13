import asyncio
import json

import httpx
import pytest
import yaml

from agentfirst.app import create_app
from agentfirst.config import ApiConfig, Config


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


def _config_with_async(tmp_path, async_poll):
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(
        yaml.safe_dump({
            "openapi": "3.0.0",
            "servers": [{"url": "https://upstream.test/v1/"}],
            "paths": {
                "/submit": {"post": {"operationId": "submitJob"}},
            },
        }, allow_unicode=True),
        encoding="utf-8",
    )
    return Config(
        db_path=str(tmp_path / "test.db"),
        users={"sk-test": "alice"},
        models={"claude-sonnet-4-5": {"input": 3.0, "output": 15.0}},
        pricing={"miss": 0.0005, "hit": 0.00025},
        apis={"jobs": ApiConfig(
            api_id="jobs", spec_path=str(spec_file),
            base_url="https://upstream.test/v1/",
            cache_ttl=0, slim_mode="safe", async_poll=async_poll,
        )},
    )


def _run(app, method, path, headers=None, params=None, body=None):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            return await ac.request(method, path, headers=headers, params=params or {}, content=body)
    return asyncio.run(scenario())


def test_async_poll_wraps_submit_until_done(tmp_path):
    status_calls = []

    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"task_id": "t1"})
        if request.method == "GET":
            status_calls.append(1)
            if len(status_calls) < 3:
                return httpx.Response(200, json={"status": "running"})
            return httpx.Response(200, json={"status": "completed", "result": "done"})
        return httpx.Response(404)

    transport = _make_transport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    cfg = _config_with_async(tmp_path, {
        "submit_path": "/submit",
        "status_path": "/status/{task_id}",
        "task_id_field": "task_id",
        "done_field": "status",
        "done_values": ["completed", "failed"],
        "interval": 0.01,
        "max_wait": 5,
    })
    app = create_app(cfg, client=upstream)

    r = _run(app, "POST", "/v1/proxy/jobs/submit", headers={"X-Api-Key": "sk-test"})

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed", "must wait for terminal status"
    assert data["result"] == "done"
    assert len(status_calls) == 3, f"expected 3 status polls, got {len(status_calls)}"
    asyncio.run(upstream.aclose())


def test_async_poll_times_out_returns_last_status(tmp_path):
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"task_id": "t1"})
        if request.method == "GET":
            return httpx.Response(200, json={"status": "running"})
        return httpx.Response(404)

    transport = _make_transport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    cfg = _config_with_async(tmp_path, {
        "submit_path": "/submit",
        "status_path": "/status/{task_id}",
        "task_id_field": "task_id",
        "done_field": "status",
        "done_values": ["completed"],
        "interval": 0.01,
        "max_wait": 0.05,
    })
    app = create_app(cfg, client=upstream)

    r = _run(app, "POST", "/v1/proxy/jobs/submit", headers={"X-Api-Key": "sk-test"})

    assert r.status_code == 200
    assert r.json()["status"] == "running", "timeout must return the last observed status"
    asyncio.run(upstream.aclose())


def test_no_async_poll_config_is_passthrough(tmp_path):
    def handler(request):
        return httpx.Response(200, json={"task_id": "t1"})

    transport = _make_transport(handler)
    upstream = httpx.AsyncClient(transport=transport)
    cfg = _config_with_async(tmp_path, {})
    app = create_app(cfg, client=upstream)

    r = _run(app, "POST", "/v1/proxy/jobs/submit", headers={"X-Api-Key": "sk-test"})

    assert r.status_code == 200
    assert r.json() == {"task_id": "t1"}, "empty async_poll = normal passthrough"
    asyncio.run(upstream.aclose())
