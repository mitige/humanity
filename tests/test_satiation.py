"""Homeostatic satiation: a sated agent stops degenerating into endless REST."""
from collections import Counter

from core.agent import CognitiveAgent
from core.policy import Policy
from core.self_model import SelfModel
from schemas.models import ActionType, EmotionState, Prediction, SimConfig


def _rest_fraction(satiation: bool, n: int = 200) -> float:
    cfg = SimConfig(world_noise=0.1, random_seed=1, learning_enabled=True,
                    persist_memory=False, trace_logging=False,
                    satiation_enabled=satiation, satiation_weight=3.0)
    a = CognitiveAgent(cfg)
    acts = [a.cognitive_cycle().decision.action.value for _ in range(n)]
    return Counter(acts)["rest"] / n


def test_satiation_off_by_default():
    assert SimConfig().satiation_enabled is False


def test_satiation_markedly_reduces_resting():
    off = _rest_fraction(False)
    on = _rest_fraction(True)
    assert on < off                      # the sated agent rests much less
    assert on < 0.5                      # REST is no longer the dominant behaviour


def test_satiation_off_leaves_policy_scores_identical():
    p = Policy()
    sm = SelfModel(SimConfig()).snapshot()
    preds = [Prediction(action=ActionType.REST, target_id=None, expected_energy_delta=5.0,
                        expected_danger=0.0, expected_novelty=0.0, expected_goal_progress=0.0,
                        uncertainty=0.2, value=1.0)]
    base = p.choose_action(preds, [], sm, [], EmotionState(), [], SimConfig())
    off = p.choose_action(preds, [], sm, [], EmotionState(), [], SimConfig(satiation_enabled=False))
    assert base.candidate_scores == off.candidate_scores
