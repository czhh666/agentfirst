import argparse
import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .billing import Billing
from .cache import Cache, cache_key
from .config import ApiConfig, Config, load_config
from .estimator import estimate
from .proxy import Upstream
from .registry import ApiSpec, build_spec, load_spec_file, match_endpoint
from .slimmer import slim_response
from .telemetry import Telemetry


def create_app(config: Config, client: httpx.AsyncClient | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if client is not None:
            await client.aclose()

    app = FastAPI(title="AgentFirst", docs_url=None, redoc_url=None, openapi_url=None,
                  lifespan=lifespan)
    specs = {}
    for api_id, api in config.apis.items():
        if not api.spec_path:
            continue
        spec_dict = load_spec_file(api.spec_path)
        specs[api_id] = build_spec(api_id, spec_dict, api.base_url)

    cache = Cache(config.db_path)
    telemetry = Telemetry(config.db_path)
    billing = Billing(config.db_path, config.pricing)
    upstream = Upstream(client or httpx.AsyncClient(follow_redirects=True))

    def authenticate(request: Request) -> str:
        key = request.headers.get("x-api-key", "")
        user = config.users.get(key)
        if not user:
            raise HTTPException(status_code=401, detail="invalid api key")
        return user

    @app.api_route("/v1/proxy/{api_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy(api_id: str, path: str, request: Request):
        user = authenticate(request)
        api = config.apis.get(api_id)
        spec = specs.get(api_id)
        if not api or not spec:
            raise HTTPException(status_code=404, detail=f"unknown api_id: {api_id}")
        endpoint, url, _ = match_endpoint(spec, request.method, path)
        if not endpoint:
            raise HTTPException(status_code=404, detail=f"no endpoint {request.method} /{path}")
        query = dict(request.query_params)
        body = await request.body()

        ckey = cache_key(api_id, request.method, endpoint.path, query)
        cacheable = request.method.upper() in api.cache_methods and api.cache_ttl > 0
        cached = cache.get(ckey) if cacheable else None
        if cached is not None:
            out, mode = slim_response(cached, api.slim_mode, api.include_fields, api.short_map)
            cost = billing.charge(user, api_id, True)
            telemetry.log_request(user, api_id, endpoint.path, True, len(cached), len(cached) * (1 / 3.5), cost, 200)
            return Response(content=out, media_type="application/json",
                            headers={"X-Cache": "HIT", "X-Slim": mode})

        status, headers, content = await upstream.call(
            request.method, url, query, body, api.auth_header, api.auth_value)
        if status >= 400:
            telemetry.log_request(user, api_id, endpoint.path, False, len(content), 0, 0.0, status)
            return Response(content=content, status_code=status,
                            headers={"X-Cache": "MISS", "X-Upstream-Status": str(status)})

        out, mode = slim_response(content, api.slim_mode, api.include_fields, api.short_map)
        if cacheable:
            cache.set(ckey, content, api.cache_ttl)
        cost = billing.charge(user, api_id, False)
        telemetry.log_request(user, api_id, endpoint.path, False, len(content), len(content) * (1 / 3.5), cost, status)
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                telemetry.record_fields(api_id, endpoint.path, data)
        except ValueError:
            pass
        resp_headers = {"X-Cache": "MISS", "X-Slim": mode}
        if headers.get("content-type"):
            resp_headers["Content-Type"] = headers["content-type"]
        return Response(content=out, status_code=status, headers=resp_headers)

    @app.get("/v1/estimate")
    async def estimate_endpoint(api_id: str, method: str = "GET", path: str = "",
                                params: str = "{}", model: str | None = None):
        api = config.apis.get(api_id)
        if not api:
            raise HTTPException(status_code=404, detail=f"unknown api_id: {api_id}")
        try:
            query = json.loads(params)
        except ValueError:
            raise HTTPException(status_code=400, detail="params must be valid JSON")
        hist_p50 = telemetry.size_stats(api_id, path)
        result = estimate(config.models, model, method, path, query, None, hist_p50)
        result["slim_mode"] = api.slim_mode
        result["include_fields"] = api.include_fields
        return result

    @app.get("/v1/schema/{api_id}")
    async def schema(api_id: str):
        api = config.apis.get(api_id)
        if not api:
            raise HTTPException(status_code=404, detail=f"unknown api_id: {api_id}")
        return {"api_id": api_id, "slim_mode": api.slim_mode,
                "include_fields": api.include_fields, "short_map": api.short_map}

    @app.post("/v1/profile/{api_id}")
    async def profile(api_id: str, top_k: int = 20):
        fields = telemetry.generate_profile(api_id, top_k)
        return {"api_id": api_id, "generated_include_fields": fields}

    @app.get("/v1/usage")
    async def usage(user_id: str):
        return billing.usage(user_id)

    return app


def _save_config(config: Config, path: str):
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    apis = raw.setdefault("apis", {})
    for api_id, api in config.apis.items():
        entry = apis.setdefault(api_id, {})
        if api.spec_path:
            entry["spec"] = api.spec_path
        entry["base_url"] = api.base_url
        if api.include_fields:
            entry["include_fields"] = api.include_fields
        entry["slim_mode"] = api.slim_mode
        if api.cache_ttl:
            entry["cache_ttl"] = api.cache_ttl
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)


def _update_config_include_fields(config_path: str, api_id: str, fields: list):
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    raw.setdefault("apis", {}).setdefault(api_id, {})["include_fields"] = fields
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)


def _load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: str, raw: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agentapi", description="AgentFirst kernel CLI")
    parser.add_argument("--config", default="config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    p_install = sub.add_parser("install", help="install a packaged API bundle from packages/")
    p_install.add_argument("package")
    p_install.add_argument("--force", action="store_true", help="overwrite existing api config")

    p_import = sub.add_parser("import", help="register an OpenAPI spec")
    p_import.add_argument("spec")
    p_import.add_argument("--id", required=True)
    p_import.add_argument("--base-url", default="")

    p_profile = sub.add_parser("profile", help="generate include_fields from usage stats")
    p_profile.add_argument("api_id")
    p_profile.add_argument("--top-k", type=int, default=20)

    p_report = sub.add_parser("report", help="cost report")
    p_report.add_argument("api_id")

    p_serve = sub.add_parser("serve", help="run the gateway")
    p_serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)
    config_path = args.config
    if args.command == "install":
        cfg = load_config(config_path)
        base_dir = os.path.dirname(os.path.abspath(config_path))
        pkg_root = None
        for cand in (os.getcwd(), base_dir):
            if os.path.isdir(os.path.join(cand, "packages", args.package)):
                pkg_root = cand
                break
        if pkg_root is None:
            sys.exit(f"package '{args.package}' not found under packages/")
        pkg_dir = os.path.join(pkg_root, "packages", args.package)
        spec_src = os.path.join(pkg_dir, "spec.yaml")
        pkg_cfg = _load_yaml(os.path.join(pkg_dir, "package.yaml"))
        if not os.path.isfile(spec_src) or "api_id" not in pkg_cfg:
            sys.exit(f"invalid package '{args.package}': need spec.yaml + package.yaml(api_id)")
        api_id = pkg_cfg["api_id"]

        os.makedirs(cfg.spec_dir, exist_ok=True)
        dst = os.path.join(cfg.spec_dir, f"{api_id}.yaml")
        shutil.copyfile(spec_src, dst)
        rel = os.path.relpath(dst, base_dir).replace("\\", "/")
        cfg.apis.setdefault(api_id, ApiConfig(api_id=api_id))
        api = cfg.apis[api_id]
        api.spec_path = rel
        api.base_url = pkg_cfg.get("base_url", api.base_url)
        for k in ("auth_header", "auth_value"):
            if pkg_cfg.get(k):
                setattr(api, k, pkg_cfg[k])
        if pkg_cfg.get("cache_ttl"):
            api.cache_ttl = int(pkg_cfg["cache_ttl"])
        if pkg_cfg.get("cache_methods"):
            api.cache_methods = tuple(pkg_cfg["cache_methods"])
        if pkg_cfg.get("slim_mode"):
            api.slim_mode = pkg_cfg["slim_mode"]
        if pkg_cfg.get("include_fields"):
            api.include_fields = list(pkg_cfg["include_fields"])
        if pkg_cfg.get("short_map"):
            api.short_map = dict(pkg_cfg["short_map"])

        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        entry = {
            "spec": rel,
            "base_url": api.base_url,
            "cache_ttl": api.cache_ttl,
            "cache_methods": list(api.cache_methods),
            "slim_mode": api.slim_mode,
            "include_fields": api.include_fields,
            "short_map": api.short_map,
        }
        if api.auth_header and api.auth_value:
            entry["auth_header"] = api.auth_header
            entry["auth_value"] = api.auth_value
        raw.setdefault("apis", {})[api_id] = entry
        _save_yaml(config_path, raw)
        if pkg_cfg.get("auth_value") and "YOUR_" in str(pkg_cfg["auth_value"]):
            print(f"  NOTE: fill in your API key at config.yaml -> apis.{api_id}.auth_value")
        print(f"installed package '{args.package}' -> api_id='{api_id}' spec={rel}")
    elif args.command == "import":
        cfg = load_config(config_path)
        os.makedirs(cfg.spec_dir, exist_ok=True)
        dst = os.path.join(cfg.spec_dir, f"{args.id}.yaml")
        shutil.copyfile(args.spec, dst)
        rel = os.path.relpath(dst, os.path.dirname(os.path.abspath(config_path)))
        existing = cfg.apis.get(args.id)
        if existing:
            existing.spec_path = rel.replace("\\", "/")
            existing.base_url = args.base_url
        else:
            cfg.apis[args.id] = ApiConfig(api_id=args.id, spec_path=rel.replace("\\", "/"),
                                          base_url=args.base_url)
        _save_config(cfg, config_path)
        print(f"registered '{args.id}' spec -> {rel}")
    elif args.command == "profile":
        cfg = load_config(config_path)
        telemetry = Telemetry(cfg.db_path)
        fields = telemetry.generate_profile(args.api_id, args.top_k)
        _update_config_include_fields(config_path, args.api_id, fields)
        print(f"updated {args.api_id} include_fields (top {args.top_k}):")
        for f in fields:
            print(f"  - {f}")
    elif args.command == "report":
        cfg = load_config(config_path)
        telemetry = Telemetry(cfg.db_path)
        print(json.dumps(telemetry.report(args.api_id), ensure_ascii=False, indent=2))
    elif args.command == "serve":
        cfg = load_config(config_path)
        uvicorn.run(create_app(cfg), host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main(sys.argv[1:])
