# AgentFirst

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg)](requirements.txt)

A "de-humanized" proxy kernel for AI/Agent API calls. Sit between your Agent and any upstream REST API to automatically **slim responses**, **cache results**, **estimate costs**, and **accumulate optimization data**. Pure Python, zero LLM dependency.

English | [中文](README.zh-CN.md)

## Why

LLMs pay for every token. When an Agent calls an API, the response is usually designed for humans — huge JSON with dozens of fields the Agent never uses. AgentFirst strips the fat, caches repeated calls, and records usage for billing — typically cutting API-to-Agent token cost by 60-80%.

## Quick Start

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml

python -m agentfirst.app --config config.yaml install weather    # install a bundled API package
python -m agentfirst.app --config config.yaml serve
```

Call from your Agent:

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/weather/forecast?latitude=39.9&longitude=116.4&current=temperature_2m,relative_humidity_2m"
```

Response headers: `X-Cache: HIT|MISS`, `X-Slim: strict|safe|off`.

## Bundled API Packages

One-command installable packages (see [packages/README.md](packages/README.md)):

| Package | What | Cost | Measured slimming |
|---|---|---|---|
| `weather` | Weather (Open-Meteo) | free, no key | 82% |
| `geocoding` / `airquality` | Place→coords / air quality | free, no key | 47% / 66% |
| `exchange` / `geoip` | FX rates / IP geolocation | free, no key | 66% / 73% |
| `covid` / `zipcode` | COVID stats / postal codes | free, no key | 67% / 28% |
| `logistics` | Shipment tracking (TrackingMore) | free tier 100/mo | — |
| `business` | Company registry (Tianyancha) | paid | — |

```bash
python -m agentfirst.app --config config.yaml install logistics
```

## Control Plane

| Command | Description |
|---|---|
| `install <package>` | Install a bundled API package (spec + recommended slim config) |
| `import <spec> --id <api_id> [--base-url]` | Register any OpenAPI 3.x spec |
| `profile <api_id> [--top-k N]` | Generate include_fields from real usage stats and write back to config |
| `report <api_id>` | Call / cache-hit / cost report |
| `serve [--port 8000]` | Run the gateway |

HTTP endpoints: `GET /v1/estimate` (pre-call cost estimate), `GET /v1/schema/{api_id}` (slim config), `POST /v1/profile/{api_id}` (generate slim fields), `GET /v1/usage?user_id=` (billing).

## Configuration (config.yaml)

```yaml
apis:
  <api_id>:
    spec: specs/<api_id>.yaml      # OpenAPI 3.x file
    base_url: https://...          # upstream base URL (falls back to spec servers)
    auth_header: X-Api-Key         # upstream key injection (optional)
    auth_value: secret
    cache_ttl: 60                  # seconds; 0 = no caching
    cache_methods: [GET]           # cacheable methods
    slim_mode: strict              # strict|safe|off
    include_fields:                # STRICT whitelist (dot paths, list indices supported)
      - current.temperature_2m
    short_map:                     # response short-field mapping (optional)
      temperature_2m: t
users:
  sk-test: alice                   # API key -> user
pricing:
  miss: 0.0005                     # price per miss ($)
  hit: 0.00025                     # price per cache hit ($)
models:
  claude-sonnet-4-5: {input: 3.0, output: 15.0}   # $/1M tokens
```

## Slimming Modes

- `strict` — keep only `include_fields` whitelist (dot paths, supports list indices like `results.0.name`)
- `safe` — keep structure, drop nulls/empties
- `off` — pass through unchanged

On invalid JSON the gateway degrades to `off` automatically — it never corrupts data.

## Tests

```bash
python -m pytest tests -v
python scripts/demo_live.py             # live demo against open-meteo
python scripts/verify_free_packages.py  # verify all 7 free packages against real networks
```

Measured (open-meteo): STRICT slimming 434B → 78B (**82% savings**); second identical call returns `X-Cache: HIT` without hitting upstream.

## Spec

Design spec and acceptance criteria: [KERNEL_SPEC.md](KERNEL_SPEC.md) (Chinese).

## License

[Apache 2.0](LICENSE). Free to use, modify, and commercialize. Do not use the project name/logo to brand third-party services.
