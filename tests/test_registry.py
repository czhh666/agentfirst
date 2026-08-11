import pytest

from agentfirst.registry import build_spec, match_endpoint

from conftest import SPEC_PATHS


@pytest.fixture
def spec():
    return build_spec("demo", {"servers": [{"url": "https://api.test/v2/"}], "paths": SPEC_PATHS})


def test_build_spec_endpoints(spec):
    methods = {(e.method, e.path) for e in spec.endpoints}
    assert ("GET", "/forecast") in methods
    assert ("GET", "/items/{id}") in methods
    assert spec.base_url == "https://api.test/v2"


def test_build_spec_raises_without_paths():
    with pytest.raises(ValueError):
        build_spec("x", {"openapi": "3.0.0"})


def test_match_exact(spec):
    ep, url, params = match_endpoint(spec, "GET", "forecast")
    assert ep.path == "/forecast"
    assert url == "https://api.test/v2/forecast"
    assert params == {}


def test_match_template_params(spec):
    ep, url, params = match_endpoint(spec, "GET", "items/42")
    assert url == "https://api.test/v2/items/42"
    assert params == {"id": "42"}


def test_no_match(spec):
    assert match_endpoint(spec, "GET", "nope") == (None, None, None)
    assert match_endpoint(spec, "POST", "forecast") == (None, None, None)
