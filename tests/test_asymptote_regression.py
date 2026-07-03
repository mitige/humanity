"""Phase 5 regression lock: all asymptote flags OFF => Phase-1/2/3/4 behaviour
byte-identical (same decisions/energies), new trace sub-objects null, no
facilitation, neutral Phase-5 metrics."""
from core.agent import CognitiveAgent
from schemas.models import SimConfig


def _run(cfg, n=15):
    a = CognitiveAgent(cfg)
    traces = [a.cognitive_cycle() for _ in range(n)]
    return a, traces


def test_all_phase5_flags_off_is_deterministic_and_clean():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, random_seed=55,
                    persist_memory=False, trace_logging=False)
    _, ta = _run(cfg)
    _, tb = _run(cfg)
    assert [t.decision.action for t in ta] == [t.decision.action for t in tb]
    assert [t.result.new_energy for t in ta] == [t.result.new_energy for t in tb]
    last = ta[-1]
    assert last.recurrence is None and last.reality_monitor is None
    assert last.interoception is None and last.temporality is None
    assert last.inner_speech is None and last.phi_ar is None
    assert last.workspace.facilitation_applied == 0.0
    m = last.metrics
    assert m.presence == 0.0 and m.intero_error == 0.0
    assert m.temporal_surprise == 0.0 and m.phi_ar == 0.0 and m.reality_accuracy == 0.0


def test_observational_flags_do_not_change_behaviour():
    """Purely observational mechanisms (recurrence with gain 0 excluded — the
    reality monitor and Φ_AR only READ the cycle) must not alter decisions."""
    base = dict(grid_size=10, n_objects=8, world_noise=0.0, random_seed=55,
                persist_memory=False, trace_logging=False)
    _, plain = _run(SimConfig(**base))
    _, observed = _run(SimConfig(**base, reality_monitor_enabled=True,
                                 phi_ar_enabled=True))
    assert [t.decision.action for t in plain] == [t.decision.action for t in observed]
    assert [t.result.new_energy for t in plain] == [t.result.new_energy for t in observed]
    assert observed[-1].reality_monitor is not None


def test_full_phase5_stack_is_deterministic_and_populated():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.1, random_seed=7,
                    persist_memory=False, trace_logging=False,
                    recurrence_enabled=True, reality_monitor_enabled=True,
                    intero_inference_enabled=True, temporality_enabled=True,
                    inner_speech_enabled=True, phi_ar_enabled=True,
                    priming_enabled=True,
                    imagination_enabled=True, curiosity_enabled=True,
                    agency_enabled=True, self_opacity_enabled=True,
                    individuation_enabled=True)
    _, ta = _run(cfg, 20)
    _, tb = _run(cfg, 20)
    assert [t.decision.action for t in ta] == [t.decision.action for t in tb]
    assert [t.metrics.model_dump() for t in ta] == [t.metrics.model_dump() for t in tb]
    last = ta[-1]
    assert last.recurrence is not None and last.reality_monitor is not None
    assert last.interoception is not None and last.temporality is not None
    assert last.inner_speech is not None


def test_phase5_composes_with_society():
    from core.society import SocietyManager
    cfg = SimConfig(n_agents=3, world_noise=0.1, random_seed=9,
                    persist_memory=False, trace_logging=False,
                    recurrence_enabled=True, intero_inference_enabled=True,
                    temporality_enabled=True, inner_speech_enabled=True)
    m1, m2 = SocietyManager(cfg), SocietyManager(cfg)
    for _ in range(10):
        t1 = m1.tick()
        t2 = m2.tick()
    e1 = [a.energy for a in m1.world.agents.values()]
    e2 = [a.energy for a in m2.world.agents.values()]
    assert e1 == e2                                  # society determinism holds
    assert all(tr.inner_speech is not None for tr in t1)
