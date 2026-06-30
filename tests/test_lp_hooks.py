from core.world_model import WorldModel
from core.policy import Policy
from core.self_model import SelfModel
from schemas.models import (ActionType, EmotionState, Observation, Prediction, SimConfig, StepResult)


def _result(e, g):
    return StepResult(tick=1, action=ActionType.INTERACT, target_id=None, energy_delta=e,
                      new_energy=50.0, events=[], actual={"danger": 0.0, "novelty": 0.0, "goal_progress": g})


def test_world_model_lr_override_changes_update_magnitude():
    obs = Observation(tick=0, agent_x=0, agent_y=0, agent_energy=50.0, radius=3, visible=[])
    slow = WorldModel(SimConfig(learning_rate=0.2)); fast = WorldModel(SimConfig(learning_rate=0.2))
    pred = slow.predict(obs, ActionType.INTERACT, None)
    res = _result(9.0, 0.5)
    slow.update(pred, res)
    fast.update(pred, res, lr_override=0.9)
    sb = slow.beliefs["interact"]["energy_delta"]; fb = fast.beliefs["interact"]["energy_delta"]
    assert abs(fb - 9.0) < abs(sb - 9.0)


def test_policy_learned_values_bonus_lifts_action():
    p = Policy()
    sm = SelfModel(SimConfig()).snapshot()
    preds = [Prediction(action=ActionType.OBSERVE, target_id=None, expected_energy_delta=-0.6,
                        expected_danger=0.0, expected_novelty=0.3, expected_goal_progress=0.05,
                        uncertainty=0.5, value=0.1)]
    base = p.choose_action(preds, [], sm, [], EmotionState(), [], SimConfig())
    lifted = p.choose_action(preds, [], sm, [], EmotionState(), [], SimConfig(value_learning_weight=1.0),
                             learned_values={"observe": 0.9})
    assert lifted.candidate_scores["observe"] > base.candidate_scores["observe"]
