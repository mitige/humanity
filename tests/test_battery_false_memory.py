from core.test_battery import ConsciousnessTestBattery


def test_false_memory_intrudes_into_recall():
    res = ConsciousnessTestBattery().false_memory_test(seed=42)
    assert res.test == "false_memory"
    assert res.detail["intruded"] is True and res.score == 1.0
    assert res.disclaimer
