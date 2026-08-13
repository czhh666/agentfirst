# AgentFirst 内核

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-green.svg)](requirements.txt)
[![CI](https://github.com/czhh666/agentfirst/actions/workflows/ci.yml/badge.svg)](https://github.com/czhh666/agentfirst/actions/workflows/ci.yml)

[English](README.md) | 中文

专为 AI/Agent 调用 API 设计的"去人化"代理内核:挂在 Agent 与上游 API 之间,自动瘦身响应、缓存结果、预估成本、积累裁剪数据。纯代码实现,不依赖 LLM。

规格与标准见 [KERNEL_SPEC.md](KERNEL_SPEC.md)。开源协议见 [LICENSE](LICENSE)（Apache 2.0）。

## 快速开始

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml

python -m agentfirst.app --config config.yaml install weather    # 一键装好天气包
python -m agentfirst.app --config config.yaml serve
```

Agent 调用(数据面):

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/weather/forecast?latitude=39.9&longitude=116.4&current=temperature_2m,relative_humidity_2m"
```

响应头 `X-Cache: HIT|MISS`、`X-Slim: strict|safe|off`。

## 预配置包

内置开箱即用的 API 包（见 [packages/README.md](packages/README.md)）：

| 包 | 场景 | 费用 | 实测瘦身 |
|---|---|---|---|
| `weather` | 天气查询（open-meteo） | 免费无 key，装完即用 | 82% |
| `geocoding` / `airquality` | 地名转坐标 / 空气质量 | 免费无 key | 47% / 66% |
| `exchange` / `geoip` | 汇率 / IP 定位 | 免费无 key | 66% / 73% |
| `covid` / `zipcode` | 疫情数据 / 邮编查询 | 免费无 key | 67% / 28% |
| `logistics` | 快递物流追踪（TrackingMore） | 免费档 100 次/月 | — |
| `business` | 企业工商信息（天眼查） | 按次计费 | — |

`install` 命令复制 spec + 合并推荐配置到 `config.yaml`，付费包只需填一个 key：

```bash
python -m agentfirst.app --config config.yaml install logistics
```

## 管理面

| 命令 | 说明 |
|---|---|
| `agentapi install <package>` | 安装预配置包（天气/物流/工商等） |
| `agentapi import <spec> --id <api_id> [--base-url]` | 注册 OpenAPI 3.x 规范 |
| `agentapi profile <api_id> [--top-k N]` | 从调用统计自动生成裁剪字段并写入配置 |
| `agentapi report <api_id>` | 调用/缓存命中/成本报告 |
| `agentapi serve [--port 8000]` | 启动网关 |

HTTP 管理端点: `GET /v1/estimate`(调用前成本预估)、`GET /v1/schema/{api_id}`(裁剪配置)、`POST /v1/profile/{api_id}`(生成裁剪字段)、`GET /v1/usage?user_id=`(账单)。

## 配置(config.yaml)

```yaml
apis:
  <api_id>:
    spec: specs/<api_id>.yaml      # OpenAPI 3.x 文件
    base_url: https://...          # 上游地址(默认取 spec servers)
    auth_header: X-Api-Key         # 上游密钥注入(可选)
    auth_value: secret
    cache_ttl: 60                  # 秒;0 = 不缓存
    cache_methods: [GET]           # 可缓存的方法
    slim_mode: strict              # strict|safe|off
    include_fields:                # STRICT 白名单(点分路径,支持列表索引)
      - current.temperature_2m
    short_map:                     # 响应短字段映射(可选)
      temperature_2m: t
users:
  sk-test: alice                   # API key -> 用户
pricing:
  miss: 0.0005                     # 未命中单价 $
  hit: 0.00025                     # 缓存命中单价 $
models:
  claude-sonnet-4-5: {input: 3.0, output: 15.0}   # $/1M tokens
```

## 瘦身模式

- `strict` — 只保留 `include_fields` 白名单（点分路径，支持 `results.0.name` 列表索引）
- `safe` — 保结构，删空值
- `off` — 原样透传

非法 JSON 时自动降级为 `off`——永远不会损坏数据。

## 弹性与控制

- **自动重试**：429/5xx/连接错误指数退避重试（0.3s→0.6s），仅限幂等方法（GET/HEAD/PUT/DELETE）
- **幂等去重**：`Idempotency-Key` 请求头去重写请求——重发的 POST 直接返回原结果，不重复执行上游（Stripe 同款）
- **每请求覆盖头**（无需重启即可 steer）：
  - `X-Skip-Cache: true` — 本次请求绕过缓存
  - `X-Force-Slim: strict|safe|off` — 本次覆盖瘦身模式
  - `X-Cache-TTL: <秒>` — 本次覆盖缓存时长
- **异步轮询封装**（`async_poll` 配置）：Agent 提交一次，网关内部轮询状态直到完成——Agent 不再轮询（省 ~99% 轮询 token）

方案与路线图：[docs/IMPROVEMENT_PLAN.md](docs/IMPROVEMENT_PLAN.md)

## 测试

```bash
python -m pytest tests -v
python scripts/demo_live.py             # 真实网络演示(open-meteo)
python scripts/verify_free_packages.py  # 7 个免费包真实网络验证
```

实测(open-meteo):STRICT 裁剪响应 434B → 78B,省 82%;相同请求第二次 `X-Cache: HIT`,不再触发上游。

## 协议

[Apache 2.0](LICENSE)。可自由使用、修改、商用；不得用本项目名称/logo 为第三方服务背书。
