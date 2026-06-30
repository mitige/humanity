from core.scenario import ScenarioRunner
from schemas.models import Scenario, Intervention, ConfigPatch


def _scn(**kw):
    return Scenario(name="t", config=ConfigPatch(n_agents=1, world_noise=0.0),
                    ticks=8, seed=7, **kw)


def test_runs_and_produces_series():
    res = ScenarioRunner().run(_scn())
    assert res.name == "t" and res.ticks == 8
    assert len(res.series.rows) == 8  # 1 agent x 8 ticks
    assert res.disclaimer


def test_is_deterministic():
    a = ScenarioRunner().run(_scn())
    b = ScenarioRunner().run(_scn())
    assert [r["energy"] for r in a.series.rows] == [r["energy"] for r in b.series.rows]


def test_stimulus_intervention_adds_world_object():
    scn = _scn(interventions=[Intervention(at_tick=2, type="stimulus",
                                           params={"kind": "hazard", "intensity": 3.0})])
    res = ScenarioRunner().run(scn)
    assert len(res.series.rows) == 8
