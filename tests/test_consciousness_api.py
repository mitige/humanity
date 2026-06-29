"""Tests for the v2 consciousness HTTP endpoints (app.main + app.api.routes).

These exercise the new JSON endpoints through fastapi's TestClient:
``GET /agent/consciousness`` (bound sub-states + disclaimer + framing),
``GET /agent/workspace`` (latest competition), ``GET /agent/stream`` (list of
moments), and the v2 extensions to ``GET /state`` and ``GET /metrics``
(phi_proxy). Collection is skipped gracefully if the web stack is unavailable.
"""
from __future__ import annotations

import pytest

# Skip the whole module gracefully if the optional web stack is not installed.
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path) -> TestClient:
    """A TestClient over a fresh manager with persistence redirected to tmp."""
    import core.agent as agent_module
    from storage.persistence import MemoryStore
    from storage.trace_logger import TraceLogger

    # Reset the process-wide singleton so tests are independent.
    agent_module._MANAGER = None
    manager = agent_module.get_manager()
    manager.agent(0).memory_store = MemoryStore(tmp_path / "memory.json")
    manager.agent(0).memory._store = manager.agent(0).memory_store
    manager.agent(0).trace_logger = TraceLogger(tmp_path / "traces.jsonl")

    with TestClient(app) as c:
        yield c

    agent_module._MANAGER = None


def test_consciousness_endpoint_full_payload(client: TestClient) -> None:
    """GET /agent/consciousness returns all sub-states + disclaimer + framing."""
    # Advance one tick so the bound sub-states are populated.
    client.post("/tick")
    resp = client.get("/agent/consciousness")
    assert resp.status_code == 200
    body = resp.json()

    for key in ("conscious_moment", "attention_schema", "metacognition", "integration"):
        assert key in body
        assert body[key] is not None

    assert "workspace" in body
    assert "ignited" in body["workspace"]

    assert "disclaimer" in body and body["disclaimer"]
    assert "framing" in body and body["framing"]
    # The framing is the good-faith theoretical-attempt statement.
    assert "hard problem" in body["framing"]


def test_workspace_endpoint_returns_coalitions(client: TestClient) -> None:
    """GET /agent/workspace returns the latest competition (WorkspaceState)."""
    client.post("/tick")
    resp = client.get("/agent/workspace")
    assert resp.status_code == 200
    body = resp.json()
    assert "ignited" in body
    assert "competition" in body
    assert isinstance(body["competition"], list)
    # After a tick, at least one specialist coalition bid for the workspace.
    assert len(body["competition"]) >= 1
    assert "broadcast_strength" in body
    assert "threshold" in body


def test_stream_endpoint_returns_list(client: TestClient) -> None:
    """GET /agent/stream returns a JSON list of conscious moments."""
    for _ in range(3):
        client.post("/tick")
    resp = client.get("/agent/stream?limit=20")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 3
    # Each entry is a ConsciousMoment with the documented bound fields.
    first = body[0]
    for key in ("tick", "contents", "ignited", "awareness_level", "phi_proxy"):
        assert key in first


def test_state_includes_phi_proxy_and_framing(client: TestClient) -> None:
    """GET /state carries the v2 phi_proxy summary field and the theory framing."""
    client.post("/tick")
    resp = client.get("/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "phi_proxy" in body
    assert 0.0 <= float(body["phi_proxy"]) <= 1.0
    assert "framing" in body and body["framing"]
    # The metrics block (nested in state) also carries phi_proxy.
    assert "phi_proxy" in body["metrics"]


def test_metrics_endpoint_includes_phi_proxy(client: TestClient) -> None:
    """GET /metrics includes the v2 consciousness fields (phi_proxy et al.)."""
    client.post("/tick")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "phi_proxy" in body
    assert 0.0 <= float(body["phi_proxy"]) <= 1.0
    assert "free_energy" in body
    assert "ignition" in body
    assert "broadcast_strength" in body
    assert "meta_confidence" in body
    assert "awareness_level" in body


def test_consciousness_endpoint_before_any_tick(client: TestClient) -> None:
    """GET /agent/consciousness is well-formed even before any cycle has run."""
    resp = client.get("/agent/consciousness")
    assert resp.status_code == 200
    body = resp.json()
    # Sub-states may be null pre-tick, but the framing/disclaimer must be present.
    assert "framing" in body and body["framing"]
    assert "disclaimer" in body and body["disclaimer"]
    assert "workspace" in body
