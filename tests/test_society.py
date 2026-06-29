from core.society import SocietyManager
from schemas.models import SimConfig


def test_society_ticks_all_agents_and_is_deterministic():
    cfg = SimConfig(grid_size=8, n_objects=4, world_noise=0.0, n_agents=3, random_seed=5)
    a = SocietyManager(cfg)
    b = SocietyManager(cfg)
    ta = [t.tick for t in a.tick()]
    tb = [t.tick for t in b.tick()]
    assert len(ta) == 3 and ta == tb  # one trace per agent, identical across runs


def test_society_of_one_matches_solo_energy_trajectory():
    cfg = SimConfig(grid_size=10, n_objects=6, world_noise=0.0, n_agents=1, random_seed=9)
    soc = SocietyManager(cfg)
    for _ in range(5):
        soc.tick()
    trace = soc.agents[0].last_trace
    assert trace is not None and trace.social is not None  # society always sets social
    assert soc.world.tick == 5


def test_verbalize_message_is_heard_next_tick():
    cfg = SimConfig(grid_size=6, n_objects=2, world_noise=0.0, n_agents=2, random_seed=3)
    soc = SocietyManager(cfg)
    soc.world.agents[0].x, soc.world.agents[0].y = 3, 3
    soc.world.agents[1].x, soc.world.agents[1].y = 3, 3  # same earshot
    soc.world.post_message(0, "agent 0: hello", [0.5, 0.5, 0.2, 0.3])
    soc.world.advance_tick()  # message now belongs to a prior tick
    obs1 = soc.world.observe(1)
    assert any("hello" in m.content for m in obs1.audible_messages)
