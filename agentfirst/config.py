import os
from dataclasses import dataclass, field

import yaml


@dataclass
class ApiConfig:
    api_id: str
    spec_path: str = ""
    base_url: str = ""
    auth_header: str | None = None
    auth_value: str | None = None
    cache_ttl: int = 0
    cache_methods: tuple = ("GET",)
    slim_mode: str = "safe"
    include_fields: list = field(default_factory=list)
    short_map: dict = field(default_factory=dict)
    async_poll: dict = field(default_factory=dict)


@dataclass
class Config:
    db_path: str = "data/agentfirst.db"
    spec_dir: str = "specs"
    users: dict = field(default_factory=dict)
    models: dict = field(default_factory=dict)
    pricing: dict = field(default_factory=lambda: {"miss": 0.0005, "hit": 0.00025})
    apis: dict = field(default_factory=dict)

    def resolve(self, base_dir: str):
        self.db_path = os.path.join(base_dir, self.db_path) if not os.path.isabs(self.db_path) else self.db_path
        self.spec_dir = os.path.join(base_dir, self.spec_dir) if not os.path.isabs(self.spec_dir) else self.spec_dir
        for api in self.apis.values():
            if api.spec_path and not os.path.isabs(api.spec_path):
                api.spec_path = os.path.join(base_dir, api.spec_path)


def load_config(path: str) -> Config:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    apis = {}
    for api_id, cfg in (raw.get("apis") or {}).items():
        apis[api_id] = ApiConfig(
            api_id=api_id,
            spec_path=cfg.get("spec", ""),
            base_url=cfg.get("base_url", ""),
            auth_header=cfg.get("auth_header"),
            auth_value=cfg.get("auth_value"),
            cache_ttl=int(cfg.get("cache_ttl", 0)),
            cache_methods=tuple(cfg.get("cache_methods", ["GET"])),
            slim_mode=cfg.get("slim_mode", "safe"),
            include_fields=list(cfg.get("include_fields", [])),
            short_map=dict(cfg.get("short_map", {})),
            async_poll=dict(cfg.get("async_poll", {})),
        )
    cfg = Config(
        db_path=raw.get("db_path", "data/agentfirst.db"),
        spec_dir=raw.get("spec_dir", "specs"),
        users=dict(raw.get("users", {})),
        models=dict(raw.get("models", {})),
        pricing=dict(raw.get("pricing", {"miss": 0.0005, "hit": 0.00025})),
        apis=apis,
    )
    cfg.resolve(os.path.dirname(os.path.abspath(path)))
    return cfg
