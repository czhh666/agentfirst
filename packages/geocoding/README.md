# geocoding — 地名转经纬度

- 上游: Open-Meteo Geocoding（免费无 key，与天气同厂）
- 端点:
  - `GET /search?name=beijing&count=5` 搜索地名 → 坐标/国家/时区/人口

## 安装

```bash
python -m agentfirst.app --config config.yaml install geocoding
```

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/geocoding/search?name=beijing&count=1"
```

## 已预置的优化

- `slim_mode: strict` — 只保留首个结果的 8 个字段（坐标/国家/省份/时区/人口）
- `cache_ttl: 86400s` — 地名→坐标几乎不变，全天命中缓存

> Agent 工作流经典组合：地名 → geocoding 得坐标 → weather 查天气。
