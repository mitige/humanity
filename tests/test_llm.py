"""Optional LLM narrator — grounded, additive, offline-testable (no real calls)."""
import json

from fastapi.testclient import TestClient

import core.llm as llm
from app.main import app
from core.agent import CognitiveAgent
from schemas.models import SimConfig


class _Fake(llm.LLMBackend):
    model = "fake/model"

    def available(self) -> bool:
        return True

    def complete(self, system: str, user: str, **kw) -> str:
        assert "conscious_moment" in user          # the real variables are in the prompt
        assert "not" in system.lower()              # the strict "do not claim" system prompt
        return "The variables indicate a low-broadcast, low-arousal moment."


def _agent():
    return CognitiveAgent(SimConfig(world_noise=0.0, self_opacity_enabled=True,
                                    persist_memory=False, trace_logging=False))


def test_build_narration_state_is_grounded_and_jsonable():
    a = _agent()
    a.cognitive_cycle()
    st = llm.build_narration_state(a)
    for k in ("conscious_moment", "global_workspace", "self_model", "affect", "outside_my_control"):
        assert k in st
    json.dumps(st)  # must be JSON-serializable


def test_narrate_uses_backend_and_returns_grounding():
    out = llm.narrate(_Fake(), _agent())
    assert out["narration"].startswith("The variables")
    assert out["model"] == "fake/model"
    assert "conscious_moment" in out["grounding"]


def test_get_backend_is_null_without_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert llm.get_backend().available() is False


def test_narrate_endpoint_503_without_backend(monkeypatch):
    monkeypatch.setattr(llm, "get_backend", lambda: llm.NullBackend())
    r = TestClient(app).post("/agent/narrate")
    assert r.status_code == 503


def test_narrate_endpoint_ok_with_fake_backend(monkeypatch):
    monkeypatch.setattr(llm, "get_backend", lambda: _Fake())
    r = TestClient(app).post("/agent/narrate")
    assert r.status_code == 200
    body = r.json()
    assert body["narration"].startswith("The variables")
    assert "disclaimer" in body and "grounding" in body
