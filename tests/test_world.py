"""Tests for core.world.World (the environment/dynamics simulator)."""
from __future__ import annotations

import pytest

from core.constants import ACTION_COSTS, ENERGY_CAP_FACTOR, PASSIVE_ENERGY_DECAY
from core.world import World
from schemas.models import ActionDecision, ActionType, SimConfig


def _decision(action: ActionType, target_id: int | None = None) -> ActionDecision:
    """Build a minimal valid ActionDecision for stepping the world."""
    return ActionDecision(
        action=action,
        target_id=target_id,
        confidence=0.5,
        rationale="test",
        candidate_scores={action.value: 1.0},
    )


def test_world_is_deterministic_for_fixed_seed() -> None:
    """Same seed yields identical object layouts and agent placement."""
    cfg = SimConfig(random_seed=123, world_noise=0.0)
    w1 = World(cfg)
    w2 = World(SimConfig(random_seed=123, world_noise=0.0))

    assert (w1.agent_x, w1.agent_y) == (w2.agent_x, w2.agent_y)
    dump1 = [o.model_dump() for o in w1.objects.values()]
    dump2 = [o.model_dump() for o in w2.objects.values()]
    assert dump1 == dump2


def test_world_different_seeds_differ() -> None:
    """Different seeds should (with very high probability) differ in layout."""
    w1 = World(SimConfig(random_seed=1, world_noise=0.0, n_objects=10))
    w2 = World(SimConfig(random_seed=2, world_noise=0.0, n_objects=10))
    dump1 = [o.model_dump() for o in w1.objects.values()]
    dump2 = [o.model_dump() for o in w2.objects.values()]
    assert dump1 != dump2


def test_agent_starts_at_grid_center() -> None:
    """The agent spawns at the integer grid center."""
    cfg = SimConfig(grid_size=12, random_seed=42)
    w = World(cfg)
    center = cfg.grid_size // 2
    assert w.agent_x == center
    assert w.agent_y == center
    assert w.agent_energy == pytest.approx(cfg.initial_energy)


def test_step_applies_action_cost_and_passive_decay() -> None:
    """An OBSERVE step subtracts the action cost plus passive decay."""
    cfg = SimConfig(random_seed=42, world_noise=0.0)
    w = World(cfg)
    start = w.agent_energy
    result = w.step(_decision(ActionType.OBSERVE))
    expected_cost = ACTION_COSTS[ActionType.OBSERVE.value] + PASSIVE_ENERGY_DECAY
    assert result.energy_delta == pytest.approx(-expected_cost, abs=1e-6)
    assert result.new_energy == pytest.approx(start - expected_cost, abs=1e-6)


def test_step_increments_tick() -> None:
    """Each step advances the world tick by exactly one."""
    cfg = SimConfig(random_seed=42, world_noise=0.0)
    w = World(cfg)
    assert w.tick == 0
    r1 = w.step(_decision(ActionType.OBSERVE))
    assert w.tick == 1
    assert r1.tick == 1
    w.step(_decision(ActionType.OBSERVE))
    assert w.tick == 2


def test_energy_clamped_to_cap() -> None:
    """Repeated REST cannot push energy above initial_energy * ENERGY_CAP_FACTOR."""
    cfg = SimConfig(random_seed=42, world_noise=0.0)
    w = World(cfg)
    cap = cfg.initial_energy * ENERGY_CAP_FACTOR
    for _ in range(100):
        w.step(_decision(ActionType.REST))
    assert w.agent_energy <= cap + 1e-9
    assert w.agent_energy == pytest.approx(cap, abs=1e-6)


def test_energy_clamped_to_zero_floor() -> None:
    """Energy never goes below zero even after many costly ticks."""
    cfg = SimConfig(random_seed=42, world_noise=0.0, initial_energy=5.0)
    w = World(cfg)
    for _ in range(50):
        result = w.step(_decision(ActionType.INTERACT))
        assert result.new_energy >= 0.0
    assert w.agent_energy >= 0.0


def test_observe_only_returns_objects_within_radius() -> None:
    """observe() must only surface objects within Chebyshev perception_radius."""
    cfg = SimConfig(random_seed=42, world_noise=0.0, perception_radius=3)
    w = World(cfg)
    obs = w.observe()
    for obj in obs.visible:
        cheb = max(abs(obj.x - w.agent_x), abs(obj.y - w.agent_y))
        assert cheb <= cfg.perception_radius
    assert obs.radius == cfg.perception_radius
    assert obs.agent_x == w.agent_x
    assert obs.agent_y == w.agent_y


def test_observe_no_noise_does_not_mutate_stored_objects() -> None:
    """With world_noise=0 readings equal stored object attributes."""
    cfg = SimConfig(random_seed=42, world_noise=0.0)
    w = World(cfg)
    obs = w.observe()
    for vis in obs.visible:
        stored = w.objects[vis.id]
        assert vis.danger == pytest.approx(stored.danger)
        assert vis.novelty == pytest.approx(stored.novelty)
        assert vis.utility == pytest.approx(stored.utility)


def test_reset_restores_initial_state() -> None:
    """reset() rebuilds the world deterministically from the stored config."""
    cfg = SimConfig(random_seed=7, world_noise=0.0)
    w = World(cfg)
    baseline = [o.model_dump() for o in w.objects.values()]
    for _ in range(5):
        w.step(_decision(ActionType.MOVE))
    assert w.tick == 5
    w.reset()
    assert w.tick == 0
    assert [o.model_dump() for o in w.objects.values()] == baseline


def test_snapshot_is_json_serializable_structure() -> None:
    """snapshot() returns the documented dict shape with native types."""
    w = World(SimConfig(random_seed=42))
    snap = w.snapshot()
    assert set(snap.keys()) >= {"grid_size", "tick", "agent", "objects"}
    assert set(snap["agent"].keys()) == {"x", "y", "energy"}
    assert isinstance(snap["objects"], list)
    assert isinstance(snap["grid_size"], int)
