import json

from agentfirst.slimmer import apply_short_map, pick_paths, safe_strip, slim_response

from conftest import FULL_RESPONSE, INCLUDE, SHORT_MAP


def test_pick_paths_nested_and_top():
    out = pick_paths(FULL_RESPONSE, ["current.temperature_2m", "timezone"])
    assert out == {"current": {"temperature_2m": 22.5}, "timezone": "GMT"}


def test_pick_paths_missing_field_skipped():
    out = pick_paths(FULL_RESPONSE, ["current.does_not_exist", "current.temperature_2m"])
    assert out == {"current": {"temperature_2m": 22.5}}


def test_pick_paths_list_index():
    data = {"results": [{"name": "Beijing", "latitude": 39.9}, {"name": "Shanghai"}]}
    out = pick_paths(data, ["results.0.name", "results.0.latitude"])
    assert out == {"results": [{"name": "Beijing", "latitude": 39.9}]}


def test_safe_strip_removes_nulls_and_empty():
    data = {"a": None, "b": [], "c": {}, "d": {"x": None, "y": 1}, "e": [None, 2]}
    out = safe_strip(data)
    assert out == {"d": {"y": 1}, "e": [2]}


def test_apply_short_map_recursive():
    out = apply_short_map({"current_units": {"temperature_2m": "°C"}, "other": 1}, SHORT_MAP)
    assert out == {"u": {"t": "°C"}, "other": 1}


def test_strict_slim_reduces_volume_over_50_percent(full_response_bytes):
    out, mode = slim_response(full_response_bytes, "strict", INCLUDE, SHORT_MAP)
    assert mode == "strict"
    assert len(out) * 2 < len(full_response_bytes)


def test_safe_mode_keeps_structure(full_response_bytes):
    out, mode = slim_response(full_response_bytes, "safe", [], {})
    assert mode == "safe"
    data = json.loads(out)
    assert set(data.keys()) == set(FULL_RESPONSE.keys())


def test_invalid_json_degrades_to_off():
    out, mode = slim_response(b"not json", "strict", INCLUDE, {})
    assert mode == "off"
    assert out == b"not json"


def test_strict_without_include_degrades(full_response_bytes):
    out, mode = slim_response(full_response_bytes, "strict", [], {})
    assert mode == "off"
    assert out == full_response_bytes


def test_off_mode_passthrough(full_response_bytes):
    out, mode = slim_response(full_response_bytes, "off", INCLUDE, {})
    assert mode == "off"
    assert out == full_response_bytes
