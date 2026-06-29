from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_legacy_endpoints_still_work():
    client.post("/society/config", json={"n_agents": 1, "random_seed": 1})
    assert client.post("/tick").status_code == 200
    s = client.get("/state").json()
    assert "metrics" in s and "disclaimer" in s
    assert client.get("/agent/self-model").status_code == 200
    assert client.get("/agent/consciousness").status_code == 200
