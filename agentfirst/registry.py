import json
from dataclasses import dataclass

import yaml


@dataclass
class Endpoint:
    method: str
    path: str
    operation_id: str = ""


@dataclass
class ApiSpec:
    api_id: str
    base_url: str
    endpoints: list


def load_spec_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        if path.endswith(".json"):
            return json.load(f)
        return yaml.safe_load(f) or {}


def build_spec(api_id: str, spec: dict, base_url: str = "") -> ApiSpec:
    if not base_url:
        servers = spec.get("servers") or []
        if servers:
            base_url = servers[0].get("url", "")
    base_url = base_url.rstrip("/")
    endpoints = []
    for path, item in (spec.get("paths") or {}).items():
        if not path.startswith("/"):
            path = "/" + path
        for method, op in (item or {}).items():
            if method.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                continue
            endpoints.append(Endpoint(method=method.upper(), path=path, operation_id=(op or {}).get("operationId", "")))
    if not endpoints:
        raise ValueError(f"spec for '{api_id}' has no paths")
    return ApiSpec(api_id=api_id, base_url=base_url, endpoints=endpoints)


def resolve_target(base_url: str, template: str, request_path: str) -> str:
    template_parts = [p for p in template.split("/") if p]
    request_parts = [p for p in request_path.strip("/").split("/") if p]
    values = {}
    if len(template_parts) == len(request_parts):
        for t, r in zip(template_parts, request_parts):
            if t.startswith("{") and t.endswith("}"):
                values[t[1:-1]] = r
            elif t != r:
                return None, None
        filled = template
        for k, v in values.items():
            filled = filled.replace("{" + k + "}", v)
        return base_url + filled, values
    return None, None


def match_endpoint(spec: ApiSpec, method: str, request_path: str):
    for ep in spec.endpoints:
        if ep.method != method.upper():
            continue
        url, params = resolve_target(spec.base_url, ep.path, request_path)
        if url is not None:
            return ep, url, params
    return None, None, None
