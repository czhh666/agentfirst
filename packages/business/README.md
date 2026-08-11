# business — 企业工商信息查询

- 上游: [天眼查开放平台](https://open.tianyancha.com/)（企业实名认证，按次计费）
- 端点:
  - `GET /ic/baseinfo/normal?keyword=公司名` 企业工商信息
  - `GET /ic/risk/loans?id=` 司法/融资风险信息

## 安装

```bash
python -m agentfirst.app --config config.yaml install business
```

## 获取 key

工商类 API 基本都需要企业认证 + 付费（天眼查/企查查/爱企查均如此），暂无免费替代。
流程：注册天眼查开放平台 → 实名认证 → 购买套餐 → 复制 `Token`。
填入 `config.yaml` → `apis.business.auth_value`（代理会自动注入 `Authorization` 头）。

## 调用

```bash
curl -H "X-Api-Key: sk-test" \
  "http://localhost:8000/v1/proxy/business/ic/baseinfo/normal?keyword=华为"
```

## 已预置的优化

- `slim_mode: strict` — 只返回 7 个核心字段（公司名/状态/注册资本/成立时间/法人/信用代码/类型），省 70%+ token
- `cache_ttl: 86400s` — 工商信息一天内几乎不变，全天命中缓存、零重复计费
- 首次真实调用后可用 `profile` 命令按实际返回结构微调白名单

> 计费建议：该 API 按次付费，缓存命中走 `hit` 半价计费，Agent 高频查询同家公司时成本显著下降。
