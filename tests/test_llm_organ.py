"""The LLM language organ — converse / biography / cross-examine / inner voice.

Offline: a fake backend stands in for OpenRouter. These features render REAL
variables into richer language; the tests lock the grounding discipline (state
in the prompt, strict system rules, disclaimers, no loop mutation except the
explicit inner-voice re-entry hook).
"""
import json

import pytest
from fastapi.testclient import TestClient

import core.llm as llm
from app.main import app
from core.agent import CognitiveAgent
from schemas.models import SimConfig


class _Organ(llm.LLMBackend):
    """Routes canned replies by which system prompt is in use."""
    model = "fake/nemotron"

    def __init__(self):
        self.calls = []

    def available(self) -> bool:
        return True

    def complete(self, system: str, user: str, **kw) -> str:
        self.calls.append((system, user))
        if system == llm.CONVERSE_SYSTEM:
            return "Based on my variables, my attention is on the workspace winner."
        if system == llm.BIOGRAPHER_SYSTEM:
            return "Chapter I — First ticks. I observed, and learned to rest."
        if system == llm.CROSS_EXAMINER_SYSTEM:
            return json.dumps({"case_for": "It implements global access and recurrence.",
                               "case_against": "Access is not phenomenality.",
                               "verdict": "Undecidable in principle."})
        if system == llm.INNER_VOICE_SYSTEM:
            return "danger near — keep watching."
        return "generic"


def _agent(**flags):
    return CognitiveAgent(SimConfig(world_noise=0.0, random_seed=42,
                                    persist_memory=False, trace_logging=False, **flags))


def test_narration_state_includes_phase5_when_enabled():
    a = _agent(intero_inference_enabled=True, temporality_enabled=True,
               reality_monitor_enabled=True, inner_speech_enabled=True)
    for _ in range(4):
        a.cognitive_cycle()
    st = llm.build_narration_state(a)
    for key in ("interoception", "temporality", "reality_monitoring", "inner_speech"):
        assert key in st, key
    json.dumps(st)


def test_converse_is_grounded_and_carries_the_rules():
    a = _agent()
    a.cognitive_cycle()
    b = _Organ()
    out = llm.converse(b, a, "What are you attending to?",
                       history=[{"role": "interviewer", "content": "hello"}])
    assert out["answer"].startswith("Based on my variables")
    system, user = b.calls[-1]
    assert "NEVER claim to be conscious" in system          # the rule is load-bearing
    assert "REAL internal variables" in user                # the state is in the prompt
    assert "template-based answer" in user                  # the agent's own report too
    assert "Recent conversation" in user                    # history folded in
    assert out["grounding"]["template_answer"]["answer"]
    assert "not" in out["disclaimer"].lower()


def test_biography_aggregates_real_records():
    a = _agent()
    for _ in range(10):
        a.cognitive_cycle()
    facts = llm._biography_facts(a)
    assert facts["n_memories"] == len(a.memory._records)
    assert sum(facts["action_counts"].values()) == facts["n_memories"]
    assert all(e["summary"] is not None for e in facts["episodes"])
    out = llm.biography(_Organ(), a)
    assert out["biography"].startswith("Chapter I")
    assert out["grounding"]["n_episodes_provided"] == len(facts["episodes"])


def test_cross_examine_parses_structured_verdict():
    a = _agent()
    a.cognitive_cycle()
    out = llm.cross_examine(_Organ(), a)
    assert out["case_for"] and out["case_against"]
    assert "Undecidable" in out["verdict"]
    assert "/" in out["grounding"]["coverage"]
    assert set(out["grounding"]["probes"]) >= {
        "masking_signature_of_access", "reality_monitoring_accuracy"}


def test_cross_examine_falls_back_to_raw_text():
    class _Loose(_Organ):
        def complete(self, system, user, **kw):
            return "no json here, just an essay"
    a = _agent()
    a.cognitive_cycle()
    out = llm.cross_examine(_Loose(), a)
    assert out["case_for"] == "no json here, just an essay"
    assert out["verdict"] == ""


def test_inner_voice_enters_the_real_competition():
    a = _agent(inner_speech_enabled=True, inner_speech_gain=1.0)
    for _ in range(3):
        a.cognitive_cycle()
    out = llm.inner_voice(_Organ(), a)
    assert out["utterance"] == "danger near — keep watching."
    assert out["entered"] is True
    # The LLM's words are now the pending re-entrant content: the NEXT
    # competition must contain them as the inner_speech coalition.
    tr = a.cognitive_cycle()
    inner = [c for c in tr.workspace.competition if c.source == "inner_speech"]
    assert inner and "danger near" in inner[0].content


def test_inner_voice_does_not_enter_when_mechanism_off():
    a = _agent()          # inner_speech_enabled defaults False
    a.cognitive_cycle()
    out = llm.inner_voice(_Organ(), a)
    assert out["entered"] is False
    tr = a.cognitive_cycle()
    assert not [c for c in tr.workspace.competition if c.source == "inner_speech"]


def test_endpoints_503_without_backend(monkeypatch):
    monkeypatch.setattr(llm, "get_backend", lambda: llm.NullBackend())
    client = TestClient(app)
    assert client.post("/agent/converse", json={"question": "hi"}).status_code == 503
    assert client.post("/agent/biography").status_code == 503
    assert client.post("/agent/cross-examine").status_code == 503
    assert client.post("/agent/inner-voice").status_code == 503


def test_converse_endpoint_ok_with_fake_backend(monkeypatch):
    monkeypatch.setattr(llm, "get_backend", lambda: _Organ())
    r = TestClient(app).post("/agent/converse",
                             json={"question": "Are you conscious?", "history": []})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] and body["disclaimer"]


@pytest.mark.parametrize("payload", [
    {"question": "   "},
    {"question": "ok", "extra": True},
    {"question": "ok", "history": [{"role": "user", "content": ""}]},
    {"question": "ok", "history": [
        {"role": "user", "content": "x"}
    ] * 7},
    {"question": "ok", "history": [
        {"role": "user", "content": "x", "extra": 1}
    ]},
])
def test_converse_request_is_strictly_bounded(payload, monkeypatch):
    monkeypatch.setattr(llm, "get_backend", lambda: _Organ())
    assert TestClient(app).post("/agent/converse", json=payload).status_code == 422
