from agentfirst.telemetry import Telemetry


def test_log_and_report(tmp_path):
    t = Telemetry(str(tmp_path / "t.db"))
    for i in range(10):
        t.log_request("alice", "weather", "/forecast", cache_hit=(i % 2 == 0),
                      response_bytes=1000, tokens_estimate=300, cost=0.0005, upstream_status=200)
    rep = t.report("weather")
    assert rep["calls"] == 10
    assert rep["cache_hit_rate"] == 0.5
    assert rep["total_bytes"] == 10000
    assert rep["endpoints"][0]["calls"] == 10


def test_record_fields_and_profile(tmp_path):
    t = Telemetry(str(tmp_path / "t.db"))
    for i in range(5):
        t.record_fields("weather", "/forecast", {"current": {"t": 1}, "units": {"u": 2}})
    t.record_fields("weather", "/forecast", {"current": {"t": 1}})
    fields = t.generate_profile("weather", top_k=10)
    assert "current" in fields
    assert "units" in fields
    assert fields[0] == "current"


def test_size_stats_ignores_cache_hits(tmp_path):
    t = Telemetry(str(tmp_path / "t.db"))
    t.log_request("alice", "weather", "/forecast", False, response_bytes=4000, tokens_estimate=1, cost=0, upstream_status=200)
    t.log_request("alice", "weather", "/forecast", True, response_bytes=9000, tokens_estimate=1, cost=0, upstream_status=200)
    assert t.size_stats("weather", "/forecast") == 4000
    assert t.size_stats("weather", "/nope") is None
