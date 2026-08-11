import json
import sys
from pathlib import Path

import httpx
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentfirst.config import ApiConfig, Config

SPEC_PATHS = {
    "forecast": {
        "get": {
            "operationId": "getForecast",
            "parameters": [
                {"name": "latitude", "in": "query", "required": True},
                {"name": "longitude", "in": "query", "required": True},
            ],
        }
    },
    "/items/{id}": {
        "get": {"operationId": "getItem"},
    },
}

FULL_RESPONSE = {
    "current": {
        "temperature_2m": 22.5,
        "relative_humidity_2m": 60,
        "apparent_temperature": 22.1,
        "weather_code": 2,
        "wind_speed_10m": 5.1,
    },
    "current_units": {
        "temperature_2m": "°C",
        "apparent_temperature": "°C",
        "weather_code": "wmo",
        "wind_speed_10m": "km/h",
    },
    "timezone": "GMT",
    "utc_offset_seconds": 0,
    "huge": "x" * 2000,
}

INCLUDE = ["current.temperature_2m", "current.relative_humidity_2m", "current_units.temperature_2m"]
SHORT_MAP = {"temperature_2m": "t", "relative_humidity_2m": "h", "current_units": "u"}


@pytest.fixture
def full_response_bytes():
    return json.dumps(FULL_RESPONSE).encode()


@pytest.fixture
def config(tmp_path):
    spec_file = tmp_path / "weather.yaml"
    spec_file.write_text(
        yaml.safe_dump({
            "openapi": "3.0.0",
            "servers": [{"url": "https://upstream.test/v1/"}],
            "paths": SPEC_PATHS,
        }, allow_unicode=True),
        encoding="utf-8",
    )
    return Config(
        db_path=str(tmp_path / "test.db"),
        users={"sk-test": "alice"},
        models={"claude-sonnet-4-5": {"input": 3.0, "output": 15.0}},
        pricing={"miss": 0.0005, "hit": 0.00025},
        apis={
            "weather": ApiConfig(
                api_id="weather",
                spec_path=str(spec_file),
                base_url="https://upstream.test/v1/",
                cache_ttl=60,
                cache_methods=("GET",),
                slim_mode="strict",
                include_fields=list(INCLUDE),
                short_map=dict(SHORT_MAP),
            )
        },
    )


@pytest.fixture
def mock_transport():
    counter = {"calls": 0}

    async def handler(request: httpx.Request):
        counter["calls"] += 1
        return httpx.Response(200, json=FULL_RESPONSE)

    transport = httpx.MockTransport(handler)
    transport.counter = counter
    return transport
