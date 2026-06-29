"""Tests for core.perception.Perception and core.attention.Attention."""
from __future__ import annotations

import math

import pytest

from core.attention import Attention
from core.perception import Perception
from schemas.models import (
    EmotionState,
    GoalPressure,
    Observation,
    Percept,
    SimConfig,
    WorldObject,
)


def _observation(agent_x: int, agent_y: int, objects: list[WorldObject]) -> Observation:
    """Build an observation with the given agent pose and visible objects."""
    return Observation(
        tick=0,
        agent_x=agent_x,
        agent_y=agent_y,
        agent_energy=100.0,
        radius=3,
        visible=objects,
    )


def test_perception_encodes_dx_dy_distance() -> None:
    """dx/dy are relative to the agent; distance is euclidean."""
    obj = WorldObject(id=0, kind="food", x=5, y=8, energy_value=8.0, novelty=0.5)
    obs = _observation(2, 4, [obj])
    percepts = Perception().encode(obs, seen_counts={})
    assert len(percepts) == 1
    p = percepts[0]
    assert p.dx == 5 - 2
    assert p.dy == 8 - 4
    assert p.distance == pytest.approx(math.hypot(3, 4))
    assert p.object_id == 0


def test_perception_novelty_attenuated_by_familiarity() -> None:
    """Effective novelty = novelty / (1 + seen_count)."""
    obj = WorldObject(id=7, kind="curio", x=1, y=0, novelty=1.0)
    obs = _observation(0, 0, [obj])
    fresh = Perception().encode(obs, seen_counts={})[0]
    seen = Perception().encode(obs, seen_counts={7: 3})[0]
    assert fresh.novelty == pytest.approx(1.0)
    assert seen.novelty == pytest.approx(1.0 / (1 + 3))
    assert seen.novelty < fresh.novelty


def test_perception_is_pure_no_mutation() -> None:
    """encode() must not mutate the observation or seen_counts mapping."""
    obj = WorldObject(id=0, kind="food", x=1, y=1, novelty=0.9)
    obs = _observation(0, 0, [obj])
    seen = {0: 2}
    Perception().encode(obs, seen_counts=seen)
    assert seen == {0: 2}
    assert obs.visible[0].novelty == pytest.approx(0.9)


def test_attention_respects_capacity() -> None:
    """attention.select never returns more than config.attention_capacity items."""
    percepts = [
        Percept(
            object_id=i,
            kind="curio",
            dx=1,
            dy=0,
            distance=1.0,
            danger=0.1,
            novelty=0.5,
            utility=0.2,
            energy_value=0.0,
        )
        for i in range(8)
    ]
    cfg = SimConfig(attention_capacity=3)
    sal = Attention().select(percepts, [], 0.0, EmotionState(), cfg)
    assert len(sal) <= cfg.attention_capacity
    assert len(sal) == 3


def test_attention_sorted_descending() -> None:
    """Returned salient items are ordered by descending saliency."""
    percepts = [
        Percept(
            object_id=i,
            kind="hazard",
            dx=1,
            dy=0,
            distance=1.0,
            danger=0.1 * i,
            novelty=0.0,
            utility=0.0,
            energy_value=0.0,
        )
        for i in range(5)
    ]
    goals = [GoalPressure(need="reduce_danger", pressure=1.0, description="x")]
    sal = Attention().select(percepts, goals, 0.0, EmotionState(), SimConfig())
    saliencies = [it.saliency for it in sal]
    assert saliencies == sorted(saliencies, reverse=True)


def test_higher_danger_raises_saliency() -> None:
    """A more dangerous percept is more salient, all else equal."""
    att = Attention()
    cfg = SimConfig()
    goals = [GoalPressure(need="reduce_danger", pressure=1.0, description="x")]
    low = att.select(
        [Percept(object_id=0, kind="hazard", dx=1, dy=0, distance=1.0,
                 danger=0.1, novelty=0.0, utility=0.0, energy_value=0.0)],
        goals, 0.0, EmotionState(), cfg,
    )
    high = att.select(
        [Percept(object_id=0, kind="hazard", dx=1, dy=0, distance=1.0,
                 danger=0.9, novelty=0.0, utility=0.0, energy_value=0.0)],
        goals, 0.0, EmotionState(), cfg,
    )
    assert high[0].saliency > low[0].saliency


def test_higher_novelty_raises_saliency() -> None:
    """A more novel percept is more salient, all else equal."""
    att = Attention()
    cfg = SimConfig(curiosity=1.0)
    low = att.select(
        [Percept(object_id=0, kind="curio", dx=1, dy=0, distance=1.0,
                 danger=0.0, novelty=0.1, utility=0.0, energy_value=0.0)],
        [], 0.0, EmotionState(), cfg,
    )
    high = att.select(
        [Percept(object_id=0, kind="curio", dx=1, dy=0, distance=1.0,
                 danger=0.0, novelty=0.9, utility=0.0, energy_value=0.0)],
        [], 0.0, EmotionState(), cfg,
    )
    assert high[0].saliency > low[0].saliency


def test_focus_in_unit_interval_and_empty() -> None:
    """focus() returns a value in [0, 1]; empty input gives 0."""
    att = Attention()
    assert att.focus([]) == 0.0
    percepts = [
        Percept(object_id=i, kind="hazard", dx=1, dy=0, distance=1.0,
                danger=0.5, novelty=0.3, utility=0.1, energy_value=0.0)
        for i in range(4)
    ]
    goals = [GoalPressure(need="reduce_danger", pressure=1.0, description="x")]
    sal = att.select(percepts, goals, 0.2, EmotionState(curiosity=0.3), SimConfig())
    f = att.focus(sal)
    assert 0.0 <= f <= 1.0


def test_reasons_breakdown_present() -> None:
    """Each salient item carries a per-source contribution breakdown."""
    percepts = [
        Percept(object_id=0, kind="hazard", dx=1, dy=0, distance=1.0,
                danger=0.7, novelty=0.4, utility=0.2, energy_value=0.0)
    ]
    goals = [GoalPressure(need="reduce_danger", pressure=1.0, description="x")]
    sal = Attention().select(percepts, goals, 0.1, EmotionState(), SimConfig())
    assert sal
    assert isinstance(sal[0].reasons, dict)
    assert sal[0].reasons  # non-empty
