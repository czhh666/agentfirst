import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from agentfirst.app import create_app
from agentfirst.config import load_config

BASE = "http://test"
CASES = [
    ("exchange", "GET", "/latest", {"base": "USD"}),
    ("geoip", "GET", "/8.8.8.8/json/", {}),
    ("geocoding", "GET", "/search", {"name": "beijing", "count": 1}),
    ("airquality", "GET", "/air-quality", {"latitude": 39.9, "longitude": 116.4, "current": "pm10,pm2_5"}),
    ("covid", "GET", "/countries/CN", {}),
    ("zipcode", "GET", "/us/90210", {}),
]


async def main():
    config = load_config("_verify.yaml")
    app = create_app(config)
    headers = {"X-Api-Key": "sk-test"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=BASE) as ac:
        for api_id, method, path, params in CASES:
            raw_url = ""
            if api_id == "exchange":
                raw_url = "https://api.frankfurter.app/latest?base=USD"
            elif api_id == "geoip":
                raw_url = "https://ipapi.co/8.8.8.8/json/"
            elif api_id == "geocoding":
                raw_url = "https://geocoding-api.open-meteo.com/v1/search?name=beijing&count=1"
            elif api_id == "airquality":
                raw_url = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=39.9&longitude=116.4&current=pm10,pm2_5"
            elif api_id == "covid":
                raw_url = "https://disease.sh/v3/covid-19/countries/CN"
            elif api_id == "zipcode":
                raw_url = "https://api.zippopotam.us/us/90210"
            raw = httpx.get(raw_url, timeout=15, follow_redirects=True)
            r1 = await ac.request(method, f"/v1/proxy/{api_id}{path}", params=params, headers=headers)
            r2 = await ac.request(method, f"/v1/proxy/{api_id}{path}", params=params, headers=headers)
            savings = 100 * (1 - len(r1.content) / len(raw.content))
            print(f"{api_id}: raw={len(raw.content)}B slim={len(r1.content)}B savings={savings:.0f}% "
                  f"cache={r1.headers.get('X-Cache')}->{r2.headers.get('X-Cache')} "
                  f"mode={r1.headers.get('X-Slim')} status={r1.status_code} body={r1.text[:90]}")
            assert r1.status_code == 200, f"{api_id} status {r1.status_code}"
            assert r2.headers["X-Cache"] == "HIT", f"{api_id} cache miss on 2nd call"
            assert r1.json() == r2.json(), f"{api_id} cache content mismatch"


asyncio.run(main())
print("ALL FREE PACKAGES VERIFIED OK")
