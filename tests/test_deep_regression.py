from core.agent import CognitiveAgent
from schemas.models import SimConfig


def test_all_flags_off_matches_phase1_energy_and_actions():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, random_seed=33)
    a, b = CognitiveAgent(cfg), CognitiveAgent(cfg)
    seq_a, seq_b = [], []
    for _ in range(15):
        seq_a.append(a.cognitive_cycle().decision.action)
        seq_b.append(b.cognitive_cycle().decision.action)
    assert seq_a == seq_b  # deterministic
    assert a.last_trace.circadian is None and a.last_trace.agency is None
