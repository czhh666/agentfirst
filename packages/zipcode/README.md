# zipcode — 邮编查询（物流域免费替代）

- 上游: [Zippopotam](https://api.zippopotam.us/)（免费无 key）
- 端点:
  - `GET /{country}/{postal}` 邮编 → 城市/州/经纬度（支持 US/GB/DE/JP 等，中国暂不支持）

## 安装

```bash
python -m agentfirst.app --config config.yaml install zipcode
```

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/zipcode/us/90210"
```

## 已预置的优化

- `slim_mode: strict` — 只保留邮编/国家/首个地点（城市/州/坐标）
- `short_map` — `post code→zip`、`place name→name`、`state abbreviation→state_abbr`
- `cache_ttl: 86400s` — 邮编数据几乎不变，整天命中缓存

> 物流域的免费替代：Agent 处理国际订单时先用它把邮编翻译成城市/州，再接 `logistics` 查轨迹（后者需 key）。
