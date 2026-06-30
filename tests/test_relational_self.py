"""Relational self (looking-glass self / social mirror)."""
from core.social_self import reflected_appraisal
from schemas.models import OtherMind, SimConfig


def _other(aid, *, trust=0.5, valence=0.0, familiarity=0.5, seen=10):
    return OtherMind(agent_id=aid, trust=trust, inferred_valence=valence,
                     familiarity=familiarity, last_seen_tick=seen)


# ---- pure reflected_appraisal -------------------------------------------------

def test_no_observers_gives_neutral_inert_self():
    rs = reflected_appraisal([], n_others=0, now_tick=10)
    assert rs.social_presence == 0.0
    assert rs.reflected_appraisal == 0.5
    assert rs.n_observers == 0


def test_stale_or_unfamiliar_observers_are_ignored():
    stale = _other(1, seen=0)                 # last seen 0, now 10, recency 3 -> dropped
    unknown = _other(2, familiarity=0.0)      # never really met -> dropped
    rs = reflected_appraisal([stale, unknown], n_others=2, now_tick=10, recency=3)
    assert rs.n_observers == 0 and rs.social_presence == 0.0


def test_positive_regard_raises_appraisal_and_presence():
    obs = [_other(1, trust=0.9, valence=0.8, seen=10), _other(2, trust=0.8, valence=0.6, seen=9)]
    rs = reflected_appraisal(obs, n_others=3, now_tick=10)
    assert rs.reflected_appraisal > 0.6      # well regarded
    assert rs.n_observers == 2
    assert abs(rs.social_presence - 2 / 3) < 1e-6
    assert rs.regard_consistency > 0.5       # the two agree


def test_distrust_lowers_appraisal():
    obs = [_other(1, trust=0.1, valence=-0.8, seen=10)]
    rs = reflected_appraisal(obs, n_others=2, now_tick=10)
    assert rs.reflected_appraisal < 0.3


# ---- config defaults ----------------------------------------------------------

def test_social_mirror_off_by_default():
    c = SimConfig()
    assert c.social_mirror_enabled is False
    assert c.social_mirror_weight == 0.3


# ---- society wiring -----------------------------------------------------------

def _mgr(**kw):
    from core.society import SocietyManager
    kw.setdefault("world_noise", 0.0)
    kw.setdefault("persist_memory", False)
    kw.setdefault("trace_logging", False)
    return SocietyManager(SimConfig(**kw))


def test_society_feeds_reflected_self_into_self_model():
    mgr = _mgr(n_agents=2, random_seed=1, social_mirror_enabled=True)
    # Agent 1 holds a warm, recent model of agent 0.
    m = mgr.agents[1].theory_of_mind.model_of(0)
    m.trust, m.inferred_valence, m.familiarity = 0.9, 0.8, 0.8
    m.last_seen_tick = int(mgr.world.tick)
    mgr._update_reflected_appraisals()
    rs0 = mgr.agents[0].incoming_appraisal
    assert rs0 is not None and rs0.social_presence > 0.0 and rs0.reflected_appraisal > 0.5
    mgr.tick()  # agent 0 consumes its reflected appraisal
    assert mgr.agents[0].self_model.snapshot().relational_self is not None


def test_isolated_agent_with_mirror_matches_baseline():
    # An isolated agent has no observers => the mirror must change nothing numerically.
    def run(mirror):
        mgr = _mgr(n_agents=1, random_seed=3, social_mirror_enabled=mirror)
        for _ in range(15):
            mgr.tick()
        s = mgr.agents[0].self_model.snapshot()
        return (round(s.confidence, 9), round(s.mood, 9), round(s.coherence, 9))
    assert run(True) == run(False)


def test_society_with_mirror_is_deterministic():
    def run():
        mgr = _mgr(n_agents=3, world_noise=0.1, random_seed=5, social_mirror_enabled=True)
        for _ in range(20):
            mgr.tick()
        return [(round(mgr.agents[a].self_model.snapshot().confidence, 9),
                 round(mgr.agents[a].self_model.snapshot().mood, 9)) for a in sorted(mgr.agents)]
    assert run() == run()


def test_mirror_off_leaves_relational_self_none():
    mgr = _mgr(n_agents=3, random_seed=1)
    for _ in range(8):
        mgr.tick()
    assert all(mgr.agents[a].self_model.snapshot().relational_self is None for a in mgr.agents)


# ---- Phase-4 experiment -------------------------------------------------------

def test_relational_self_battery_probe():
    from core.test_battery import ConsciousnessTestBattery
    r = ConsciousnessTestBattery().relational_self_test(ticks=20)
    assert r.test == "relational_self"
    # The isolated agent develops no social self; the social one does.
    assert r.detail["isolated"]["social_presence"] == 0.0
    assert r.detail["social"]["social_presence"] > 0.0
    assert r.score == max(0.0, r.detail["social"]["social_presence"] - r.detail["isolated"]["social_presence"])
    assert "consciousness" not in r.disclaimer.lower() or "not conscious" in r.disclaimer.lower()
