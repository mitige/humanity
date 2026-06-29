"""Tests for core.world_model.WorldModel (learned forward model)."""
from __future__ import annotations

import pytest

from core.world_model import WorldModel
from schemas.models import (
    ActionType,
    Observation,
    Prediction,
    SimConfig,
    StepResult,
)


def _empty_observation() -> Observation:
    """A minimal observation with no visible objects."""
    return Observation(
        tick=0, agent_x=0, agent_y=0, agent_energy=100.0, radius=3, visible=[]
    )


def _rest_result() -> StepResult:
    """A fixed, repeatable REST outcome used for the learning test."""
    return StepResult(
        tick=1,
        action=ActionType.REST,
        target_id=None,
        energy_delta=5.5,
        new_energy=105.5,
        events=[],
        actual={
            "danger": 0.0,
            "novelty": 0.0,
            "goal_progress": 0.0,
            "energy_value": 0.0,
            "utility": 0.0,
        },
    )


def test_predict_returns_valid_prediction() -> None:
    """predict() yields a Prediction with bounded uncertainty and an action."""
    wm = WorldModel(SimConfig(random_seed=1))
    pred = wm.predict(_empty_observation(), ActionType.REST, None)
    assert isinstance(pred, Prediction)
    assert pred.action == ActionType.REST
    assert 0.0 <= pred.uncertainty <= 1.0


def test_compute_error_in_unit_interval() -> None:
    """compute_error() is always clipped to [0, 1] across many cases."""
    wm = WorldModel(SimConfig(random_seed=1))
    obs = _empty_observation()
    for action in ActionType:
        pred = wm.predict(obs, action, None)
        # A wildly different outcome should still produce a bounded error.
        result = StepResult(
            tick=1,
            action=action,
            target_id=None,
            energy_delta=-100.0,
            new_energy=0.0,
            events=[],
            actual={
                "danger": 1.0,
                "novelty": 1.0,
                "goal_progress": 1.0,
                "energy_value": 0.0,
                "utility": 1.0,
            },
        )
        err = wm.compute_error(pred, result)
        assert 0.0 <= err <= 1.0


def test_predict_all_matches_candidate_count() -> None:
    """predict_all() returns one Prediction per candidate."""
    wm = WorldModel(SimConfig(random_seed=1))
    obs = _empty_observation()
    candidates = [
        (ActionType.OBSERVE, None),
        (ActionType.REST, None),
        (ActionType.EXPLORE, None),
    ]
    preds = wm.predict_all(obs, candidates)
    assert len(preds) == len(candidates)
    assert [p.action for p in preds] == [a for a, _ in candidates]


def test_repeated_same_outcome_reduces_prediction_error() -> None:
    """Learning: repeating the SAME action+outcome drives error DOWN over time."""
    wm = WorldModel(SimConfig(random_seed=1, learning_rate=0.5))
    obs = _empty_observation()
    result = _rest_result()

    errors: list[float] = []
    for _ in range(10):
        pred = wm.predict(obs, ActionType.REST, None)
        errors.append(wm.compute_error(pred, result))
        wm.update(pred, result)

    # The error after several updates is strictly below the first observation.
    assert errors[-1] < errors[0]
    # And the trend is broadly non-increasing (monotone decrease for a delta-rule).
    assert errors[-1] <= errors[len(errors) // 2]


def test_update_drives_belief_toward_observed_energy() -> None:
    """The belief's energy_delta should move toward the observed value."""
    wm = WorldModel(SimConfig(random_seed=1, learning_rate=0.5))
    obs = _empty_observation()
    result = _rest_result()
    target = result.energy_delta

    before = wm.beliefs[ActionType.REST.value]["energy_delta"]
    for _ in range(10):
        pred = wm.predict(obs, ActionType.REST, None)
        wm.update(pred, result)
    after = wm.beliefs[ActionType.REST.value]["energy_delta"]

    assert abs(after - target) < abs(before - target)
    assert after == pytest.approx(target, abs=0.5)


def test_current_uncertainty_in_unit_interval() -> None:
    """The global current_uncertainty stays clipped to [0, 1] after updates."""
    wm = WorldModel(SimConfig(random_seed=1, learning_rate=0.3))
    obs = _empty_observation()
    result = _rest_result()
    for _ in range(5):
        pred = wm.predict(obs, ActionType.REST, None)
        wm.update(pred, result)
        assert 0.0 <= wm.current_uncertainty <= 1.0
