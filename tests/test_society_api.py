from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_society_config_then_state_lists_agents():
    client.post("/society/config", json={"n_agents": 3, "random_seed": 4, "world_noise": 0.0})
    client.post("/society/tick")
    body = client.get("/society").json()
    assert body["n_agents"] == 3 and len(body["agents"]) == 3
    assert "relations" in body and "edges" in body["relations"]


def test_society_per_agent_consciousness():
    client.post("/society/config", json={"n_agents": 2, "random_seed": 4})
    client.post("/society/tick")
    r = client.get("/society/agent/1/consciousness")
    assert r.status_code == 200 and "disclaimer" in r.json()


def test_unknown_agent_is_404():
    client.post("/society/config", json={"n_agents": 1, "random_seed": 4})
    assert client.get("/society/agent/99/consciousness").status_code == 404
