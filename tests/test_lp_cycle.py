from core.agent import CognitiveAgent
from schemas.models import SimConfig


def _cfg(**kw):
    return SimConfig(grid_size=8, n_objects=5, world_noise=0.0, learning_enabled=True,
                     concepts_enabled=True, meta_learning_enabled=True, personality_enabled=True, **kw)


def test_phase3_substates_present_when_enabled():
    a = CognitiveAgent(_cfg())
    tr = a.cognitive_cycle()
    assert tr.learning is not None and tr.concept is not None and tr.personality is not None
    assert "effective_learning_rate" in tr.metrics.model_dump()


def test_phase3_substates_absent_when_disabled():
    a = CognitiveAgent(SimConfig(grid_size=8, n_objects=5, world_noise=0.0))
    tr = a.cognitive_cycle()
    assert tr.learning is None and tr.concept is None and tr.personality is None


def test_learned_value_table_grows_over_time():
    a = CognitiveAgent(_cfg(initial_energy=100.0))
    for _ in range(20):
        a.cognitive_cycle()
    assert a.policy_learner.values()
