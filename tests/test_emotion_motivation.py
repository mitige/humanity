"""Tests for core.emotion.EmotionModel and core.motivation.MotivationSystem."""
from __future__ import annotations

import pytest

from core.emotion import EmotionModel
from core.motivation import MotivationSystem
from schemas.models import (
    EmotionState,
    GoalPressure,
    Percept,
    SelfModelState,
    SimConfig,
)


def _self_model(energy: float, coherence: float = 1.0, goals: list[str] | None = None) -> SelfModelState:
    """Build a SelfModelState with the given energy/coherence/active goals."""
    return SelfModelState(
        identity="Aurora-fn-01",
        age_ticks=0,
        energy=energy,
        confidence=0.5,
        mood=0.0,
        preferences={},
        active_goals=goals or [],
        capability_beliefs={},
        coherence=coherence,
        narrative="",
    )


def _danger_percept(danger: float) -> Percept:
    """A hazard percept with the given danger reading."""
    return Percept(
        object_id=0,
        kind="hazard",
        dx=1,
        dy=0,
        distance=1.0,
        danger=danger,
        novelty=0.0,
        utility=0.0,
        energy_value=0.0,
    )


def _pressures(goals: list[GoalPressure]) -> dict[str, float]:
    """Index goal pressures by need name."""
    return {g.need: g.pressure for g in goals}


# ----------------------------------------------------------------- emotion
def test_all_emotion_fields_in_unit_interval() -> None:
    """Every emotion component stays within [0, 1] across extreme inputs."""
    em = EmotionModel()
    cfg = SimConfig()
    state = em.update(
        danger=5.0, uncertainty=5.0, novelty=5.0, prediction_error=5.0,
        energy=-50.0, initial_energy=100.0, goal_progress=5.0,
        error_reduction=5.0, prev=EmotionState(), config=cfg,
    )
    for value in (state.fear, state.curiosity, state.satisfaction,
                  state.fatigue, state.confusion):
        assert 0.0 <= value <= 1.0


def test_low_energy_raises_fatigue() -> None:
    """Low energy yields higher fatigue than full energy."""
    em = EmotionModel()
    cfg = SimConfig()
    low = em.update(
        danger=0.0, uncertainty=0.0, novelty=0.0, prediction_error=0.0,
        energy=5.0, initial_energy=100.0, goal_progress=0.0,
        error_reduction=0.0, prev=EmotionState(), config=cfg,
    )
    full = em.update(
        danger=0.0, uncertainty=0.0, novelty=0.0, prediction_error=0.0,
        energy=100.0, initial_energy=100.0, goal_progress=0.0,
        error_reduction=0.0, prev=EmotionState(), config=cfg,
    )
    assert low.fatigue > full.fatigue


def test_visible_danger_raises_fear() -> None:
    """High perceived danger produces higher fear than a safe situation."""
    em = EmotionModel()
    cfg = SimConfig()
    dangerous = em.update(
        danger=0.9, uncertainty=0.0, novelty=0.0, prediction_error=0.0,
        energy=100.0, initial_energy=100.0, goal_progress=0.0,
        error_reduction=0.0, prev=EmotionState(), config=cfg,
    )
    safe = em.update(
        danger=0.0, uncertainty=0.0, novelty=0.0, prediction_error=0.0,
        energy=100.0, initial_energy=100.0, goal_progress=0.0,
        error_reduction=0.0, prev=EmotionState(), config=cfg,
    )
    assert dangerous.fear > safe.fear


# -------------------------------------------------------------- motivation
def test_low_energy_raises_preserve_energy_pressure() -> None:
    """Low self-model energy increases the preserve_energy pressure."""
    mot = MotivationSystem(SimConfig())
    cfg = SimConfig()
    low = mot.evaluate(_self_model(10.0), EmotionState(), [], 0.0, 0.0, cfg)
    high = mot.evaluate(_self_model(100.0), EmotionState(), [], 0.0, 0.0, cfg)
    assert _pressures(low)["preserve_energy"] > _pressures(high)["preserve_energy"]


def test_visible_danger_raises_reduce_danger_pressure() -> None:
    """A dangerous visible object increases the reduce_danger pressure."""
    mot = MotivationSystem(SimConfig())
    cfg = SimConfig()
    with_danger = mot.evaluate(
        _self_model(100.0), EmotionState(), [_danger_percept(0.9)], 0.0, 0.0, cfg
    )
    without = mot.evaluate(
        _self_model(100.0), EmotionState(), [], 0.0, 0.0, cfg
    )
    assert _pressures(with_danger)["reduce_danger"] > _pressures(without)["reduce_danger"]


def test_all_pressures_non_negative() -> None:
    """Every goal pressure is >= 0."""
    mot = MotivationSystem(SimConfig())
    goals = mot.evaluate(
        _self_model(50.0, coherence=0.5, goals=["explorer"]),
        EmotionState(fear=0.3),
        [_danger_percept(0.5)],
        prediction_error=0.4,
        uncertainty=0.6,
        config=SimConfig(),
    )
    assert all(g.pressure >= 0.0 for g in goals)


def test_active_goal_produces_achieve_goals_pressure() -> None:
    """An explicit active goal yields positive achieve_goals pressure."""
    mot = MotivationSystem(SimConfig())
    cfg = SimConfig()
    with_goal = mot.evaluate(_self_model(100.0, goals=["explorer"]), EmotionState(), [], 0.0, 0.0, cfg)
    without = mot.evaluate(_self_model(100.0, goals=[]), EmotionState(), [], 0.0, 0.0, cfg)
    assert _pressures(with_goal)["achieve_goals"] > 0.0
    assert _pressures(without)["achieve_goals"] == pytest.approx(0.0)


def test_total_pressure_is_sum() -> None:
    """total_pressure equals the sum of individual pressures."""
    mot = MotivationSystem(SimConfig())
    goals = mot.evaluate(_self_model(50.0), EmotionState(), [], 0.2, 0.2, SimConfig())
    assert mot.total_pressure(goals) == pytest.approx(sum(g.pressure for g in goals))
