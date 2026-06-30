from schemas.models import (Intervention, Scenario, MetricSeries, ScenarioResult,
                            BatteryResult, ConfigPatch, SimConfig)


def test_models_default_safely():
    iv = Intervention(at_tick=3, type="stimulus")
    assert iv.agent_id == 0 and iv.params == {}
    sc = Scenario(name="s")
    assert sc.ticks == 20 and sc.interventions == [] and isinstance(sc.config, ConfigPatch)
    ms = MetricSeries(fields=["tick"])
    assert ms.rows == []
    br = BatteryResult(test="mirror", score=0.5, interpretation="x", disclaimer="d")
    assert br.detail == {}


def test_config_has_history_max():
    assert SimConfig().metrics_history_max == 1000
