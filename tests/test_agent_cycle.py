"""Integration tests for core.agent.CognitiveAgent (full cognitive cycle)."""
from __future__ import annotations

import pytest

from core.agent import CognitiveAgent
from core.constants import ENERGY_CAP_FACTOR
from core.introspection import DISCLAIMER_EN
from schemas.models import (
    ActionType,
    CycleTrace,
    IntrospectionReport,
    Metrics,
    SimConfig,
)
from storage.persistence import MemoryStore
from storage.trace_logger import TraceLogger


@pytest.fixture()
def agent(tmp_path) -> CognitiveAgent:
    """A CognitiveAgent whose persistence is redirected to a temp directory."""
    cfg = SimConfig(random_seed=42, world_noise=0.0)
    ag = CognitiveAgent(cfg)
    # Redirect file-writing stores so tests stay isolated and deterministic.
    ag.memory_store = MemoryStore(tmp_path / "memory.json")
    ag.memory._store = ag.memory_store
    ag.trace_logger = TraceLogger(tmp_path / "traces.jsonl")
    return ag


def test_cognitive_cycle_returns_valid_trace(agent: CognitiveAgent) -> None:
    """One cycle returns a CycleTrace with every sub-object populated."""
    trace = agent.cognitive_cycle()
    assert isinstance(trace, CycleTrace)
    assert trace.tick == 1
    assert trace.observation is not None
    assert trace.prediction is not None
    assert isinstance(trace.decision.action, ActionType)
    assert trace.result is not None
    assert trace.emotion is not None
    assert trace.self_model is not None
    assert isinstance(trace.introspection, IntrospectionReport)
    assert isinstance(trace.metrics, Metrics)
    assert isinstance(trace.goals, list)


def test_introspection_carries_disclaimer(agent: CognitiveAgent) -> None:
    """The introspection report always carries the canonical EN disclaimer."""
    trace = agent.cognitive_cycle()
    assert trace.introspection.disclaimer == DISCLAIMER_EN


def test_multiple_cycles_keep_energy_in_bounds(agent: CognitiveAgent) -> None:
    """Across many cycles energy stays within [0, initial * cap factor]."""
    cap = agent.config.initial_energy * ENERGY_CAP_FACTOR
    for _ in range(30):
        trace = agent.cognitive_cycle()
        assert 0.0 <= trace.result.new_energy <= cap + 1e-6


def test_tick_increments_monotonically(agent: CognitiveAgent) -> None:
    """The trace tick increments by one per cycle."""
    ticks = [agent.cognitive_cycle().tick for _ in range(10)]
    assert ticks == list(range(1, 11))


def test_memory_count_monotonic_non_decreasing(agent: CognitiveAgent) -> None:
    """Autobiographical memory count never decreases across cycles."""
    counts = []
    for _ in range(20):
        agent.cognitive_cycle()
        counts.append(agent.memory.count())
    assert all(counts[i] <= counts[i + 1] for i in range(len(counts) - 1))


def test_metrics_reflects_latest_tick(agent: CognitiveAgent) -> None:
    """agent.metrics() returns metrics for the most recent tick."""
    for _ in range(3):
        agent.cognitive_cycle()
    metrics = agent.metrics()
    assert isinstance(metrics, Metrics)
    assert metrics.tick == agent.world.tick == 3


def test_introspect_regenerates_report(agent: CognitiveAgent) -> None:
    """introspect() returns a fresh IntrospectionReport from current state."""
    agent.cognitive_cycle()
    report = agent.introspect()
    assert isinstance(report, IntrospectionReport)
    assert report.disclaimer == DISCLAIMER_EN


def test_set_goal_registers_on_self_model(agent: CognitiveAgent) -> None:
    """set_goal surfaces in the self-model state."""
    agent.set_goal("explorer la grille")
    state = agent.self_model_state()
    assert "explorer la grille" in state.active_goals


def test_reset_restores_initial_tick(agent: CognitiveAgent) -> None:
    """reset() rebuilds the agent so the world tick returns to zero."""
    for _ in range(5):
        agent.cognitive_cycle()
    assert agent.world.tick == 5
    agent.reset()
    assert agent.world.tick == 0


def test_apply_config_merges_patch(agent: CognitiveAgent) -> None:
    """apply_config merges a partial patch into the live config."""
    new_cfg = agent.apply_config({"curiosity": 2.5})
    assert new_cfg.curiosity == pytest.approx(2.5)
    assert agent.config.curiosity == pytest.approx(2.5)


def test_world_snapshot_shape(agent: CognitiveAgent) -> None:
    """world_snapshot returns the documented serializable structure."""
    snap = agent.world_snapshot()
    assert set(snap.keys()) >= {"grid_size", "tick", "agent", "objects"}
