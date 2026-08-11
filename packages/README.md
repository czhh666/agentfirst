# AgentFirst 预配置包

开箱即用的 API 接入包，每个包含三件东西：

| 文件 | 作用 |
|---|---|
| `spec.yaml` | OpenAPI 3.x 规范（上游接口定义） |
| `package.yaml` | 推荐配置：`base_url` / `slim_mode` / `include_fields` / `short_map` / `cache_ttl` / key 占位 |
| `README.md` | 安装、申请 key、调用示例 |

## 一键安装

```bash
python -m agentfirst.app --config config.yaml install <package>
```

命令会：复制 `spec.yaml` 到 `specs/`、合并推荐配置到 `config.yaml` 的 `apis.<api_id>`。

## 现有包

| 包 | 场景 | 上游 | 费用 | 可用性 | 实测瘦身 |
|---|---|---|---|---|---|
| `weather` | 天气查询 | open-meteo | 免费无 key | ✅ 装完即用 | 82% |
| `geocoding` | 地名→经纬度 | open-meteo | 免费无 key | ✅ 装完即用 | 47% |
| `airquality` | 空气质量 | open-meteo | 免费无 key | ✅ 装完即用 | 66% |
| `exchange` | 实时汇率 | Frankfurter(ECB) | 免费无 key | ✅ 装完即用 | 66% |
| `geoip` | IP 定位 | ipapi.co | 免费无 key | ✅ 装完即用 | 73% |
| `covid` | 全球疫情 | disease.sh | 免费无 key | ✅ 装完即用 | 67% |
| `zipcode` | 邮编查询 | Zippopotam | 免费无 key | ✅ 装完即用 | 28% |
| `logistics` | 快递物流追踪 | TrackingMore | 免费档 100 次/月 | 填 key 即用 | — |
| `business` | 企业工商信息 | 天眼查开放平台 | 按次计费 | 填 key 即用 | — |

7 个免费包经真实网络调用验证（scripts/verify_free_packages.py），瘦身/缓存/计费链路全部正常。

## 如何新增一个包

```text
packages/<name>/
  spec.yaml        # OpenAPI 3.x
  package.yaml     # 配置片段(见 packages/weather/package.yaml)
  README.md        # 使用说明
```

`package.yaml` 最小结构：

```yaml
api_id: <api_id>
base_url: <上游地址>
slim_mode: strict            # strict | safe | off
include_fields: [...]        # 白名单(点分路径)
short_map: {...}             # 响应短字段映射
cache_ttl: 60                # 缓存秒数
auth_header: X-Api-Key       # 需要 key 时填
auth_value: YOUR_KEY         # 占位符,安装后手动替换
```

> 设计原则：每个包都带着"已调好的瘦身配置"。免费包开箱即用；付费包用 `YOUR_*` 占位，安装后只需在 `config.yaml` 填一个 key。
