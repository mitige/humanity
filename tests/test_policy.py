"""Tests for core.policy.Policy (candidate generation + action choice)."""
from __future__ import annotations

import pytest

from core.policy import Policy
from core.self_model import SelfModel
from schemas.models import (
    ActionDecision,
    ActionType,
    EmotionState,
    GoalPressure,
    Percept,
    Prediction,
    SalientItem,
    SimConfig,
)


def _self_state():
    """A neutral self-model state snapshot."""
    return SelfModel(SimConfig(random_seed=1)).snapshot()


def _prediction(action: ActionType, value: float, target_id: int | None = None) -> Prediction:
    """A Prediction with the given action/value used for scoring."""
    return Prediction(
        action=action,
        target_id=target_id,
        expected_energy_delta=value,
        expected_danger=0.0,
        expected_novelty=0.1,
        expected_goal_progress=0.0,
        uncertainty=0.5,
        value=value,
    )


def test_choose_action_returns_valid_action() -> None:
    """choose_action returns a valid ActionType with bounded confidence."""
    pol = Policy()
    predictions = [
        _prediction(ActionType.OBSERVE, 0.1),
        _prediction(ActionType.REST, 5.0),
        _prediction(ActionType.EXPLORE, 0.3),
    ]
    decision = pol.choose_action(
        predictions, [], _self_state(),
        [GoalPressure(need="preserve_energy", pressure=0.5, description="x")],
        EmotionState(), [], SimConfig(),
    )
    assert isinstance(decision, ActionDecision)
    assert isinstance(decision.action, ActionType)
    assert decision.action in set(ActionType)
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.candidate_scores  # non-empty
    assert decision.rationale  # non-empty rationale


def test_choose_action_candidate_scores_cover_predictions() -> None:
    """Every prediction contributes a score entry in candidate_scores."""
    pol = Policy()
    predictions = [
        _prediction(ActionType.OBSERVE, 0.1),
        _prediction(ActionType.REST, 5.0),
        _prediction(ActionType.ANALYZE, 0.2),
    ]
    decision = pol.choose_action(
        predictions, [], _self_state(), [], EmotionState(), [], SimConfig()
    )
    assert len(decision.candidate_scores) == len(predictions)


def test_choose_action_empty_predictions_defaults_to_observe() -> None:
    """With no candidates the policy falls back to a valid OBSERVE decision."""
    pol = Policy()
    decision = pol.choose_action(
        [], [], _self_state(), [], EmotionState(), [], SimConfig()
    )
    assert decision.action == ActionType.OBSERVE
    assert 0.0 <= decision.confidence <= 1.0


def test_candidate_actions_always_include_target_free_actions() -> None:
    """candidate_actions always proposes the target-free baseline actions."""
    pol = Policy()
    candidates = pol.candidate_actions([], _self_state())
    actions = {a for a, _ in candidates}
    assert {
        ActionType.OBSERVE,
        ActionType.EXPLORE,
        ActionType.REST,
        ActionType.ANALYZE,
        ActionType.VERBALIZE,
    } <= actions


def test_candidate_actions_add_target_directed_for_salient() -> None:
    """Salient dangerous/useful targets add AVOID/APPROACH/INTERACT candidates."""
    pol = Policy()
    hazard = SalientItem(
        percept=Percept(object_id=1, kind="hazard", dx=1, dy=0, distance=1.0,
                        danger=0.9, novelty=0.5, utility=0.0, energy_value=0.0),
        saliency=2.0,
        reasons={},
    )
    food = SalientItem(
        percept=Percept(object_id=2, kind="food", dx=0, dy=1, distance=1.0,
                        danger=0.0, novelty=0.5, utility=0.2, energy_value=8.0),
        saliency=1.5,
        reasons={},
    )
    candidates = pol.candidate_actions([hazard, food], _self_state())
    pairs = {(a, p.object_id if p else None) for a, p in candidates}
    assert (ActionType.AVOID, 1) in pairs
    assert (ActionType.APPROACH, 2) in pairs
    assert (ActionType.INTERACT, 2) in pairs


def test_choose_action_sets_direction_for_movement() -> None:
    """A chosen MOVE/EXPLORE decision carries a [dx, dy] direction in {-1,0,1}."""
    pol = Policy()
    salient = [
        SalientItem(
            percept=Percept(object_id=1, kind="curio", dx=2, dy=-3, distance=3.6,
                            danger=0.0, novelty=1.0, utility=0.0, energy_value=0.0),
            saliency=5.0,
            reasons={},
        )
    ]
    # Make EXPLORE clearly the best option.
    predictions = [
        _prediction(ActionType.OBSERVE, -5.0),
        _prediction(ActionType.EXPLORE, 10.0),
    ]
    decision = pol.choose_action(
        predictions, [], _self_state(),
        [GoalPressure(need="explore_novelty", pressure=2.0, description="x")],
        EmotionState(curiosity=0.8), salient, SimConfig(curiosity=2.0),
    )
    if decision.action in (ActionType.MOVE, ActionType.EXPLORE):
        assert decision.direction is not None
        assert len(decision.direction) == 2
        assert all(d in (-1, 0, 1) for d in decision.direction)
