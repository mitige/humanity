"""Tests for the v2 cognitive cycle wiring in ``core.agent.CognitiveAgent``.

These exercise the rewired ``cognitive_cycle()``: it returns a CycleTrace whose
five consciousness sub-objects (workspace / attention_schema / metacognition /
conscious_moment / integration) are all populated and valid; the stream is
bounded by ``config.stream_length``; and the metrics carry the v2 consciousness
fields (phi_proxy / free_energy / ignition).
"""
from __future__ import annotations

import pytest

from core.agent import CognitiveAgent
from schemas.models import (
    AttentionSchemaState,
    ConsciousMoment,
    CycleTrace,
    IntegrationState,
    MetacognitiveState,
    SimConfig,
    WorkspaceState,
)
from storage.persistence import MemoryStore
from storage.trace_logger import TraceLogger


@pytest.fixture()
def agent(tmp_path) -> CognitiveAgent:
    """A CognitiveAgent with persistence redirected to a temp directory."""
    cfg = SimConfig(random_seed=42, world_noise=0.0, stream_length=5)
    ag = CognitiveAgent(cfg)
    ag.memory_store = MemoryStore(tmp_path / "memory.json")
    ag.memory._store = ag.memory_store
    ag.trace_logger = TraceLogger(tmp_path / "traces.jsonl")
    return ag


def test_cycle_populates_all_consciousness_sub_objects(agent: CognitiveAgent) -> None:
    """One cycle returns a CycleTrace with all five v2 sub-objects populated."""
    trace = agent.cognitive_cycle()
    assert isinstance(trace, CycleTrace)

    assert isinstance(trace.workspace, WorkspaceState)
    assert isinstance(trace.attention_schema, AttentionSchemaState)
    assert isinstance(trace.metacognition, MetacognitiveState)
    assert isinstance(trace.conscious_moment, ConsciousMoment)
    assert isinstance(trace.integration, IntegrationState)


def test_cycle_sub_objects_are_valid_and_bounded(agent: CognitiveAgent) -> None:
    """The bound sub-objects carry valid, bounded values (phi & awareness in [0,1])."""
    trace = agent.cognitive_cycle()

    cm = trace.conscious_moment
    assert 0.0 <= cm.phi_proxy <= 1.0
    assert 0.0 <= cm.awareness_level <= 1.0
    assert -1.0 <= cm.valence <= 1.0
    assert cm.tick == trace.tick
    assert isinstance(cm.ignited, bool)
    assert cm.contents

    integ = trace.integration
    assert 0.0 <= integ.phi_proxy <= 1.0
    assert 0.0 <= integ.differentiation <= 1.0
    assert 0.0 <= integ.integration <= 1.0

    asch = trace.attention_schema
    assert 0.0 <= asch.awareness_level <= 1.0
    assert 0.0 <= asch.stability <= 1.0

    mc = trace.metacognition
    assert 0.0 <= mc.meta_confidence <= 1.0

    ws = trace.workspace
    assert 0.0 <= ws.broadcast_strength <= 1.0
    assert isinstance(ws.ignited, bool)


def test_conscious_moment_consistency_with_workspace(agent: CognitiveAgent) -> None:
    """The bound moment mirrors the workspace ignition + attention awareness level."""
    trace = agent.cognitive_cycle()
    assert trace.conscious_moment.ignited == trace.workspace.ignited
    assert trace.conscious_moment.awareness_level == trace.attention_schema.awareness_level
    assert trace.conscious_moment.phi_proxy == trace.integration.phi_proxy


def test_stream_length_is_bounded_by_config(agent: CognitiveAgent) -> None:
    """Over many cycles, the stream length never exceeds config.stream_length."""
    for _ in range(10):
        agent.cognitive_cycle()
    # stream_length was set to 5 in the fixture.
    stream = agent.stream(100)
    assert len(stream) == agent.config.stream_length == 5
    assert all(isinstance(m, ConsciousMoment) for m in stream)
    # The stream holds the most recent moments (ticks 6..10), in order.
    ticks = [m.tick for m in stream]
    assert ticks == sorted(ticks)
    assert ticks[-1] == 10


def test_metrics_include_consciousness_fields(agent: CognitiveAgent) -> None:
    """Trace metrics carry the v2 consciousness fields with valid values."""
    trace = agent.cognitive_cycle()
    metrics = trace.metrics
    assert 0.0 <= metrics.phi_proxy <= 1.0
    assert isinstance(metrics.free_energy, float)
    assert isinstance(metrics.ignition, bool)
    assert 0.0 <= metrics.broadcast_strength <= 1.0
    assert 0.0 <= metrics.meta_confidence <= 1.0
    assert 0.0 <= metrics.awareness_level <= 1.0
    # The cycle's free energy equals the chosen prediction's expected free energy.
    assert metrics.free_energy == pytest.approx(
        trace.prediction.expected_free_energy, abs=1e-4
    )


def test_consciousness_state_accessor_populated(agent: CognitiveAgent) -> None:
    """consciousness_state() returns the bound sub-states after a cycle."""
    agent.cognitive_cycle()
    state = agent.consciousness_state()
    assert state["conscious_moment"] is not None
    assert state["attention_schema"] is not None
    assert state["metacognition"] is not None
    assert state["integration"] is not None
    assert "ignited" in state["workspace"]
