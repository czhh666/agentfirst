# airquality — 空气质量

- 上游: Open-Meteo Air Quality（免费无 key，与天气同厂）
- 端点:
  - `GET /air-quality?latitude=&longitude=&current=pm10,pm2_5` 当前空气质量

## 安装

```bash
python -m agentfirst.app --config config.yaml install airquality
```

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/airquality/air-quality?latitude=39.9&longitude=116.4&current=pm10,pm2_5"
```

## 已预置的优化

- `slim_mode: strict` — 只保留 PM10/PM2.5/NO2/O₃ 四个关键指标
- `short_map` — `nitrogen_dioxide→no2`、`pm2_5→pm25`
- `cache_ttl: 900s` — 15 分钟缓存（空气质量更新频率低）

> 适合健康/通勤/地产类 Agent 场景，与 `weather` 组合使用。
