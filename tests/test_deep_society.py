from core.society import SocietyManager
from schemas.models import SimConfig


def test_phase2_runs_in_a_society_deterministically():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, n_agents=3, random_seed=44,
                    circadian_enabled=True, circadian_period=12, sleep_enabled=True,
                    imagination_enabled=True, curiosity_enabled=True, agency_enabled=True)
    a, b = SocietyManager(cfg), SocietyManager(cfg)
    for _ in range(15):
        a.tick(); b.tick()
    sa = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in a.world.agents.items()}
    sb = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in b.world.agents.items()}
    assert sa == sb
    assert a.agents[0].last_trace.circadian is not None
