"""Public Phase-7 compatibility contracts that documentation promises."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from app.main import app
from core.society import SocietyManager
from schemas.models import SimConfig
from storage.trace_export import analysis
from storage.trace_logger import TraceLogger


@pytest.fixture()
def client(tmp_path) -> TestClient:
    import core.agent as agent_module

    manager = SocietyManager(SimConfig(
        n_objects=4,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=True,
    ))
    manager.agent(0).trace_logger = TraceLogger(tmp_path / "traces.jsonl")
    agent_module._MANAGER = manager
    with TestClient(app) as test_client:
        yield test_client
    manager.pause()
    agent_module._MANAGER = None


def test_documented_trace_format_is_canonical_and_fmt_stays_compatible(client) -> None:
    for _ in range(3):
        assert client.post("/tick").status_code == 200

    canonical = client.get(
        "/export/traces",
        params={"format": "csv", "fmt": "json", "fields": "tick,metrics"},
    )
    legacy = client.get("/export/traces", params={"fmt": "csv", "fields": "tick"})

    assert canonical.status_code == 200
    assert canonical.headers["content-type"].startswith("text/csv")
    assert "metrics.prediction_error" in canonical.text.splitlines()[0]
    assert legacy.status_code == 200
    assert legacy.headers["content-type"].startswith("text/csv")


@pytest.mark.parametrize("alias, canonical", [
    ("shock", "choc"),
    ("soothe", "apaisement"),
    ("choc", "choc"),
    ("apaisement", "apaisement"),
    ("surprise", "surprise"),
])
def test_perturbation_aliases_report_the_canonical_applied_effect(
    client, alias: str, canonical: str,
) -> None:
    assert client.post("/tick").status_code == 200
    response = client.post(
        "/agent/perturb", json={"type": alias, "magnitude": 0.5},
    )

    assert response.status_code == 200
    effect = response.json()["effect"]
    assert effect["type"] == canonical
    assert effect["applied"] is True


def test_negative_perturbation_magnitude_is_rejected(client) -> None:
    before = client.get("/state").json()["world"]["agent"]["energy"]
    response = client.post(
        "/agent/perturb", json={"type": "shock", "magnitude": -1},
    )
    after = client.get("/state").json()["world"]["agent"]["energy"]

    assert response.status_code == 422
    assert after == before


def test_trace_analysis_exposes_phi_means_and_maxima(tmp_path) -> None:
    path = tmp_path / "analysis.jsonl"
    rows = [
        {"tick": 1, "metrics": {"phi_ar": 0.2, "phi_causal": 0.1}},
        {"tick": 2, "metrics": {"phi_ar": 0.8, "phi_causal": 0.3}},
        {"tick": 3, "metrics": {"phi_ar": 0.0, "phi_causal": 0.0}},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    report = analysis(path)
    empty = analysis(tmp_path / "missing.jsonl")

    assert report["mean_phi_ar"] == pytest.approx(0.5)
    assert report["max_phi_ar"] == pytest.approx(0.8)
    assert report["mean_phi_causal"] == pytest.approx(0.2)
    assert report["max_phi_causal"] == pytest.approx(0.3)
    assert empty["max_phi_ar"] == 0.0
    assert empty["max_phi_causal"] == 0.0
