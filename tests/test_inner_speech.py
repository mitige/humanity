from core.global_workspace import GlobalWorkspace
from core.inner_speech import InnerSpeech
from schemas.models import ConsciousMoment, SimConfig, WorkspaceState


def _moment(source="perception", affect="curiosity", action="explore", awareness=0.8,
            ignited=True):
    return ConsciousMoment(
        tick=1,
        contents=f"Aware of: {source}: object 3; dominant affect: {affect}; action: {action}.",
        ignited=ignited, dominant_source=source, awareness_level=awareness,
        valence=0.1, phi_proxy=0.4, free_energy=0.2, summary="s")


def _ws(winner="perception"):
    return WorkspaceState(ignited=True, threshold=0.3, winner_source=winner,
                          winner_content="x", broadcast_strength=0.6,
                          competition=[], broadcast_vector=[])


def test_condensation_keeps_predicate_drops_subject():
    cfg = SimConfig(inner_speech_enabled=True)
    isp = InnerSpeech()
    state = isp.generate(_moment(), _ws(), cfg)
    assert "curiosity" in state.utterance and "explore" in state.utterance
    assert 0.0 < state.condensation <= 1.0
    assert len(state.utterance) < len(_moment().contents)


def test_utterance_reenters_next_competition():
    cfg = SimConfig(inner_speech_enabled=True, inner_speech_gain=0.8)
    isp = InnerSpeech()
    assert isp.coalition(GlobalWorkspace.make_coalition, cfg) is None   # nothing yet
    isp.generate(_moment(awareness=0.9, ignited=True), _ws(), cfg)
    coal = isp.coalition(GlobalWorkspace.make_coalition, cfg)
    assert coal is not None and coal.source == "inner_speech"
    assert coal.activation > 0.7                    # gain*(floor + awareness + ignition bonus)
    assert "inner speech" in coal.content


def test_reentry_detection_and_count():
    cfg = SimConfig(inner_speech_enabled=True)
    isp = InnerSpeech()
    s1 = isp.generate(_moment(), _ws(winner="perception"), cfg)
    assert s1.reentered is False and s1.reentry_count == 0
    s2 = isp.generate(_moment(), _ws(winner="inner_speech"), cfg)
    assert s2.reentered is True and s2.reentry_count == 1


def test_agent_gating_and_live_reentry():
    from core.agent import CognitiveAgent
    from schemas.models import CognitiveInjection
    base = dict(world_noise=0.1, random_seed=11, persist_memory=False, trace_logging=False)
    off = CognitiveAgent(SimConfig(**base))
    assert off.cognitive_cycle().inner_speech is None
    on = CognitiveAgent(SimConfig(**base, inner_speech_enabled=True, inner_speech_gain=1.0))
    states = []
    for i in range(30):
        if i % 7 == 3:   # salient events: their ignited moments echo loudly
            on.inject(CognitiveInjection(content="vivid danger", source="injection",
                                         activation=0.97, precision=0.97, ttl=1))
        states.append(on.cognitive_cycle().inner_speech)
    assert all(s is not None for s in states)
    assert states[-1].utterance                       # a live condensed report
    # After strongly-ignited moments the re-entrant echo can win global access.
    assert any(s.reentered for s in states)
