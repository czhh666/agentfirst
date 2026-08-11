# logistics — 快递物流轨迹追踪

- 上游: [TrackingMore](https://www.trackingmore.com/)（国际物流，需注册获取 API key）
- 端点:
  - `POST /trackings/create?tracking_number=&carrier_code=` 创建追踪
  - `GET /trackings/{tracking_number}/{carrier_code}` 查询轨迹

## 安装

```bash
python -m agentfirst.app --config config.yaml install logistics
```

## 获取 key

1. 注册 https://www.trackingmore.com/ （免费档 100 次/月）
2. 打开 Dashboard → API → Copy API key
3. 填入 `config.yaml` → `apis.logistics.auth_value`

## 调用

```bash
# 先创建追踪
curl -X POST -H "X-Api-Key: sk-test" -H "Trackingmore-Api-Key: <你的key>" \
  "http://localhost:8000/v1/proxy/logistics/trackings/create?tracking_number=LX012345678CN&carrier_code=china-ems"

# 再查询轨迹（300 秒内命中缓存）
curl -H "X-Api-Key: sk-test" -H "Trackingmore-Api-Key: <你的key>" \
  "http://localhost:8000/v1/proxy/logistics/trackings/LX012345678CN/china-ems"
```

## 已预置的优化

- `slim_mode: safe` — 保结构删空值（快递轨迹字段因单而异，用 safe 更稳妥）
- `include_fields` — 只保留单号/承运商/状态/最近事件（首次调用后可用 `profile` 命令按真实数据重生成）
- `cache_ttl: 300s` — 快递状态 5 分钟内不会大变，命中即不重复调上游

> 注：代理会通过 `auth_header` 自动注入 `Trackingmore-Api-Key`，调用时无需再手动带。
