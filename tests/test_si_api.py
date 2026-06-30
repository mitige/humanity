from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_scenario_run_endpoint():
    body = {"name": "demo", "config": {"n_agents": 2, "world_noise": 0.0},
            "ticks": 5, "seed": 9,
            "interventions": [{"at_tick": 1, "type": "stimulus",
                               "params": {"kind": "food", "intensity": 2.0}}]}
    r = client.post("/scenario/run", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["name"] == "demo" and len(j["series"]["rows"]) == 10 and j["disclaimer"]


def test_battery_endpoints_carry_disclaimer():
    for name in ("mirror", "false_memory", "calibration"):
        r = client.post(f"/battery/{name}", json={"seed": 42, "ticks": 8})
        assert r.status_code == 200
        j = r.json()
        assert j["test"] == name and "not" in j["disclaimer"].lower()


def test_history_and_export():
    client.post("/society/config", json={"n_agents": 1, "world_noise": 0.0})
    client.post("/society/tick")
    assert client.get("/metrics/history?limit=10").status_code == 200
    assert client.get("/export.csv").status_code == 200
    assert client.get("/export.json").status_code == 200
