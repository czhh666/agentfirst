# geoip — IP 地址定位

- 上游: [ipapi.co](https://ipapi.co/)（免费无 key，1000 次/天）
- 端点:
  - `GET /{ip}/json/` 查询指定 IP
  - `GET /json/` 查询本机出口 IP

## 安装

```bash
python -m agentfirst.app --config config.yaml install geoip
```

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/geoip/8.8.8.8/json/"
```

## 已预置的优化

- `slim_mode: strict` — 26 字段中只保留 10 个常用字段（城市/国家/经纬度/时区/归属）
- `short_map` — `country_name→cn`、`country_code→cc`
- `cache_ttl: 86400s` — IP 地理位置几乎不变，整天命中缓存

> 适合风控/合规/地域判断场景，Agent 可先查 IP 再决定走哪个 API。
