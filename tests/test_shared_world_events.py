from core.shared_world import SharedWorld
from schemas.models import ActionDecision, ActionType, SimConfig


def _observe_decision():
    return ActionDecision(action=ActionType.OBSERVE, target_id=None, direction=None,
                          confidence=1.0, rationale="t", candidate_scores={})


def test_random_events_spawn_objects_with_noise():
    w = SharedWorld(SimConfig(grid_size=8, n_objects=3, world_noise=1.0, n_agents=1, random_seed=7))
    start = len(w.objects)
    for _ in range(40):
        w.step(0, _observe_decision())
    assert len(w.objects) > start  # seeded => deterministic stochastic spawns


def test_no_random_events_without_noise():
    w = SharedWorld(SimConfig(grid_size=8, n_objects=3, world_noise=0.0, n_agents=1, random_seed=7))
    start = len(w.objects)
    for _ in range(40):
        w.step(0, _observe_decision())
    assert len(w.objects) == start  # no noise => no spawns, fully deterministic
