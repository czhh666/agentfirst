import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentfirst.app import main
from agentfirst.config import load_config


def _write_config(path: Path, apis=None):
    raw = {"db_path": "data/test.db", "spec_dir": "specs", "users": {"sk-test": "alice"}, "apis": apis or {}}
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def test_install_weather_package(tmp_path):
    pkg_root = Path(__file__).resolve().parent.parent / "packages"
    if not pkg_root.is_dir():
        import pytest
        pytest.skip("packages/ not present")
    config_path = _write_config(tmp_path / "config.yaml")
    main(["--config", str(config_path), "install", "weather"])

    cfg = load_config(str(config_path))
    assert "weather" in cfg.apis
    api = cfg.apis["weather"]
    assert api.spec_path.endswith("weather.yaml")
    assert api.base_url == "https://api.open-meteo.com/v1/"
    assert api.slim_mode == "strict"
    assert "current.temperature_2m" in api.include_fields
    assert api.short_map.get("temperature_2m") == "t"
    assert Path(api.spec_path).is_file()


def test_install_package_preserves_auth_placeholder(tmp_path):
    pkg_root = Path(__file__).resolve().parent.parent / "packages"
    if not pkg_root.is_dir():
        import pytest
        pytest.skip("packages/ not present")
    config_path = _write_config(tmp_path / "config.yaml")
    main(["--config", str(config_path), "install", "business"])

    cfg = load_config(str(config_path))
    api = cfg.apis["business"]
    assert api.auth_header == "Authorization"
    assert "YOUR_" in api.auth_value
    assert api.cache_ttl == 86400


@pytest.mark.parametrize("name,api_id", [
    ("weather", "weather"), ("exchange", "exchange"), ("geoip", "geoip"),
    ("geocoding", "geocoding"), ("airquality", "airquality"),
    ("covid", "covid"), ("zipcode", "zipcode"), ("logistics", "logistics"),
])
def test_install_each_free_package(tmp_path, name, api_id):
    pkg_root = Path(__file__).resolve().parent.parent / "packages"
    if not (pkg_root / name).is_dir():
        import pytest
        pytest.skip(f"packages/{name} not present")
    config_path = _write_config(tmp_path / "config.yaml")
    main(["--config", str(config_path), "install", name])

    cfg = load_config(str(config_path))
    assert api_id in cfg.apis
    api = cfg.apis[api_id]
    assert api.spec_path.endswith(".yaml")
    assert api.base_url
    assert Path(api.spec_path).is_file()
    assert api.slim_mode in ("strict", "safe", "off")
    assert api.cache_ttl > 0
