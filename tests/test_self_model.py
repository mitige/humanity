"""Tests for core.self_model.SelfModel (functional self-state bookkeeping)."""
from __future__ import annotations

import pytest

from core.self_model import SelfModel
from schemas.models import (
    ActionDecision,
    ActionType,
    EmotionState,
    SimConfig,
    StepResult,
)


def _decision(action: ActionType = ActionType.OBSERVE, confidence: float = 0.6) -> ActionDecision:
    """A minimal valid ActionDecision for self-model updates."""
    return ActionDecision(
        action=action,
        target_id=None,
        confidence=confidence,
        rationale="test",
        candidate_scores={action.value: 1.0},
    )


def _result(tick: int, new_energy: float, energy_delta: float = -0.8) -> StepResult:
    """A neutral StepResult with no danger/novelty/goal_progress."""
    return StepResult(
        tick=tick,
        action=ActionType.OBSERVE,
        target_id=None,
        energy_delta=energy_delta,
        new_energy=new_energy,
        events=[],
        actual={
            "danger": 0.0,
            "novelty": 0.0,
            "goal_progress": 0.0,
            "energy_value": 0.0,
            "utility": 0.0,
        },
    )


def test_initial_self_model_is_neutral() -> None:
    """A fresh self-model has the stable identity and neutral preferences."""
    sm = SelfModel(SimConfig(random_seed=1))
    state = sm.snapshot()
    assert state.identity == "Aurora-fn-01"
    assert state.coherence == pytest.approx(1.0)
    assert all(v == pytest.approx(0.5) for v in state.preferences.values())
    assert all(v == pytest.approx(0.5) for v in state.capability_beliefs.values())


def test_coherence_in_unit_interval() -> None:
    """Coherence stays within [0, 1] even after churny updates."""
    sm = SelfModel(SimConfig(random_seed=1, learning_rate=0.5))
    actions = [ActionType.OBSERVE, ActionType.REST, ActionType.EXPLORE, ActionType.INTERACT]
    for tick in range(1, 16):
        action = actions[tick % len(actions)]
        emotion = EmotionState(
            satisfaction=(tick % 2) * 0.8,
            fear=((tick + 1) % 2) * 0.7,
        )
        sm.update(
            decision=_decision(action),
            result=_result(tick, new_energy=100.0 - tick),
            prediction_error=0.3 if tick % 2 else 0.05,
            emotion=emotion,
            goals=[],
            tick=tick,
        )
        assert 0.0 <= sm.snapshot().coherence <= 1.0
    assert 0.0 <= sm.coherence() <= 1.0


def test_stable_behavior_keeps_coherence_high() -> None:
    """Repeating the same action with steady mood keeps coherence high."""
    sm = SelfModel(SimConfig(random_seed=1))
    for tick in range(1, 15):
        sm.update(
            decision=_decision(ActionType.OBSERVE),
            result=_result(tick, new_energy=100.0 - 0.8 * tick),
            prediction_error=0.05,
            emotion=EmotionState(),
            goals=[],
            tick=tick,
        )
    assert sm.snapshot().coherence > 0.7


def test_identity_constant_across_updates() -> None:
    """The agent's identity string never changes through updates."""
    sm = SelfModel(SimConfig(random_seed=1))
    identity = sm.snapshot().identity
    for tick in range(1, 10):
        sm.update(
            decision=_decision(ActionType.EXPLORE),
            result=_result(tick, new_energy=100.0 - tick),
            prediction_error=0.2,
            emotion=EmotionState(curiosity=0.5),
            goals=[],
            tick=tick,
        )
        assert sm.snapshot().identity == identity


def test_energy_tracks_step_result() -> None:
    """After an update the self-model energy equals the step's new_energy."""
    sm = SelfModel(SimConfig(random_seed=1))
    sm.update(
        decision=_decision(),
        result=_result(1, new_energy=87.5),
        prediction_error=0.1,
        emotion=EmotionState(),
        goals=[],
        tick=1,
    )
    assert sm.snapshot().energy == pytest.approx(87.5)


def test_set_goal_appends_unique() -> None:
    """set_goal adds new goals and ignores duplicates/blank input."""
    sm = SelfModel(SimConfig(random_seed=1))
    sm.set_goal("explorer la grille")
    sm.set_goal("explorer la grille")  # duplicate ignored
    sm.set_goal("  ")  # blank ignored
    sm.set_goal("trouver de la nourriture")
    goals = sm.snapshot().active_goals
    assert goals == ["explorer la grille", "trouver de la nourriture"]


def test_confidence_in_unit_interval() -> None:
    """Confidence stays within [0, 1] across updates."""
    sm = SelfModel(SimConfig(random_seed=1))
    for tick in range(1, 8):
        sm.update(
            decision=_decision(confidence=1.0),
            result=_result(tick, new_energy=100.0 - tick),
            prediction_error=0.0,
            emotion=EmotionState(),
            goals=[],
            tick=tick,
        )
        assert 0.0 <= sm.snapshot().confidence <= 1.0
