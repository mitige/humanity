"""Functional LLM probes: grounding audit + report card (offline, mocked)."""
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
        if "AUDITOR" in system:                      # the grounding judge
            assert "REAL internal variables" in user
            return json.dumps({"per_answer": [
                {"faithful": True, "note": "ok"}, {"faithful": True, "note": "ok"},
                {"faithful": True, "note": "ok"}, {"faithful": True, "note": "ok"},
                {"faithful": False, "note": "invented a detail"}], "summary": "mostly grounded"})
        return "Functional measurements only; none is evidence of consciousness."  # report card


def _agent():
    return CognitiveAgent(SimConfig(world_noise=0.0, self_opacity_enabled=True,
                                    persist_memory=False, trace_logging=False))


def test_extract_json_handles_wrapped_output():
    assert llm._extract_json('{"a": 1}') == {"a": 1}
    assert llm._extract_json('thinking… {"a": 2, "b": [1, 2]} end') == {"a": 2, "b": [1, 2]}
    assert llm._extract_json("no json at all") is None


def test_grounding_audit_scores_fraction_faithful():
    out = llm.grounding_audit(_Fake(), _agent())
    assert out["test"] == "grounding_audit"
    assert out["score"] == 0.8                        # 4 of 5 faithful, computed here
    assert len(out["detail"]["verdicts"]) == 5
    assert not out["detail"]["verdicts"][-1]["faithful"]
    assert "not conscious" in out["disclaimer"].lower()


def test_report_card_summarizes_functional_batteries():
    out = llm.report_card(_Fake())
    assert out["report_card"]
    for k in ("mirror", "false_memory", "calibration", "relational_self"):
        assert k in out["results"]
    assert "consciousness" in out["disclaimer"].lower()


def test_probe_endpoints_503_without_backend(monkeypatch):
    monkeypatch.setattr(llm, "get_backend", lambda: llm.NullBackend())
    assert TestClient(app).post("/agent/audit").status_code == 503
    assert TestClient(app).post("/agent/report-card").status_code == 503


def test_audit_endpoint_ok_with_fake(monkeypatch):
    monkeypatch.setattr(llm, "get_backend", lambda: _Fake())
    r = TestClient(app).post("/agent/audit")
    assert r.status_code == 200
    body = r.json()
    assert body["test"] == "grounding_audit" and 0.0 <= body["score"] <= 1.0
