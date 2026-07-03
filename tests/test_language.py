"""Phase 6 — the invention of language (deterministic naming games)."""
from core.language import Lexicon, society_language_summary
from core.society import SocietyManager
from schemas.models import SimConfig


# ------------------------------------------------------------------ lexicon
def test_invention_is_deterministic_and_agent_specific():
    a1, a2 = Lexicon(1), Lexicon(1)
    b = Lexicon(2)
    w1 = a1.speak("food")["word"]
    w2 = a2.speak("food")["word"]
    wb = b.speak("food")["word"]
    assert w1 == w2                     # same agent id + history => same word
    assert w1 != wb                     # different agents coin different words
    assert w1.isalpha() and 4 <= len(w1) <= 6


def test_hearing_aligns_two_lexicons():
    speaker, hearer = Lexicon(0), Lexicon(1)
    word = speaker.speak("hazard")["word"]
    first = hearer.hear(word, "hazard", sender_id=0)
    assert first.understood is False    # no convention yet
    assert hearer.word_for("hazard") == word   # adopted
    again = hearer.hear(word, "hazard", sender_id=0)
    assert again.understood is True     # convention settled
    assert hearer.success_rate > 0.0


def test_synonym_and_homonym_inhibition():
    lex = Lexicon(3)
    lex.speak("food")
    own = lex.word_for("food")
    # A rival synonym heard repeatedly displaces the weaker word...
    for _ in range(6):
        lex.hear("zaza", "food", sender_id=9)
    assert lex.word_for("food") == "zaza"
    # ...and a word reinforced on one meaning cannot keep colonizing another.
    for _ in range(8):
        lex.hear("zaza", "hazard", sender_id=9)
    strengths = {m: w for (m, w) in lex._strengths}
    assert lex.word_for("hazard") == "zaza"
    assert lex.word_for("food") != "zaza" or lex._strengths.get(("food", "zaza"), 0) < \
        lex._strengths.get(("hazard", "zaza"), 1)


def test_no_context_no_update():
    lex = Lexicon(4)
    heard = lex.hear("bobo", None, sender_id=1)
    assert heard.inferred_meaning is None
    assert lex.vocabulary() == {}
    assert lex.deficit() == 1.0


def test_deficit_falls_as_conventions_settle():
    lex = Lexicon(5)
    start = lex.deficit()
    lex.speak("food")
    for _ in range(10):
        lex.hear(lex.word_for("food"), "food", sender_id=2)
    assert lex.deficit() < start


def test_urge_is_periodic():
    lex = Lexicon(6)
    assert lex.urge == 1.0              # full at birth
    lex.speak("curio")
    assert lex.urge == 0.0              # resets after speaking
    for _ in range(lex.URGE_PERIOD):
        lex.state()                     # each tick rebuilds it
    assert lex.urge == 1.0


# ------------------------------------------------------------------ agent
def test_flag_off_is_clean_and_deterministic():
    from core.agent import CognitiveAgent
    cfg = SimConfig(world_noise=0.0, random_seed=55, persist_memory=False,
                    trace_logging=False)
    a, b = CognitiveAgent(cfg), CognitiveAgent(cfg)
    sa = [a.cognitive_cycle().decision.action for _ in range(12)]
    sb = [b.cognitive_cycle().decision.action for _ in range(12)]
    assert sa == sb
    assert a.last_trace.language is None
    assert a.last_trace.metrics.vocabulary_size == 0
    assert "invent a language" not in a.self_model.snapshot().active_goals


def test_flag_on_installs_goal_and_trace():
    from core.agent import CognitiveAgent
    a = CognitiveAgent(SimConfig(world_noise=0.0, random_seed=55, persist_memory=False,
                                 trace_logging=False, language_drive_enabled=True))
    tr = a.cognitive_cycle()
    assert "invent a language" in a.self_model.snapshot().active_goals
    assert tr.language is not None
    assert any(g.need == "language" for g in tr.goals)


def test_solo_agent_rehearses_naming():
    from core.agent import CognitiveAgent
    from schemas.models import ActionType
    a = CognitiveAgent(SimConfig(world_noise=0.0, random_seed=55, persist_memory=False,
                                 trace_logging=False, language_drive_enabled=True))
    spoke = False
    for _ in range(60):
        tr = a.cognitive_cycle()
        if tr.decision.action == ActionType.VERBALIZE and tr.language.utterance:
            spoke = True
            break
    assert spoke, "solo agent never rehearsed a name in 60 ticks"
    assert a.lexicon.vocabulary()


# ------------------------------------------------------------------ society
def _society(seed=42, ticks=200, drive=True):
    mgr = SocietyManager(SimConfig(
        n_agents=4, world_noise=0.1, random_seed=seed,
        grid_size=10, comm_radius=8, satiation_enabled=True,
        persist_memory=False, trace_logging=False,
        language_drive_enabled=drive))
    for _ in range(ticks):
        mgr.tick()
    return mgr


def test_language_emerges_in_a_society():
    mgr = _society()
    s = mgr.language_summary()
    assert s["n_meanings_named"] >= 2
    assert s["convergence"] is not None and s["convergence"] > 0.5
    assert any(ag.lexicon.success_rate > 0.5 for ag in mgr.agents.values())
    # messages actually carried invented words
    assert any(tr.language and tr.language.n_exchanges > 0
               for ag in mgr.agents.values() for tr in [ag.last_trace])


def test_no_language_without_the_drive():
    mgr = _society(drive=False)
    s = mgr.language_summary()
    assert s["n_meanings_named"] == 0 and s["convergence"] is None
    assert all(ag.last_trace.language is None for ag in mgr.agents.values())


def test_genesis_is_deterministic():
    s1 = _society(ticks=120).language_summary()
    s2 = _society(ticks=120).language_summary()
    assert s1 == s2


def test_society_summary_shape():
    s = _society(ticks=120).language_summary()
    for meaning, d in s["dictionary"].items():
        assert set(d) >= {"modal_word", "agreement", "speakers", "variants", "by_agent"}
    assert "distinct_modal_words" in s


# ------------------------------------------------------------------ battery + api
def test_language_genesis_battery():
    from core.test_battery import ConsciousnessTestBattery
    r = ConsciousnessTestBattery().language_genesis_test(seed=42, ticks=120)
    assert r.test == "language_genesis"
    assert r.score > 0.5                                  # a lexicon emerged
    assert r.detail["drive_off"]["n_meanings_named"] == 0  # and not without the drive
    assert "not" in r.disclaimer.lower()


def test_language_api():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.post("/config", json={"language_drive_enabled": True})
    assert r.status_code == 200 and r.json()["config"]["language_drive_enabled"] is True
    try:
        client.post("/tick")
        lang = client.get("/society/language")
        assert lang.status_code == 200
        j = lang.json()
        assert "dictionary" in j and "convergence" in j and j["disclaimer"]
        c = client.get("/agent/consciousness").json()
        assert "language" in c
    finally:
        client.post("/config", json={"language_drive_enabled": False})
