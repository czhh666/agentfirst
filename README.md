# AgentFirst — cut 60-80% of the tokens your Agent spends on API calls

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](requirements.txt)
[![CI](https://github.com/czhh666/agentfirst/actions/workflows/ci.yml/badge.svg)](https://github.com/czhh666/agentfirst/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/czhh666/agentfirst?style=social)](https://github.com/czhh666/agentfirst)

**A "de-humanized" proxy kernel for LLM/Agent API calls** — automatically slims responses, caches results, estimates costs, and records billing. Pure Python, zero LLM dependency. Plug in any OpenAPI 3.x upstream in one command.

English | [中文](README.zh-CN.md)

---

## Why you need it

LLMs pay for every token. When an Agent calls an API, the response is usually **human-oriented JSON** — dozens of fields, when the Agent actually needs 3. The rest is burning money.

AgentFirst sits between your Agent and upstream, doing four things automatically:

| Capability | Effect (measured, real) |
|---|---|
| ✂️ **Response slimming** | open-meteo weather: **434B → 78B, 82% savings** |
| 🗄️ **Caching** | identical requests hit cache — **zero upstream calls, zero double billing** |
| 💰 **Cost estimation** | know tokens / cost *before* you call |
| 📊 **Data flywheel** | usage stats auto-generate the optimal slim config |

**Core idea: APIs are for Agents, not for humans.** Give the Agent only what it needs.

---

## Two-minute start

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml

python -m agentfirst.app --config config.yaml install weather   # one command, ready to use
python -m agentfirst.app --config config.yaml serve
```

Call from your Agent (one curl, everything preconfigured):

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/weather/forecast?latitude=39.9&longitude=116.4&current=temperature_2m"
```

Response headers tell you everything: `X-Cache: HIT|MISS`, `X-Slim: strict|safe|off`.

---

## 🎁 9 ready-made API packages

`install` connects a real upstream in one command — spec, slim whitelist, cache policy and key injection all pre-tuned:

| Package | What | Cost | Measured slimming |
|---|---|---|---|
| `weather` | Weather (Open-Meteo) | free, no key | **82%** |
| `geocoding` / `airquality` | Place→coords / air quality | free, no key | 47% / 66% |
| `exchange` / `geoip` | FX rates / IP geolocation | free, no key | 66% / 73% |
| `covid` / `zipcode` | COVID stats / postal codes | free, no key | 67% / 28% |
| `logistics` | Shipment tracking (TrackingMore) | free tier 100/mo | — |
| `business` | Company registry (Tianyancha) | paid | — |

The 7 free packages are **verified against live networks** (`scripts/verify_free_packages.py`) — not a promise, proof.

```bash
python -m agentfirst.app --config config.yaml install logistics
```

---

## Why "de-humanized"

- **STRICT mode**: return only the `include_fields` whitelist (dot paths, list indices like `results.0.name` supported)
- **SAFE mode**: keep structure, drop nulls/empties — the fallback when you don't know the fields yet
- **Auto-degrade**: invalid JSON falls back to raw passthrough — **never corrupts data**
- **Short field mapping**: `temperature_2m → t`, one more slice off what the LLM sees

## Resilience & control

- **Auto retry**: exponential backoff (0.3s→0.6s) on 429/5xx and connection errors — idempotent methods only (GET/HEAD/PUT/DELETE)
- **Idempotency**: `Idempotency-Key` header dedupes writes — re-sent POSTs return the original result without re-executing upstream (Stripe-style)
- **Per-request overrides** (steer without restart):
  - `X-Skip-Cache: true` — bypass cache for this request
  - `X-Force-Slim: strict|safe|off` — override slim mode per request
  - `X-Cache-TTL: <seconds>` — override cache TTL per request
- **Async polling wrapper** (`async_poll` config): submit once, the gateway polls the upstream status endpoint until done — the Agent stops polling (saves ~99% polling tokens)

Design & roadmap: [docs/IMPROVEMENT_PLAN.md](docs/IMPROVEMENT_PLAN.md)

## Control plane

```bash
agentapi install <package>          # install a bundled package
agentapi import <spec> --id <id>    # register any OpenAPI 3.x
agentapi profile <id> --top-k 20    # generate slim config from real usage (data flywheel)
agentapi report <id>                # calls / hits / cost report
agentapi serve --port 8000          # run the gateway
```

HTTP endpoints: `GET /v1/estimate` (pre-call estimate), `GET /v1/schema/{id}` (slim config), `POST /v1/profile/{id}` (generate slim fields), `GET /v1/usage?user_id=` (billing).

---

## Configuration is the contract

```yaml
apis:
  weather:
    spec: specs/weather.yaml
    base_url: https://api.open-meteo.com/v1/
    cache_ttl: 60          # seconds; identical requests skip upstream within 60s
    slim_mode: strict      # strict | safe | off
    include_fields:
      - current.temperature_2m
    short_map:
      temperature_2m: t    # response key becomes t
users:
  sk-test: alice
pricing:
  miss: 0.0005             # price per miss ($)
  hit: 0.00025             # cache hits cost half — encourage reuse
models:
  claude-sonnet-4-5: {input: 3.0, output: 15.0}
```

**Per-call billing with miss/hit differentiated pricing** — the foundation for commercializing is already there.

---

## Quality

- ✅ **38 pytest tests, all green** (e2e, caching, billing, slimming/degrade edge cases)
- ✅ **CI runs on every push** (GitHub Actions, Python 3.11 / 3.12)
- ✅ **Live-network verification scripts**: `scripts/demo_live.py`, `scripts/verify_free_packages.py`
- ✅ Zero LLM dependency — slimming/estimation/caching are deterministic algorithms, white-box trustworthy

```bash
python -m pytest tests -q            # 38 passed
python scripts/verify_free_packages.py  # verify all 7 free packages against live networks
```

---

## Roadmap

- [ ] Polling → event-driven (webhooks): stop the Agent from polling, save 99% of polling tokens
- [ ] Files → minimal structured data: PDFs/contracts/invoices into a few hundred tokens
- [ ] Package ecosystem: more real-world API bundles

---

## License

[Apache 2.0](LICENSE) — use it, fork it, commercialize it. If it saves you money, a ⭐ is appreciated.

Design spec: [KERNEL_SPEC.md](KERNEL_SPEC.md) (Chinese)
