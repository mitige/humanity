# tests/test_phase7_api.py
"""Phase 7 — the horizon: API surface tests.

Covers the new config flags roundtrip, the trace sub-objects over /tick and
/agent/consciousness, semantic memory search + graph, the richer trace export
(filters + formats + analysis), and the extended coverage roster.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

PHASE7_FLAGS = [
    "phi_causal_enabled", "hierarchy_enabled", "planning_enabled",
    "vector_memory_enabled", "td_learning_enabled", "mind_wandering_enabled",
    "world_dynamics_enabled", "tasks_enabled",
]


@pytest.fixture()
def client(tmp_path) -> TestClient:
    import core.agent as agent_module
    from storage.persistence import MemoryStore
    from storage.trace_logger import TraceLogger

    agent_module._MANAGER = None
    manager = agent_module.get_manager()
    manager.agent(0).memory_store = MemoryStore(tmp_path / "memory.json")
    manager.agent(0).memory._store = manager.agent(0).memory_store
    manager.agent(0).trace_logger = TraceLogger(tmp_path / "traces.jsonl")

    with TestClient(app) as c:
        yield c

    agent_module._MANAGER = None


def test_config_accepts_phase7_flags(client: TestClient):
    payload = {flag: True for flag in PHASE7_FLAGS}
    payload.update({"planning_horizon": 3, "phi_causal_nodes": 4,
                    "season_period": 100, "td_lambda": 0.7})
    r = client.post("/config", json=payload)
    assert r.status_code == 200
    cfg = r.json()["config"]
    for flag in PHASE7_FLAGS:
        assert cfg[flag] is True, flag
    assert cfg["phi_causal_nodes"] == 4


def test_tick_exposes_phase7_sub_objects_when_enabled(client: TestClient):
    client.post("/config", json={flag: True for flag in PHASE7_FLAGS})
    trace = None
    for _ in range(6):
        r = client.post("/tick")
        assert r.status_code == 200
        trace = r.json()
    assert trace["hierarchy"] is not None
    assert trace["planning"] is not None
    assert trace["semantic_memory"] is not None
    assert trace["wandering"] is not None
    assert trace["task"] is not None
    consc = client.get("/agent/consciousness").json()
    for key in ("phi_causal", "hierarchy", "planning", "semantic_memory",
                "wandering", "task"):
        assert key in consc, key


def test_tick_phase7_sub_objects_none_when_disabled(client: TestClient):
    r = client.post("/tick")
    assert r.status_code == 200
    trace = r.json()
    for key in ("phi_causal", "hierarchy", "planning", "semantic_memory",
                "wandering", "task"):
        assert trace[key] is None, key


def test_memory_search_and_graph(client: TestClient):
    # Generate some episodes first.
    for _ in range(12):
        client.post("/tick")
    r = client.get("/agent/memory/search", params={"q": "explore danger", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["query"] == "explore danger"
    assert "disclaimer" in body
    for hit in body["results"]:
        assert "similarity" in hit and "summary" in hit
    g = client.get("/agent/memory/graph", params={"limit": 30, "edges": 2})
    assert g.status_code == 200
    graph = g.json()
    assert "nodes" in graph and "edges" in graph and "disclaimer" in graph
    for edge in graph["edges"]:
        assert {"source", "target", "similarity"} <= set(edge)


def test_export_traces_filters_and_formats(client: TestClient):
    for _ in range(8):
        client.post("/tick")
    r = client.get("/export/traces", params={"fmt": "jsonl", "limit": 5,
                                             "fields": "tick,metrics"})
    assert r.status_code == 200
    lines = [ln for ln in r.text.splitlines() if ln.strip()]
    assert 0 < len(lines) <= 5
    import json as _json
    row = _json.loads(lines[0])
    assert "tick" in row and "metrics" in row and "decision" not in row

    r_csv = client.get("/export/traces", params={"fmt": "csv", "limit": 5,
                                                 "fields": "tick,metrics"})
    assert r_csv.status_code == 200
    header = r_csv.text.splitlines()[0]
    assert "metrics.prediction_error" in header

    r_json = client.get("/export/traces", params={"fmt": "json", "from_tick": 3})
    assert r_json.status_code == 200
    body = r_json.json()
    assert all(row["tick"] >= 3 for row in body["rows"])


def test_export_analysis(client: TestClient):
    for _ in range(6):
        client.post("/tick")
    r = client.get("/export/analysis")
    assert r.status_code == 200
    body = r.json()
    for key in ("n_traces", "ignition_rate", "action_histogram",
                "mean_prediction_error", "disclaimer"):
        assert key in body, key
    assert body["n_traces"] >= 6


def test_coverage_includes_phase7_mechanisms(client: TestClient):
    r = client.get("/agent/coverage")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 33
    theories = " ".join(item["theory"] for item in body["items"])
    assert "causal" in theories.lower()
    assert "mind-wandering" in theories.lower() or "default mode" in theories.lower()
    # Flags off => the Phase-7 entries are inactive by default. (Only the
    # consciousness-mechanism flags appear in the roster: world_dynamics and
    # tasks are environment features, deliberately not roster entries.)
    inactive = [i for i in body["items"] if i["flag"] in PHASE7_FLAGS]
    assert inactive and all(not i["active"] for i in inactive)
    # Enable them all => active.
    client.post("/config", json={flag: True for flag in PHASE7_FLAGS})
    body2 = client.get("/agent/coverage").json()
    active2 = [i for i in body2["items"] if i["flag"] in PHASE7_FLAGS]
    assert active2 and all(i["active"] for i in active2)
    assert body2["active_count"] == body["active_count"] + len(inactive)


def test_checkpoint_roundtrip_with_phase7_state(client: TestClient, tmp_path):
    client.post("/config", json={flag: True for flag in PHASE7_FLAGS})
    for _ in range(5):
        client.post("/tick")
    r = client.post("/checkpoint/save", json={"name": "p7-test"})
    assert r.status_code == 200
    for _ in range(3):
        client.post("/tick")
    r2 = client.post("/checkpoint/load", json={"name": "p7-test"})
    assert r2.status_code == 200
    client.post("/checkpoint/delete", json={"name": "p7-test"})
