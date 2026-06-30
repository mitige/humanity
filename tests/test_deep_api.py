from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_tick_trace_carries_phase2_when_enabled():
    client.post("/config", json={"circadian_enabled": True, "imagination_enabled": True,
                                 "curiosity_enabled": True, "agency_enabled": True,
                                 "sleep_enabled": True, "world_noise": 0.0})
    body = client.post("/tick").json()
    assert body["circadian"] is not None and body["imagination"] is not None
    assert "daylight" in body["metrics"] and "agency" in body["metrics"]


def test_tick_trace_omits_phase2_by_default():
    client.post("/config", json={"circadian_enabled": False, "imagination_enabled": False,
                                 "curiosity_enabled": False, "agency_enabled": False,
                                 "sleep_enabled": False})
    body = client.post("/tick").json()
    assert body["circadian"] is None and body["agency"] is None
