# weather — 免费实时天气

- 上游: [Open-Meteo](https://open-meteo.com/)（无需 key，免费）
- 端点: `GET /forecast`（当前/逐时/逐日）、`GET /archive`（历史）

## 安装

```bash
python -m agentfirst.app --config config.yaml install weather
```

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/weather/forecast?latitude=39.9&longitude=116.4&current=temperature_2m,relative_humidity_2m,apparent_temperature"
```

## 已预置的优化

- `slim_mode: strict` — 只返回白名单 5 个字段（实测 434B → 78B，省 82%）
- `short_map` — `temperature_2m→t`、`relative_humidity_2m→h`、`apparent_temperature→at`
- `cache_ttl: 60s` — 相同请求 60 秒内命中缓存，不重复调上游

需要更多字段时，编辑 `config.yaml` 的 `apis.weather.include_fields` 即可，无需改代码。
