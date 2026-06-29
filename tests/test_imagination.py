from core.imagination import Imagination
from core.world_model import WorldModel
from schemas.models import ActionType, Observation, SimConfig


def _obs():
    return Observation(tick=0, agent_x=2, agent_y=2, agent_energy=50.0, radius=3, visible=[])


def test_rollout_respects_horizon_and_is_pure():
    cfg = SimConfig(imagination_enabled=True, imagination_horizon=3)
    wm = WorldModel(cfg)
    beliefs_before = {a: dict(v) for a, v in wm.beliefs.items()}
    candidates = [(ActionType.OBSERVE, None), (ActionType.EXPLORE, None),
                  (ActionType.REST, None), (ActionType.ANALYZE, None)]
    st = Imagination().plan(wm, _obs(), candidates, current_energy=50.0,
                            initial_energy=100.0, config=cfg)
    assert st.horizon == 3 and st.best_first_action is not None
    assert st.n_rollouts == 3 * len(candidates)
    assert {a: dict(v) for a, v in wm.beliefs.items()} == beliefs_before


def test_low_imagined_energy_favours_rest_eventually():
    cfg = SimConfig(imagination_enabled=True, imagination_horizon=4)
    wm = WorldModel(cfg)
    candidates = [(ActionType.EXPLORE, None), (ActionType.REST, None)]
    st = Imagination().plan(wm, _obs(), candidates, current_energy=3.0,
                            initial_energy=100.0, config=cfg)
    assert st.best_first_action == ActionType.REST
