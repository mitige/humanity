from core.policy import Policy
from core.self_model import SelfModel
from schemas.models import (ActionType, EmotionState, Prediction, SimConfig)


def _preds():
    return [
        Prediction(action=ActionType.OBSERVE, target_id=None, expected_energy_delta=-0.6,
                   expected_danger=0.0, expected_novelty=0.3, expected_goal_progress=0.05,
                   uncertainty=0.5, value=0.10),
        Prediction(action=ActionType.EXPLORE, target_id=None, expected_energy_delta=-1.2,
                   expected_danger=0.0, expected_novelty=0.3, expected_goal_progress=0.1,
                   uncertainty=0.5, value=0.11),
    ]


def test_imagination_bonus_can_tip_the_choice():
    p = Policy()
    sm = SelfModel(SimConfig()).snapshot()
    base = p.choose_action(_preds(), [], sm, [], EmotionState(), [], SimConfig())
    tipped = p.choose_action(_preds(), [], sm, [], EmotionState(), [], SimConfig(),
                             imagined_best_action=ActionType.OBSERVE)
    assert tipped.candidate_scores["observe"] > base.candidate_scores["observe"]


def test_self_model_agency_raises_confidence():
    sm = SelfModel(SimConfig())
    before = sm.snapshot().confidence
    sm._apply_agency(0.95)
    assert sm.snapshot().confidence >= before
