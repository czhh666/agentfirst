import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from agentfirst.app import create_app
from agentfirst.config import load_config

BASE = "http://test"


async def main():
    config = load_config("config.yaml")
    app = create_app(config)
    headers = {"X-Api-Key": "sk-test"}
    params = {"latitude": 39.9, "longitude": 116.4, "current": "temperature_2m,relative_humidity_2m,apparent_temperature"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as ac:
        r_upstream = httpx.get("https://api.open-meteo.com/v1/forecast", params=params)
        raw_size = len(r_upstream.content)
        print(f"upstream direct: {raw_size} bytes")

        r1 = await ac.get("/v1/proxy/weather/forecast", params=params, headers=headers)
        slim_size = len(r1.content)
        print(f"request 1: status={r1.status_code} cache={r1.headers['X-Cache']} slim={r1.headers['X-Slim']} {slim_size} bytes")
        print(f"  slimmed body: {r1.json()}")

        r2 = await ac.get("/v1/proxy/weather/forecast", params=params, headers=headers)
        print(f"request 2: status={r2.status_code} cache={r2.headers['X-Cache']} slim={r2.headers['X-Slim']} {len(r2.content)} bytes")

        est = await ac.get("/v1/estimate", params={
            "api_id": "weather", "method": "GET", "path": "/forecast",
            "params": json.dumps(params), "model": "claude-sonnet-4-5",
        })
        print(f"estimate: {est.json()}")

        profile = await ac.post("/v1/profile/weather", params={"top_k": 10})
        print(f"generated profile fields: {profile.json()['generated_include_fields']}")

        usage = (await ac.get("/v1/usage", params={"user_id": "alice"})).json()
        print(f"usage: {usage}")

        print(f"\nRESULT: slim savings = {100 * (1 - slim_size / raw_size):.1f}% (target >= 50%)")


if __name__ == "__main__":
    asyncio.run(main())
