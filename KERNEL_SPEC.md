# AgentFirst 内核规格与标准 (KERNEL SPEC)

> 版本: v1.0
> 定位: 通用 API 代理内核——去人化、为 token 优化、纯代码实现(不依赖 LLM)

## 1. 内核范围

内核 = 挂在 Agent 与任意上游 REST API 之间的代理层,六模块:

```
M1 接入层   OpenAPI 3.x 导入/解析、路由、上游转发、密钥注入
M2 瘦身引擎 响应裁剪(STRICT/SAFE)、短字段映射、自动降级
M3 预估器   调用前 token/成本预估与建议
M4 缓存层   TTL 结果缓存(可替换适配器)
M5 数据飞轮 请求日志、字段使用统计 → 自动生成裁剪配置
M6 计费     按调用记账(命中/未命中差异化定价)
```

## 2. 设计原则

1. **纯代码**: 裁剪、缓存、预估全部确定性算法,不调用 LLM(零额外 token 成本)
2. **无人类 UI**: 只提供 HTTP 数据面 + 极简 CLI 管理面
3. **按 API 维度配置**: 每个 api_id 独立(base_url、TTL、裁剪模式、白名单)
4. **失败安全**: 裁剪失败自动降级返回原始响应,绝不向 agent 返回损坏数据
5. **可迭代**: 模块间仅通过少量接口耦合,便于替换实现
6. **日志不阻塞**: 请求路径上的记账/统计为同步落库但只写不读、轻量

## 3. 接口契约

### 3.1 数据面(agent 用)

| 端点 | 说明 |
|---|---|
| `{ANY} /v1/proxy/{api_id}/{path:path}` | 主入口: 缓存→转发→裁剪→记账 |
| `GET /v1/estimate?api_id=&method=&path=&params=` | 调用前预估 tokens/cost/建议 |
| `GET /v1/schema/{api_id}` | 返回当前裁剪配置(供 agent 感知可用字段) |

响应头: `X-Cache: HIT|MISS`, `X-Slim: strict|safe|off`, 错误时 `X-Upstream-Status`。

### 3.2 管理面(CLI / HTTP)

| 命令 | 说明 |
|---|---|
| `agentapi import <spec.yaml> --id <api_id>` | 注册 API |
| `agentapi profile <api_id> --top-k 20` | 从统计生成裁剪配置 |
| `agentapi report <api_id>` | 成本节省报告 |
| `GET /v1/usage?user_id=` | 用量与账单 |

### 3.3 认证

请求头 `X-Api-Key`;配置文件 `users` 段定义 `key -> user`。

## 4. 模块标准(验收标准)

### M1 接入层
- [ ] 解析 OpenAPI 3.x(YAML/JSON 文件),生成端点注册表(api_id → base_url + path 列表)
- [ ] 路由支持 path 参数替换、query/body 透传
- [ ] 上游密钥注入(配置 auth_header + 值)
- [ ] 上游错误原样透传(状态码、错误体)

### M2 瘦身引擎
- [ ] STRICT: 仅保留白名单字段(点分路径),顶层/嵌套均支持
- [ ] SAFE: 保留全部结构,仅删除 null/空容器
- [ ] 短字段映射: 响应 key 替换(可逆配置)
- [ ] 裁剪结果 JSON 解析失败 → 自动降级返回原始响应
- [ ] 基准测试: STRICT 裁剪后响应体积下降 ≥ 50%

### M3 预估器
- [ ] 输入 method/path/params/model → 输出 estimated_tokens / estimated_cost / suggestions
- [ ] 响应体积估计: 优先用该端点历史 p50(telemetry),否则默认值
- [ ] token 换算: 字节数 / 3.5(英文近似,可配置)
- [ ] suggestions: 响应过大 → 建议裁剪/换模型;历史高频 → 建议缓存

### M4 缓存层
- [ ] key = sha256(api_id|method|path|规范化参数)
- [ ] TTL 过期自动失效;GET 幂等端点默认缓存,POST 默认不缓存(可配置)
- [ ] 命中返回原始(未裁剪)缓存体,裁剪在命中路径同样生效
- [ ] 适配器接口 `Cache.get/set`,默认 SQLite 实现(零外部依赖)

### M5 数据飞轮
- [ ] 每笔调用落 request_log: user/api_id/endpoint/缓存命中/字节/token估计/成本/上游状态
- [ ] field_usage 统计: 每个端点各字段的出现次数与累计体积
- [ ] `generate_profile(api_id, top_k)` → 自动生成 STRICT 白名单配置(出现频率 top_k 字段)
- [ ] 统计不阻塞请求路径

### M6 计费
- [ ] 每笔调用记 usage 一行(user/api_id/ts/命中/成本)
- [ ] 单价: 未命中 $0.0005/次, 命中 $0.00025/次(配置化)
- [ ] `/v1/usage?user_id=` 返回按日汇总 + 总额

## 5. 端到端验收

1. `pytest` 全部通过
2. 注册 open-meteo 免费 API 示例 spec
3. 两次相同 GET 请求: 第一次 `X-Cache: MISS`,第二次 `X-Cache: HIT` 且未触发上游
4. STRICT 裁剪后响应体积下降 ≥ 50%(open-meteo 实测)
5. 裁剪配置自动生成(profile 命令)后可切换裁剪字段
6. 每笔调用在 usage 中有记账记录

## 6. 目录结构

```
agentfirst/
├── agentfirst/
│   ├── __init__.py
│   ├── config.py       # 配置加载(YAML)
│   ├── registry.py     # M1 OpenAPI 解析
│   ├── proxy.py        # M1 上游转发
│   ├── slimmer.py      # M2 瘦身
│   ├── estimator.py    # M3 预估
│   ├── cache.py        # M4 缓存
│   ├── telemetry.py    # M5 飞轮
│   ├── billing.py      # M6 计费
│   └── app.py          # FastAPI 入口 + CLI
├── examples/
│   └── open-meteo.yaml # 示例 spec
├── tests/
│   ├── test_registry.py test_slimmer.py test_cache.py
│   ├── test_estimator.py test_telemetry.py test_billing.py
│   └── test_e2e.py
└── config.example.yaml
```
