import asyncio
import json

import httpx

from agentfirst.app import create_app

import conftest


def test_e2e_proxy_cache_slim_billing_estimate_profile(config, mock_transport):
    upstream_client = httpx.AsyncClient(transport=mock_transport)
    app = create_app(config, client=upstream_client)
    raw_size = len(json.dumps(conftest.FULL_RESPONSE, ensure_ascii=False).encode("utf-8"))

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
            headers = {"X-Api-Key": "sk-test"}
            params = {"latitude": 1, "longitude": 2}

            r401 = await ac.get("/v1/proxy/weather/forecast", params=params)
            assert r401.status_code == 401

            r1 = await ac.get("/v1/proxy/weather/forecast", params=params, headers=headers)
            assert r1.status_code == 200
            assert r1.headers["X-Cache"] == "MISS"
            assert r1.headers["X-Slim"] == "strict"
            assert mock_transport.counter["calls"] == 1
            data1 = r1.json()
            assert set(data1.keys()) == {"current", "u"}
            assert "t" in data1["u"] and "t" in data1["current"]
            assert len(r1.content) * 2 < raw_size

            r2 = await ac.get("/v1/proxy/weather/forecast", params=params, headers=headers)
            assert r2.status_code == 200
            assert r2.headers["X-Cache"] == "HIT"
            assert mock_transport.counter["calls"] == 1
            assert r2.json() == data1

            r404 = await ac.get("/v1/proxy/weather/nope", headers=headers)
            assert r404.status_code == 404

            usage = (await ac.get("/v1/usage", params={"user_id": "alice"})).json()
            assert usage["total_calls"] == 2
            assert usage["total_cost_usd"] == 0.00075

            est = (await ac.get("/v1/estimate", params={
                "api_id": "weather", "method": "GET", "path": "/forecast",
                "params": json.dumps({"latitude": 1, "longitude": 2}),
                "model": "claude-sonnet-4-5",
            })).json()
            assert est["estimated_tokens"] > 0
            assert est["slim_mode"] == "strict"

            schema = (await ac.get("/v1/schema/weather")).json()
            assert schema["include_fields"] == [
                "current.temperature_2m", "current.relative_humidity_2m", "current_units.temperature_2m"]

            profile = (await ac.post("/v1/profile/weather")).json()
            assert "generated_include_fields" in profile
            assert len(profile["generated_include_fields"]) > 0

        await upstream_client.aclose()

    asyncio.run(scenario())
