from core.agent import CognitiveAgent
from schemas.models import SimConfig


def test_all_phase3_flags_off_is_deterministic_and_clean():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, random_seed=55)
    a, b = CognitiveAgent(cfg), CognitiveAgent(cfg)
    sa = [a.cognitive_cycle().decision.action for _ in range(15)]
    sb = [b.cognitive_cycle().decision.action for _ in range(15)]
    assert sa == sb
    assert a.last_trace.learning is None and a.last_trace.personality is None
    assert a.last_trace.concept is None
