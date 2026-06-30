from core.test_battery import ConsciousnessTestBattery


def test_calibration_score_in_range_and_deterministic():
    a = ConsciousnessTestBattery().calibration_test(seed=42, ticks=20)
    b = ConsciousnessTestBattery().calibration_test(seed=42, ticks=20)
    assert a.test == "calibration"
    assert 0.0 <= a.score <= 1.0
    assert a.score == b.score and a.detail["n"] == 20
    assert a.disclaimer
