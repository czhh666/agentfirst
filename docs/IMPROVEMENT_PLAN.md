# 中断与恢复 + Steer 改进方案

> 状态: **v0.2.0 已交付改进 1(重试) + 3A(覆盖头); v0.3.0 已交付改进 2(幂等去重)** | 提案 v1.0 | 对应评论问题: "怎么支持中断和恢复，steer"
> 设计原则: 保持纯代码、不依赖 LLM、每项都可独立验收、向后兼容

---

## 背景: 当前能力(已实现)

| 能力 | 位置 | 说明 |
|---|---|---|
| 缓存即被动恢复 | app.py:66-74 | 相同 GET 重试命中缓存, 不重复调上游、命中半价 |
| 超时硬边界 | proxy.py:3 | 30s 读 / 10s 连接超时, 不无限挂起 |
| 崩溃安全 | cache.py:31-39 | SQLite commit 即持久, 记账/缓存不丢 |

**缺口**: 无主动重试、无幂等去重、无断点续传、配置静态不可运行时改变。

---

## 改进 1: 主动重试(Retry) — ✅ v0.2.0 已实现

**问题**: 上游瞬断(超时/5xx)直接失败, Agent 需自行重试。

**实现**: proxy.py `Upstream.call(..., retries=2, retry_delay=0.3)` 指数退避(0.3s→0.6s), 仅对幂等方法(GET/HEAD/PUT/DELETE)重试(由 app.py 控制 `retries=2 if idempotent else 0`), 可重试状态 429/500/502/503/504 与连接类异常。

```python
# proxy.py 新增
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
RETRYABLE_EXC = (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError)
async def call(self, method, url, query, body, auth_header, auth_value,
               retries=2, retry_delay=0.3):
    for attempt in range(retries + 1):
        try:
            status, headers, content = await self._call_once(...)
            if status not in RETRYABLE_STATUS or attempt >= retries:
                return status, headers, content
        except RETRYABLE_EXC as exc:
            last_exc = exc
            if attempt >= retries:
                raise last_exc
        await asyncio.sleep(retry_delay * (2 ** attempt))
```

**验收**: mock 上游前两次返回 503 → 第三次 200, 断言最终 200 且调用次数=3。

---

## 改进 2: 幂等去重(Idempotency) — ✅ v0.3.0 已实现

**问题**: POST 响应丢失后重发可能重复执行(下单/扣费类危险)。GET 已有缓存兜底, POST 没有。

**实现**: `Idempotency-Key` 请求头(Stripe 同款)。`cache.py` 新增 `Idempotency` 类(SQLite `idem` 表, TTL 24h), 按 `sha256(user|api_id|idem_key)` 去重。请求带 key 时: 命中 → 原样返回上次响应(带 `X-Idempotent-Replay: true`); 未命中 → 执行上游, 成功后(状态 <400)写记录。

**方案**: 支持 `Idempotency-Key` 请求头(标准做法, Stripe 同款)。同 key 的进行中/已完成请求直接返回同一结果。

```python
# app.py proxy() 开头新增
idem_key = request.headers.get("Idempotency-Key")
if idem_key:
    done = idem_store.get(user, api_id, idem_key)
    if done:
        return Response(content=done.body, status_code=done.status,
                        headers={"X-Idempotent-Replay": "true"})
# 完成响应前(仅当请求带 key):
#   idem_store.set(user, api_id, idem_key, status, content, ttl=86400)
```

实现: 复用 SQLite 建 `idem` 表(key=sha256(user|api_id|idem_key), status, body, created_at)。TTL 24h 自动清理。

**验收**: 同一 Idempotency-Key 发两次 POST, 断言上游 mock 只被调用 1 次、两次响应体一致、第二次带 `X-Idempotent-Replay: true`。

---

## 改进 3: 运行时 Steer(动态控制)

**问题**: slim_mode/TTL/缓存开关写死配置, 改后必须重启。

**方案 A — 每请求覆盖头**(最快, 不动架构):
- `X-Skip-Cache: true` → 本次绕过缓存读写
- `X-Force-Slim: strict|safe|off` → 本次覆盖 slim_mode
- `X-Cache-TTL: 60` → 本次覆盖缓存秒数

```python
# app.py proxy() 内
cacheable = cacheable and request.headers.get("X-Skip-Cache", "").lower() != "true"
mode = request.headers.get("X-Force-Slim", api.slim_mode)
ttl = int(request.headers.get("X-Cache-TTL", api.cache_ttl))
```

**验收**: 带 `X-Skip-Cache` 两次请求, 断言第二次仍 `X-Cache: MISS`。

**方案 B — 运行时可变配置**(中期):
- `POST /v1/config/{api_id}` 运行时改 slim_mode/TTL(持久化到 config.yaml)
- 需引入"运行时配置层"(内存 dict + 文件回写), 改动较大, 列为 v1.1

---

## 改进 4: 断点续传(长响应)

**问题**: 大响应中断从头再来。

**方案**: 阶段性不做完整断点续传(复杂度高), 改为:
- 上游响应支持 `X-Response-Id` 落 SQLite(响应快照)
- Agent 断线后带 `X-Resume-From: <response_id>` 重发 → 网关直接返回快照

**注意**: 这与缓存功能重叠度高, 建议**合并进缓存**(带 response_id 的缓存即可达到同样效果)。**结论: 低优先级, 不做独立实现, 用缓存+Idempotency 覆盖 90% 场景。**

---

## 优先级与工作量

| 改进 | 优先级 | 复杂度 | 建议排期 |
|---|---|---|---|
| 1 主动重试 | P1 | 低(1 文件) | v0.2.0 |
| 3A 每请求覆盖头 | P1 | 低(~15 行) | v0.2.0 |
| 2 幂等去重 | P2 | 中(新表+逻辑) | v0.3.0 |
| 3B 运行时配置 API | P3 | 中 | v0.4.0 |
| 4 断点续传 | P4 | 高 | 不做(被缓存覆盖) |

**建议 v0.2.0 先交付 1+3A**(两天工作量, 纯增量, 不破坏现有 38 测试), 即可在知乎回复"重试+可 steer"。

---

## 回复口径建议(供知乎评论回复)

> 问得专业。当前已实现的是"被动恢复": GET 成功响应落 SQLite 缓存, Agent 中断后重试直接命中, 不重复调上游、不重复计费; 超时有 30s/10s 硬边界防止挂死。未实现的是主动机制——我已给出改进方案: (1) 指数退避重试(仅幂等方法), (2) Idempotency-Key 去重(POST 不重复执行), (3) 每请求覆盖头(X-Skip-Cache / X-Force-Slim)实现运行时 steer。1 和 3 预计 v0.2.0 落地。
