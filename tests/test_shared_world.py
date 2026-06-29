# tests/test_shared_world.py
from core.shared_world import SharedWorld
from schemas.models import ActionDecision, ActionType, SimConfig


def _cfg(**kw):
    return SimConfig(grid_size=8, n_objects=4, world_noise=0.0, perception_radius=3,
                     n_agents=3, random_seed=7, **kw)


def test_agents_spawn_distinct_and_observable():
    w = SharedWorld(_cfg())
    assert set(w.agents.keys()) == {0, 1, 2}
    obs0 = w.observe(0)
    assert obs0.agent_x == w.agents[0].x and obs0.agent_y == w.agents[0].y


def test_observe_lists_other_agents_within_radius_only():
    w = SharedWorld(_cfg())
    w.agents[0].x, w.agents[0].y = 4, 4
    w.agents[1].x, w.agents[1].y = 5, 4
    w.agents[2].x, w.agents[2].y = 0, 0
    seen = {a.id for a in w.observe(0).visible_agents}
    assert 1 in seen and 2 not in seen and 0 not in seen


def test_step_moves_only_the_acting_agent():
    w = SharedWorld(_cfg())
    before = (w.agents[2].x, w.agents[2].y)
    dec = ActionDecision(action=ActionType.MOVE, target_id=None, direction=[1, 0],
                         confidence=1.0, rationale="t", candidate_scores={})
    w.step(0, dec)
    assert (w.agents[2].x, w.agents[2].y) == before


def test_determinism_same_seed_same_layout():
    a = SharedWorld(_cfg())
    b = SharedWorld(_cfg())
    assert [(o.id, o.x, o.y, o.kind) for o in a.objects.values()] == \
           [(o.id, o.x, o.y, o.kind) for o in b.objects.values()]
    assert {i: (bd.x, bd.y) for i, bd in a.agents.items()} == \
           {i: (bd.x, bd.y) for i, bd in b.agents.items()}
