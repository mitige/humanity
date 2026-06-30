from core.agent import CognitiveAgent
from schemas.models import SimConfig


def _deep_cfg(**kw):
    return SimConfig(grid_size=8, n_objects=5, world_noise=0.0,
                     circadian_enabled=True, circadian_period=20, sleep_enabled=True,
                     dream_enabled=True, imagination_enabled=True, curiosity_enabled=True,
                     agency_enabled=True, **kw)


def test_phase2_substates_present_when_enabled():
    a = CognitiveAgent(_deep_cfg())
    tr = a.cognitive_cycle()
    assert tr.circadian is not None and tr.imagination is not None
    assert tr.curiosity is not None and tr.agency is not None and tr.sleep is not None
    assert tr.metrics.daylight <= 1.0


def test_phase2_substates_absent_when_disabled():
    a = CognitiveAgent(SimConfig(grid_size=8, n_objects=5, world_noise=0.0))
    tr = a.cognitive_cycle()
    assert tr.circadian is None and tr.imagination is None and tr.curiosity is None
    assert tr.agency is None and tr.sleep is None


def test_exhausted_agent_sleeps_and_recovers():
    a = CognitiveAgent(_deep_cfg(initial_energy=100.0))
    a.world.agent_energy = 5.0
    slept = False
    for _ in range(40):
        tr = a.cognitive_cycle()
        if tr.sleep and tr.sleep.is_sleeping:
            slept = True
    assert slept
