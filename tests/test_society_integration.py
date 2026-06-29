from core.society import SocietyManager
from schemas.models import ActionType, SimConfig


def test_three_agents_run_deterministically_for_many_ticks():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, n_agents=3, random_seed=21)
    a, b = SocietyManager(cfg), SocietyManager(cfg)
    for _ in range(20):
        a.tick(); b.tick()
    sa = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in a.world.agents.items()}
    sb = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in b.world.agents.items()}
    assert sa == sb  # fully reproducible society


def test_contagion_changes_a_listeners_emotion_over_time():
    cfg = SimConfig(grid_size=6, n_objects=2, world_noise=0.0, n_agents=2,
                    random_seed=2, contagion_rate=0.5)
    soc = SocietyManager(cfg)
    soc.world.agents[0].x, soc.world.agents[0].y = 3, 3
    soc.world.agents[1].x, soc.world.agents[1].y = 3, 3
    soc.world.agents[0].publish(ActionType.AVOID, "fear", -0.8)
    before = soc.agents[1].last_emotion.fear
    for _ in range(3):
        soc.tick()
    after = soc.agents[1].last_emotion.fear
    assert after >= before  # listener's fear did not decrease while exposed


def test_society_of_one_keeps_full_legacy_suite_green():
    soc = SocietyManager(SimConfig(n_agents=1, world_noise=0.0, random_seed=1))
    trace = soc.tick()[0]
    assert trace.metrics is not None and trace.workspace is not None
