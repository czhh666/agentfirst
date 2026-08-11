import json


def _set_path(target, parts: list, value):
    part = parts[0]
    rest = parts[1:]
    child_is_list = bool(rest) and rest[0].isdigit()
    if isinstance(target, list):
        idx = int(part)
        while len(target) <= idx:
            target.append(None)
        if len(rest) == 0:
            target[idx] = value
            return
        if target[idx] is None:
            target[idx] = [] if child_is_list else {}
        _set_path(target[idx], rest, value)
        return
    if len(rest) == 0:
        target[part] = value
        return
    if part not in target:
        target[part] = [] if child_is_list else {}
    _set_path(target[part], rest, value)


def pick_paths(data: dict, include: list) -> dict:
    out = {}
    for p in include:
        parts = p.split(".")
        node = data
        ok = True
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                ok = False
                break
        if ok:
            _set_path(out, parts, node)
    return out


def safe_strip(data):
    if isinstance(data, dict):
        return {k: v for k, v in ((k, safe_strip(v)) for k, v in data.items())
                if v is not None and v != {} and v != []}
    if isinstance(data, list):
        return [safe_strip(v) for v in data if v is not None]
    return data


def apply_short_map(data, mapping: dict):
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            out[mapping.get(k, k)] = apply_short_map(v, mapping)
        return out
    if isinstance(data, list):
        return [apply_short_map(v, mapping) for v in data]
    return data


def slim_response(content: bytes, mode: str, include: list, short_map: dict) -> tuple[bytes, str]:
    if mode == "off":
        return content, "off"
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            return content, "off"
    except (ValueError, UnicodeDecodeError):
        return content, "off"
    if mode == "strict":
        if not include:
            return content, "off"
        data = pick_paths(data, include)
    else:
        data = safe_strip(data)
    if short_map:
        data = apply_short_map(data, short_map)
    try:
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), mode
    except Exception:
        return content, "off"
