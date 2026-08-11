import json

TOKEN_PER_BYTE = 1 / 3.5
DEFAULT_RESPONSE_BYTES = 4096


def _char_len(obj) -> int:
    if isinstance(obj, str):
        return len(obj)
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def estimate(models: dict, model: str | None, method: str, path: str,
             query: dict, body: bytes | None, hist_p50: int | None = None) -> dict:
    in_chars = _char_len(query or {}) + (len(body) if body else 0)
    resp_bytes = hist_p50 if hist_p50 else DEFAULT_RESPONSE_BYTES
    in_tokens = max(1, in_chars * TOKEN_PER_BYTE)
    out_tokens = max(1, resp_bytes * TOKEN_PER_BYTE)
    price = models.get(model, {"input": 3.0, "output": 15.0})
    cost = (in_tokens / 1e6 * price.get("input", 3.0)) + (out_tokens / 1e6 * price.get("output", 15.0))
    suggestions = []
    if resp_bytes > 8192:
        suggestions.append("response 偏大,建议启用 STRICT 裁剪或缩小 include_fields")
    if hist_p50 is None:
        suggestions.append("该端点暂无历史数据,响应体积为默认估算")
    if out_tokens > 2000:
        suggestions.append("输出 token 较多,可考虑换输出更便宜的模型")
    return {
        "method": method,
        "path": path,
        "model": model or "default",
        "estimated_input_tokens": round(in_tokens),
        "estimated_output_tokens": round(out_tokens),
        "estimated_tokens": round(in_tokens + out_tokens),
        "estimated_cost_usd": round(cost, 6),
        "estimated_response_bytes": resp_bytes,
        "suggestions": suggestions,
    }
