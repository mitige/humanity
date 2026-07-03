from core.test_battery import ConsciousnessTestBattery


def test_masking_signature():
    r = ConsciousnessTestBattery().masking_test(seed=42)
    assert r.test == "masking"
    assert r.detail["p_access_alone"] > 0.8       # target alone reaches access
    assert r.detail["p_access_masked"] < 0.2      # the mask abolishes it
    assert r.score > 0.5
    assert "not" in r.disclaimer.lower()


def test_blink_signature():
    r = ConsciousnessTestBattery().blink_test(seed=42)
    assert r.test == "blink"
    assert r.detail["p_t2_control"] > 0.8
    assert r.detail["p_t2_after_t1"] < 0.2
    assert r.score > 0.5


def test_priming_signature():
    r = ConsciousnessTestBattery().priming_test(seed=42)
    assert r.test == "priming"
    assert r.detail["prime_stayed_subliminal"] == 1.0   # the prime never ignited
    assert r.detail["p_access_primed"] > 0.8
    assert r.detail["p_access_unprimed"] < 0.2
    assert r.score > 0.5


def test_reality_monitor_probe():
    r = ConsciousnessTestBattery().reality_monitor_test(seed=42, ticks=30)
    assert r.test == "reality_monitor"
    assert 0.0 <= r.score <= 1.0
    assert r.detail["scored"] > 0
    assert "hallucination_analogues" in r.detail


def test_probes_are_deterministic():
    b = ConsciousnessTestBattery()
    for name in ("masking_test", "blink_test", "priming_test", "reality_monitor_test"):
        r1 = getattr(b, name)(seed=42)
        r2 = getattr(b, name)(seed=42)
        assert r1.score == r2.score and r1.detail == r2.detail
