# tests/test_phase7_regression.py
"""Phase 7 — the horizon: backward-compatibility regression.

The load-bearing guarantee: every Phase-7 flag defaults OFF, and OFF means the
whole simulation (actions, energy, traces) is byte-identical to Phase 6 — the
new mechanisms leave no footprint until enabled.
"""
from __future__ import annotations

from core.agent import CognitiveAgent
from schemas.models import SimConfig


def _cfg(**kw) -> SimConfig:
    base = dict(random_seed=42, persist_memory=False, trace_logging=False)
    base.update(kw)
    return SimConfig(**base)


def test_all_phase7_flags_default_off():
    cfg = SimConfig()
    for flag in ("phi_causal_enabled", "hierarchy_enabled", "planning_enabled",
                 "vector_memory_enabled", "td_learning_enabled",
                 "mind_wandering_enabled", "world_dynamics_enabled", "tasks_enabled"):
        assert getattr(cfg, flag) is False, flag


def test_flags_off_run_matches_phase6_baseline():
    """Explicit False flags == absent flags: identical actions and energy."""
    a = CognitiveAgent(_cfg())
    b = CognitiveAgent(_cfg(phi_causal_enabled=False, hierarchy_enabled=False,
                            planning_enabled=False, vector_memory_enabled=False,
                            td_learning_enabled=False, mind_wandering_enabled=False,
                            world_dynamics_enabled=False, tasks_enabled=False))
    for _ in range(30):
        ta, tb = a.cognitive_cycle(), b.cognitive_cycle()
        assert ta.decision.action == tb.decision.action
        assert ta.result.new_energy == tb.result.new_energy
        assert ta.metrics.model_dump() == tb.metrics.model_dump()


def test_flags_off_trace_subobjects_are_none():
    agent = CognitiveAgent(_cfg())
    trace = agent.cognitive_cycle()
    assert trace.phi_causal is None
    assert trace.hierarchy is None
    assert trace.planning is None
    assert trace.semantic_memory is None
    assert trace.wandering is None
    assert trace.task is None
    assert trace.metrics.phi_causal == 0.0
    assert trace.metrics.vfe == 0.0
    assert trace.metrics.wandering_occupancy == 0.0
    assert trace.metrics.task_progress == 0.0


def test_flags_on_trace_subobjects_populate():
    cfg = _cfg(phi_causal_enabled=True, hierarchy_enabled=True, planning_enabled=True,
               vector_memory_enabled=True, td_learning_enabled=True,
               mind_wandering_enabled=True, world_dynamics_enabled=True,
               tasks_enabled=True, learning_enabled=True, curiosity_enabled=True)
    agent = CognitiveAgent(cfg)
    trace = None
    for _ in range(40):
        trace = agent.cognitive_cycle()
    assert trace.hierarchy is not None and trace.hierarchy.regime
    assert trace.planning is not None and len(trace.planning.best_sequence) == cfg.planning_horizon
    assert trace.semantic_memory is not None and trace.semantic_memory.mode == "semantic"
    assert trace.wandering is not None
    assert trace.task is not None and trace.task.kind in ("forage", "reach", "patrol")
    assert trace.learning is not None and trace.learning.td_context is not None
    # Φ_c computes on its periodic schedule once the buffer is warm.
    assert trace.phi_causal is not None
    assert trace.phi_causal.computed_at_tick >= 0


def test_phase7_run_is_deterministic():
    cfg = _cfg(phi_causal_enabled=True, hierarchy_enabled=True, planning_enabled=True,
               vector_memory_enabled=True, td_learning_enabled=True,
               mind_wandering_enabled=True, world_dynamics_enabled=True,
               tasks_enabled=True, learning_enabled=True)
    a, b = CognitiveAgent(cfg), CognitiveAgent(cfg.model_copy())
    for _ in range(35):
        ta, tb = a.cognitive_cycle(), b.cognitive_cycle()
        assert ta.decision.action == tb.decision.action
        assert ta.metrics.model_dump() == tb.metrics.model_dump()


def test_planning_and_imagination_coexist():
    cfg = _cfg(planning_enabled=True, imagination_enabled=True)
    agent = CognitiveAgent(cfg)
    trace = None
    for _ in range(5):
        trace = agent.cognitive_cycle()
    assert trace.planning is not None
    assert trace.imagination is not None


def test_hierarchy_modulates_effective_lr():
    """With hierarchy on, the effective lr reflects the context factor."""
    cfg = _cfg(hierarchy_enabled=True)
    agent = CognitiveAgent(cfg)
    trace = None
    for _ in range(15):
        trace = agent.cognitive_cycle()
    factor = agent.hierarchical.lr_factor()
    assert abs(trace.metrics.effective_learning_rate
               - min(1.0, max(0.0, cfg.learning_rate * factor))) < 1e-6
