# covid — 全球疫情数据

- 上游: [disease.sh](https://disease.sh/)（免费无 key，数据聚合自 WHO/JHU）
- 端点:
  - `GET /countries/{country}` 单国统计
  - `GET /all` 全球统计
  - `GET /historical/{country}?lastdays=30` 历史曲线

## 安装

```bash
python -m agentfirst.app --config config.yaml install covid
```

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/covid/countries/CN"
```

## 已预置的优化

- `slim_mode: strict` — 只保留 11 个关键数字（累计/今日/死亡/重症/人口）
- `cache_ttl: 3600s` — 数据每日更新，1 小时缓存足够

> 适合健康/出行类 Agent，如"目的地疫情是否严重"。
