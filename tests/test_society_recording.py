from core.society import SocietyManager
from schemas.models import SimConfig


def test_society_records_each_agent_each_tick():
    soc = SocietyManager(SimConfig(n_agents=2, world_noise=0.0, random_seed=4))
    for _ in range(3):
        soc.tick()
    rows = soc.recorder.series().rows
    assert len(rows) == 6  # 2 agents x 3 ticks
    assert {r["agent_id"] for r in rows} == {0, 1}
