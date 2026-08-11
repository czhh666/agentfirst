# AgentFirst — 让 Agent 的每次 API 调用都省 60-80% token

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](requirements.txt)
[![CI](https://github.com/czhh666/agentfirst/actions/workflows/ci.yml/badge.svg)](https://github.com/czhh666/agentfirst/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/czhh666/agentfirst?style=social)](https://github.com/czhh666/agentfirst)

**给 LLM/Agent 调 API 用的"去人化"代理内核** — 自动瘦身响应、缓存结果、预估成本、计费记账。纯 Python，零 LLM 依赖，一条命令接入任何 OpenAPI 3.x 上游。

English | [中文](README.zh-CN.md)

---

## 为什么你需要它

LLM 每个 token 都要钱。Agent 调 API 时，返回的往往是**给人类看的大 JSON**——几十个字段，Agent 真正用的可能只有 3 个。剩下的全在烧钱。

AgentFirst 挂在 Agent 与上游之间，自动做四件事：

| 能力 | 效果（真实实测） |
|---|---|
| ✂️ **响应瘦身** | open-meteo 天气：**434B → 78B，省 82%** |
| 🗄️ **结果缓存** | 相同请求直接命中，**上游零调用、零重复计费** |
| 💰 **成本预估** | 调用前告诉你花多少 token / 多少钱 |
| 📊 **数据飞轮** | 自动统计字段使用频率 → 一键生成最优裁剪配置 |

**核心理念：API 是给 Agent 用的，不是给人看的。** 只把 Agent 需要的字段交给它。

---

## 两分钟上手

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml

python -m agentfirst.app --config config.yaml install weather   # 一键装好天气包
python -m agentfirst.app --config config.yaml serve
```

Agent 侧调用（一条 curl，什么都给你配好了）：

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/weather/forecast?latitude=39.9&longitude=116.4&current=temperature_2m"
```

响应头一眼看透内部：`X-Cache: HIT|MISS`、`X-Slim: strict|safe|off`。

---

## 🎁 开箱即用的 9 个 API 包

`install` 一条命令接入真实上游——spec、瘦身白名单、缓存策略、密钥注入全部调好：

| 包 | 场景 | 费用 | 实测瘦身 |
|---|---|---|---|
| `weather` | 天气（Open-Meteo） | 免费无 key | **82%** |
| `geocoding` / `airquality` | 地名→坐标 / 空气质量 | 免费无 key | 47% / 66% |
| `exchange` / `geoip` | 汇率 / IP 定位 | 免费无 key | 66% / 73% |
| `covid` / `zipcode` | 疫情数据 / 邮编查询 | 免费无 key | 67% / 28% |
| `logistics` | 快递追踪（TrackingMore） | 免费档 100次/月 | — |
| `business` | 企业工商（天眼查） | 付费 | — |

7 个免费包**真实网络调用验证过**（`scripts/verify_free_packages.py`），不是画饼。

```bash
python -m agentfirst.app --config config.yaml install logistics
```

---

## 为什么说它"去人化"

- **STRICT 模式**：只返回 `include_fields` 白名单（点分路径，支持 `results.0.name` 列表索引）
- **SAFE 模式**：保结构、删空值，不知道要什么字段时兜底
- **自动降级**：非法 JSON 自动退回原样透传——**永远不会损坏数据**
- **短字段映射**：`temperature_2m → t`，喂给 LLM 的内容再省一截

## 管理面

```bash
agentapi install <package>          # 安装预配置包
agentapi import <spec> --id <id>    # 接入任意 OpenAPI 3.x
agentapi profile <id> --top-k 20    # 从真实用量生成裁剪配置（数据飞轮）
agentapi report <id>                # 调用/命中/成本报告
agentapi serve --port 8000          # 启动网关
```

HTTP 管理端点：`GET /v1/estimate`（预估）、`GET /v1/schema/{id}`（配置）、`POST /v1/profile/{id}`（生成裁剪）、`GET /v1/usage?user_id=`（账单）。

---

## 配置即契约

```yaml
apis:
  weather:
    spec: specs/weather.yaml
    base_url: https://api.open-meteo.com/v1/
    cache_ttl: 60          # 秒；相同请求 60s 内免上游
    slim_mode: strict      # strict | safe | off
    include_fields:
      - current.temperature_2m
    short_map:
      temperature_2m: t    # 响应里直接叫 t
users:
  sk-test: alice
pricing:
  miss: 0.0005             # 未命中单价 $
  hit: 0.00025             # 命中半价——鼓励缓存
models:
  claude-sonnet-4-5: {input: 3.0, output: 15.0}
```

**每笔调用按"命中/未命中"差异化记账**——商业化的地基已经打好。

---

## 质量

- ✅ **38 个 pytest 测试全绿**（含 e2e、缓存、计费、瘦身降级边界）
- ✅ **CI 自动跑**（GitHub Actions，Python 3.11/3.12）
- ✅ **真实网络验证脚本**：`scripts/demo_live.py`、`scripts/verify_free_packages.py`
- ✅ 零 LLM 依赖——瘦身/预估/缓存全用确定性算法，白盒可信

```bash
python -m pytest tests -q            # 38 passed
python scripts/verify_free_packages.py  # 7 个免费包真实调用验证
```

---

## 路线图

- [ ] 轮询→事件化（Webhook）：Agent 不用反复查，省 99% 轮询 token
- [ ] 文件→最小结构化：PDF/合同/发票直接变成几百 token
- [ ] 预配置包生态：更多真实 API 接入

---

## License

[Apache 2.0](LICENSE) — 随便用、随便改、可以商用。觉得有用请点 ⭐，让更多人看到。

规格文档：[KERNEL_SPEC.md](KERNEL_SPEC.md)（中文）
