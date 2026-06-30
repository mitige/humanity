from core.scenario import ScenarioRunner
from core.test_battery import ConsciousnessTestBattery
from schemas.models import Scenario, Intervention, ConfigPatch


def test_full_scenario_with_interventions_is_reproducible():
    scn = Scenario(name="lab", config=ConfigPatch(n_agents=2, world_noise=0.0,
                   agency_enabled=True, learning_enabled=True), ticks=12, seed=5,
                   interventions=[Intervention(at_tick=3, type="stimulus",
                                               params={"kind": "hazard", "intensity": 2.0}),
                                  Intervention(at_tick=6, type="perturb",
                                               params={"type": "surprise", "magnitude": 1.0})])
    a, b = ScenarioRunner().run(scn), ScenarioRunner().run(scn)
    assert [r["energy"] for r in a.series.rows] == [r["energy"] for r in b.series.rows]
    assert len(a.series.rows) == 24  # 2 agents x 12 ticks


def test_all_three_battery_probes_run():
    bat = ConsciousnessTestBattery()
    assert bat.mirror_test(ticks=8).disclaimer
    assert bat.false_memory_test().disclaimer
    assert bat.calibration_test(ticks=10).disclaimer
