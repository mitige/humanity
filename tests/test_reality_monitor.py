from core.global_workspace import GlobalWorkspace
from core.reality_monitor import RealityMonitor, actual_category
from schemas.models import SimConfig, WorkspaceState


def _ws(winner_source, coalitions, winner_strength=0.8, ignited=True):
    return WorkspaceState(
        ignited=ignited, threshold=0.3, winner_source=winner_source,
        winner_content=f"{winner_source}: x", broadcast_strength=0.5,
        competition=coalitions, broadcast_vector=[], winner_strength=winner_strength)


def _coal(source, vector, activation=0.5, precision=0.8):
    return GlobalWorkspace.make_coalition(source, f"{source}: x",
                                          activation=activation,
                                          precision=precision, vector=vector)


def test_actual_category_mapping():
    assert actual_category("perception") == "external"
    assert actual_category("memory") == "memory"
    assert actual_category("dream") == "self_generated"
    assert actual_category("inner_speech") == "self_generated"
    assert actual_category("injection") == "foreign"
    assert actual_category(None) == "foreign"


def test_corroborated_percept_judged_external():
    rm = RealityMonitor()
    percept = _coal("perception", [0.8, 0.6, 0.4, 0.3], precision=0.9)
    state = rm.assess(workspace=_ws("perception", [percept]),
                      recent_winners=["perception"] * 4,
                      generation_activity={})
    assert state.judged == "external" and state.actual == "external"
    assert state.correct is True and state.accuracy == 1.0


def test_thin_generated_content_judged_self():
    rm = RealityMonitor()
    percept = _coal("perception", [0.1, 0.9, 0.2, 0.6], precision=0.9)
    dream = _coal("dream", [0.0, 0.0, 0.0, 0.0], activation=0.7, precision=0.5)
    state = rm.assess(workspace=_ws("dream", [dream, percept], winner_strength=0.6),
                      recent_winners=["dream"],
                      generation_activity={"dream": True})
    assert state.actual == "self_generated"
    assert state.judged == "self_generated" and state.correct is True


def test_misattribution_is_possible_and_tallied():
    # A vivid self-generated content whose vector happens to match the current
    # percepts, with no record of generation activity: judged external — the
    # functional hallucination analogue.
    rm = RealityMonitor()
    percept = _coal("perception", [0.9, 0.7, 0.5, 0.4], precision=0.9)
    vivid = _coal("imagination", [0.9, 0.7, 0.5, 0.4], activation=0.95, precision=0.9)
    state = rm.assess(workspace=_ws("imagination", [vivid, percept], winner_strength=0.95),
                      recent_winners=["imagination"] * 5,
                      generation_activity={})
    assert state.actual == "self_generated"
    assert state.judged == "external"
    assert state.correct is False and state.hallucinations == 1
    assert "MISATTRIBUTION" in state.report


def test_foreign_content_not_scored():
    rm = RealityMonitor()
    inj = _coal("injection", [0.9, 0.9, 0.0, 0.0], activation=0.9, precision=0.9)
    state = rm.assess(workspace=_ws("injection", [inj]),
                      recent_winners=["injection"],
                      generation_activity={})
    assert state.actual == "foreign" and state.correct is None


def test_empty_competition_returns_none():
    rm = RealityMonitor()
    assert rm.assess(workspace=WorkspaceState(
        ignited=False, threshold=0.3, winner_source=None, winner_content=None,
        broadcast_strength=0.0, competition=[], broadcast_vector=[]),
        recent_winners=[], generation_activity={}) is None


def test_agent_trace_gating_and_accuracy():
    from core.agent import CognitiveAgent
    base = dict(world_noise=0.1, random_seed=42, persist_memory=False, trace_logging=False)
    off = CognitiveAgent(SimConfig(**base))
    assert off.cognitive_cycle().reality_monitor is None
    on = CognitiveAgent(SimConfig(**base, reality_monitor_enabled=True,
                                  imagination_enabled=True, inner_speech_enabled=True))
    last = None
    for _ in range(20):
        tr = on.cognitive_cycle()
        assert tr.reality_monitor is not None
        last = tr.reality_monitor
    assert 0.0 <= last.accuracy <= 1.0
    assert tr.metrics.reality_accuracy == last.accuracy
