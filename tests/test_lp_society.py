from core.society import SocietyManager
from schemas.models import SimConfig


def test_phase3_society_is_deterministic_and_learns():
    cfg = SimConfig(grid_size=10, n_objects=10, world_noise=0.0, n_agents=3, random_seed=77,
                    learning_enabled=True, concepts_enabled=True, meta_learning_enabled=True,
                    personality_enabled=True)
    a, b = SocietyManager(cfg), SocietyManager(cfg)
    for _ in range(25):
        a.tick(); b.tick()
    sa = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in a.world.agents.items()}
    sb = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in b.world.agents.items()}
    assert sa == sb
    assert a.agents[0].last_trace.personality is not None
    assert any(ag.policy_learner.values() for ag in a.agents.values())
