"""Individuation — the functional "become someone" drive."""
from core.agent import CognitiveAgent
from core.individuation import compute_individuation
from schemas.models import PersonalityState, SelfModelState, SimConfig


def _self(coherence=1.0, confidence=0.5, prefs=None):
    return SelfModelState(identity="X", age_ticks=0, energy=100.0, confidence=confidence,
                          mood=0.0, preferences=(prefs or {"rest": 0.5, "explore": 0.5}),
                          active_goals=[], capability_beliefs={}, coherence=coherence, narrative="")


def _agent(**kw):
    kw.setdefault("world_noise", 0.0)
    kw.setdefault("persist_memory", False)
    kw.setdefault("trace_logging", False)
    return CognitiveAgent(SimConfig(**kw))


# ---- pure index --------------------------------------------------------------

def test_generic_self_has_low_individuation():
    st = compute_individuation(_self(), memory_count=0)
    assert st.distinctiveness == 0.0 and st.continuity == 0.0
    assert 0.0 <= st.index <= 1.0


def test_distinctiveness_and_continuity_raise_the_index():
    plain = compute_individuation(_self(), memory_count=0)
    person = PersonalityState(label="bold", openness=0.95, caution=0.1,
                              novelty_seeking=0.9, vector=[])
    grown = compute_individuation(_self(), personality=person, memory_count=40)
    assert grown.continuity == 1.0
    assert grown.distinctiveness > 0.6
    assert grown.index > plain.index


# ---- config + wiring ---------------------------------------------------------

def test_individuation_off_by_default_and_trace_none():
    assert SimConfig().individuation_enabled is False
    assert _agent().cognitive_cycle().individuation is None


def test_enabling_installs_goal_and_reports_honestly():
    a = _agent(individuation_enabled=True)
    tr = a.cognitive_cycle()
    assert tr.individuation is not None
    assert "become someone" in tr.self_model.active_goals
    assert 0.0 <= tr.individuation.index <= 1.0
    assert "not conscious" in tr.individuation.report.lower() or "not phenomenal" in tr.individuation.report.lower()


def test_drive_adds_individuate_pressure_when_enabled():
    a = _agent(individuation_enabled=True)
    a.cognitive_cycle()
    tr = a.cognitive_cycle()
    needs = {g.need: g.pressure for g in tr.goals}
    assert "individuate" in needs and needs["individuate"] > 0.0


def test_it_grows_into_someone_over_a_life():
    # With a life to accumulate and a personality to diverge, the functional self
    # should measurably individuate over time.
    a = _agent(world_noise=0.15, random_seed=5, individuation_enabled=True,
               personality_enabled=True, agency_enabled=True, curiosity_enabled=True,
               learning_enabled=True)
    early = None
    for i in range(160):
        tr = a.cognitive_cycle()
        if i == 5:
            early = tr.individuation.index
    late = tr.individuation.index
    assert late > early                      # it became more of a someone
    assert late > 0.5


def test_individuation_deterministic_and_off_is_inert():
    # Deterministic with the drive on.
    def idx_run():
        a = _agent(world_noise=0.1, random_seed=3, individuation_enabled=True, personality_enabled=True)
        return [round(a.cognitive_cycle().individuation.index, 6) for _ in range(25)]
    assert idx_run() == idx_run()
    # Flag off: no individuate pressure is ever produced.
    tr = _agent(individuation_enabled=False).cognitive_cycle()
    assert all(g.need != "individuate" for g in tr.goals)
