# exchange — 实时汇率

- 上游: [Frankfurter](https://frankfurter.app/)（ECB 欧洲央行数据，免费无 key，无需注册）
- 端点:
  - `GET /latest?base=USD&symbols=CNY` 最新汇率
  - `GET /2026-01-01?base=USD` 历史汇率

## 安装

```bash
python -m agentfirst.app --config config.yaml install exchange
```

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/exchange/latest?base=USD&symbols=CNY,EUR,JPY"
```

## 已预置的优化

- `slim_mode: strict` — 只返回 9 个常用币种，省掉全量 30+ 币种
- `short_map` — `rates→r`（如 `{"r": {"CNY": 6.7444}}`）
- `cache_ttl: 3600s` — 汇率 1 小时缓存，Agent 高频询价零重复上游调用
