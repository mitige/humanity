from core.interoception import InteroceptiveModel
from schemas.models import SimConfig


def test_error_decreases_under_repetition():
    m = InteroceptiveModel()
    cfg = SimConfig(intero_inference_enabled=True, intero_lr=0.5)
    errors = []
    for _ in range(10):
        pe, pf = m.predict("rest")
        st = m.observe("rest", predicted_energy_delta=pe, actual_energy_delta=5.5,
                       predicted_fatigue_delta=pf, actual_fatigue_delta=-0.1,
                       config=cfg)
        errors.append(st.error)
    assert errors[-1] < errors[0]                 # the internal model learns
    assert errors[-1] < 0.05


def test_presence_rises_in_predictable_regime_and_drops_on_surprise():
    m = InteroceptiveModel()
    cfg = SimConfig(intero_inference_enabled=True)
    for _ in range(12):
        pe, pf = m.predict("rest")
        st = m.observe("rest", predicted_energy_delta=pe, actual_energy_delta=5.5,
                       predicted_fatigue_delta=pf, actual_fatigue_delta=-0.1,
                       config=cfg)
    settled = st.presence
    assert settled > 0.8
    # A big unpredicted internal shock: presence must sag.
    pe, pf = m.predict("rest")
    st = m.observe("rest", predicted_energy_delta=pe, actual_energy_delta=-10.0,
                   predicted_fatigue_delta=pf, actual_fatigue_delta=0.6, config=cfg)
    assert st.presence < settled
    assert st.error > 0.5


def test_tables_are_per_action():
    m = InteroceptiveModel()
    cfg = SimConfig(intero_inference_enabled=True, intero_lr=1.0)
    m.observe("rest", predicted_energy_delta=0.0, actual_energy_delta=6.0,
              predicted_fatigue_delta=0.0, actual_fatigue_delta=-0.2, config=cfg)
    assert m.predict("rest") == (6.0, -0.2)
    assert m.predict("move") == (0.0, 0.0)        # unseen action: neutral prior


def test_agent_gating_metrics_and_affect_coupling():
    from core.agent import CognitiveAgent
    base = dict(world_noise=0.0, random_seed=42, persist_memory=False, trace_logging=False)
    off = CognitiveAgent(SimConfig(**base))
    tr = off.cognitive_cycle()
    assert tr.interoception is None and tr.metrics.presence == 0.0
    on = CognitiveAgent(SimConfig(**base, intero_inference_enabled=True))
    for _ in range(10):
        tr = on.cognitive_cycle()
        assert tr.interoception is not None
    assert tr.metrics.presence == tr.interoception.presence
    assert tr.metrics.intero_error == tr.interoception.error
    # In a quiet deterministic world the internal milieu becomes predictable.
    assert tr.interoception.presence > 0.6
