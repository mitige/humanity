from core.test_battery import ConsciousnessTestBattery


def test_mirror_discriminates_self_from_perturbed():
    res = ConsciousnessTestBattery().mirror_test(seed=42, ticks=10)
    assert res.test == "mirror"
    assert res.detail["agency_self"] >= res.detail["agency_perturbed"]
    assert res.score >= 0.0
    assert "not" in res.disclaimer.lower() and res.disclaimer


def test_mirror_is_deterministic():
    a = ConsciousnessTestBattery().mirror_test(seed=42, ticks=8)
    b = ConsciousnessTestBattery().mirror_test(seed=42, ticks=8)
    assert a.score == b.score
