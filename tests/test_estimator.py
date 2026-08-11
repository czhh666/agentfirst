from agentfirst.estimator import estimate

MODELS = {"claude-sonnet-4-5": {"input": 3.0, "output": 15.0}}


def test_estimate_fields():
    r = estimate(MODELS, "claude-sonnet-4-5", "GET", "/forecast", {"latitude": "1", "longitude": "2"}, None)
    for key in ("estimated_input_tokens", "estimated_output_tokens", "estimated_tokens",
                "estimated_cost_usd", "estimated_response_bytes", "suggestions"):
        assert key in r


def test_estimate_uses_hist_p50():
    r1 = estimate(MODELS, None, "GET", "/x", {}, None, hist_p50=1000)
    r2 = estimate(MODELS, None, "GET", "/x", {}, None, hist_p50=100000)
    assert r2["estimated_response_bytes"] > r1["estimated_response_bytes"]
    assert r2["estimated_cost_usd"] > r1["estimated_cost_usd"]


def test_estimate_suggestion_on_large_response():
    r = estimate(MODELS, None, "GET", "/x", {}, None, hist_p50=100000)
    assert any("STRICT" in s for s in r["suggestions"])


def test_estimate_cost_is_positive():
    r = estimate(MODELS, None, "GET", "/x", {"q": "a" * 100}, b"{}")
    assert r["estimated_cost_usd"] > 0
