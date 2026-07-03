from core.temporality import Temporality
from schemas.models import ConsciousMoment, SimConfig


def _moment(tick, source="perception", valence=0.0):
    return ConsciousMoment(tick=tick, contents=f"Aware of: {source}; dominant affect: x; action: rest.",
                           ignited=True, dominant_source=source, awareness_level=0.5,
                           valence=valence, phi_proxy=0.3, free_energy=0.1, summary="s")


def test_retention_weights_decay_and_specious_width():
    t = Temporality()
    cfg = SimConfig(temporality_enabled=True, retention_horizon=4)
    stream = [_moment(i) for i in range(6)]
    state = t.update(stream, cfg)
    assert len(state.retained) == 4
    weights = [r.weight for r in state.retained]
    assert weights == sorted(weights, reverse=True)      # nearer past lingers more
    assert 1.0 < state.specious_width <= 1.0 + sum(weights) + 1e-9
    # the most recent retained moment is the immediately preceding one
    assert state.retained[0].tick == 4


def test_protention_predicts_modal_source_and_scores_violation():
    t = Temporality()
    cfg = SimConfig(temporality_enabled=True, protention_window=4)
    stream = [_moment(i, source="memory") for i in range(4)]
    s1 = t.update(stream, cfg)
    assert s1.protended_source == "memory"
    assert s1.protention_error is None                    # nothing to score yet
    # Next moment matches the protention: low violation.
    stream.append(_moment(4, source="memory"))
    s2 = t.update(stream, cfg)
    assert s2.protention_error is not None and s2.protention_error < 0.2
    # Then the stream pivots: violation spikes.
    stream.append(_moment(5, source="perception", valence=0.8))
    s3 = t.update(stream, cfg)
    assert s3.protention_error > 0.5


def test_agent_gating_and_arousal_coupling():
    from core.agent import CognitiveAgent
    base = dict(world_noise=0.1, random_seed=42, persist_memory=False, trace_logging=False)
    off = CognitiveAgent(SimConfig(**base))
    assert off.cognitive_cycle().temporality is None
    on = CognitiveAgent(SimConfig(**base, temporality_enabled=True))
    states = [on.cognitive_cycle().temporality for _ in range(8)]
    assert all(s is not None for s in states)
    assert states[-1].specious_width > 1.0                # a thick present
    # First tick has no prior protention; later ones are scored.
    assert states[0].protention_error is None
    assert any(s.protention_error is not None for s in states[1:])
    # The queued surprise is consumed by the next arousal update (reset to 0).
    assert on._pending_temporal_surprise == 0.0 or on.last_trace.temporality.protention_error is not None


def test_metrics_temporal_surprise_field():
    from core.agent import CognitiveAgent
    cfg = SimConfig(world_noise=0.1, random_seed=7, persist_memory=False,
                    trace_logging=False, temporality_enabled=True)
    a = CognitiveAgent(cfg)
    for _ in range(6):
        tr = a.cognitive_cycle()
    expected = tr.temporality.protention_error or 0.0
    assert tr.metrics.temporal_surprise == round(float(expected), 4)
