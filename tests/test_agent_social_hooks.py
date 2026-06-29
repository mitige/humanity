from core.agent import CognitiveAgent
from core.shared_world import SharedWorld
from schemas.models import SimConfig


def test_agent_in_shared_world_produces_social_trace():
    cfg = SimConfig(grid_size=8, n_objects=4, world_noise=0.0, n_agents=2, random_seed=11)
    world = SharedWorld(cfg)
    a0 = CognitiveAgent(cfg, agent_id=0, shared_world=world)
    a1 = CognitiveAgent(cfg, agent_id=1, shared_world=world)
    world.agents[0].x, world.agents[0].y = 4, 4
    world.agents[1].x, world.agents[1].y = 5, 4
    trace = a0.cognitive_cycle()
    assert trace.social is not None and trace.social.agent_id == 0


def test_legacy_agent_has_no_social_trace():
    cfg = SimConfig(grid_size=8, n_objects=4, world_noise=0.0)
    a = CognitiveAgent(cfg)  # no agent_id / shared world => legacy single-agent path
    trace = a.cognitive_cycle()
    assert trace.social is None
