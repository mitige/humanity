"""Tests for the FastAPI surface (app.main + app.api.routes).

These exercise the documented JSON endpoints through fastapi's TestClient.
fastapi/httpx are required (see requirements.txt); collection is skipped if the
web stack is unavailable so the rest of the suite still runs.
"""
from __future__ import annotations

import pytest

# Skip the whole module gracefully if the optional web stack is not installed.
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    """A TestClient over a fresh manager with persistence redirected to tmp.

    The module-level singleton is reset so each test starts from a clean agent,
    and the agent's stores are pointed at the temp directory to avoid touching
    the real storage/data files.
    """
    import core.agent as agent_module
    from storage.persistence import MemoryStore
    from storage.trace_logger import TraceLogger

    # Reset the process-wide singleton so tests are independent.
    agent_module._MANAGER = None
    manager = agent_module.get_manager()
    manager.agent.memory_store = MemoryStore(tmp_path / "memory.json")
    manager.agent.memory._store = manager.agent.memory_store
    manager.agent.trace_logger = TraceLogger(tmp_path / "traces.jsonl")

    with TestClient(app) as c:
        yield c

    agent_module._MANAGER = None


def test_state_ok_and_contains_disclaimer(client: TestClient) -> None:
    """GET /state returns 200 and includes a top-level disclaimer."""
    resp = client.get("/state")
    assert resp.status_code == 200
    body = resp.json()
    assert "disclaimer" in body
    assert isinstance(body["disclaimer"], str)
    assert body["disclaimer"]


def test_tick_returns_trace(client: TestClient) -> None:
    """POST /tick advances the simulation and returns a CycleTrace."""
    resp = client.post("/tick")
    assert resp.status_code == 200
    body = resp.json()
    assert "tick" in body
    assert body["tick"] >= 1
    # The trace must carry its key sub-objects.
    for key in ("observation", "decision", "result", "metrics", "introspection"):
        assert key in body


def test_self_model_endpoint(client: TestClient) -> None:
    """GET /agent/self-model returns the self-model state."""
    resp = client.get("/agent/self-model")
    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"] == "Aurora-fn-01"


def test_introspection_endpoint(client: TestClient) -> None:
    """GET /agent/introspection returns an introspection report with disclaimer."""
    resp = client.get("/agent/introspection")
    assert resp.status_code == 200
    body = resp.json()
    assert "disclaimer" in body
    assert body["disclaimer"]


def test_memory_endpoint(client: TestClient) -> None:
    """GET /agent/memory returns a JSON list of records."""
    # Run a few ticks first so there may be stored memories.
    for _ in range(3):
        client.post("/tick")
    resp = client.get("/agent/memory?limit=20")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_metrics_endpoint(client: TestClient) -> None:
    """GET /metrics returns a metrics object."""
    client.post("/tick")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "tick" in body
    assert "energy" in body


def test_goal_endpoint_adds_goal(client: TestClient) -> None:
    """POST /agent/goal adds a goal visible in the returned self-model."""
    resp = client.post("/agent/goal", json={"goal": "explorer la grille"})
    assert resp.status_code == 200
    body = resp.json()
    assert "explorer la grille" in body["active_goals"]


def test_config_endpoint_changes_config(client: TestClient) -> None:
    """POST /config applies a partial patch and reports the new value."""
    resp = client.post("/config", json={"curiosity": 2.5})
    assert resp.status_code == 200
    # The applied config should be reflected somewhere in the response payload.
    text = resp.text
    assert "2.5" in text


def test_run_then_pause(client: TestClient) -> None:
    """POST /run reports running=true; POST /pause reports running=false."""
    run = client.post("/run", json={"tps": 4.0, "max_ticks": 1})
    assert run.status_code == 200
    assert run.json().get("running") is True
    pause = client.post("/pause")
    assert pause.status_code == 200
    assert pause.json().get("running") is False


def test_reset_returns_state(client: TestClient) -> None:
    """POST /reset returns a fresh state payload."""
    client.post("/tick")
    resp = client.post("/reset", json={})
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_trace_endpoint(client: TestClient) -> None:
    """GET /trace returns the recent cognitive-trace export as a list."""
    for _ in range(2):
        client.post("/tick")
    resp = client.get("/trace?limit=50")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
