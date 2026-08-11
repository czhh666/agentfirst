from agentfirst.billing import Billing


def test_charge_and_usage(tmp_path):
    b = Billing(str(tmp_path / "b.db"), {"miss": 0.0005, "hit": 0.00025})
    b.charge("alice", "weather", False)
    b.charge("alice", "weather", False)
    b.charge("alice", "weather", True)
    u = b.usage("alice")
    assert u["total_calls"] == 3
    assert u["total_cost_usd"] == 0.00125
    assert u["daily"][0]["cache_hits"] == 1
    assert b.usage("nobody")["total_calls"] == 0
