from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_config_accepts_phase5_flags():
    r = client.post("/config", json={
        "recurrence_enabled": True, "reality_monitor_enabled": True,
        "intero_inference_enabled": True, "temporality_enabled": True,
        "inner_speech_enabled": True, "phi_ar_enabled": True,
        "priming_enabled": True, "recurrence_passes": 4, "phi_ar_every": 4})
    assert r.status_code == 200
    cfg = r.json()["config"]
    for key in ("recurrence_enabled", "reality_monitor_enabled",
                "intero_inference_enabled", "temporality_enabled",
                "inner_speech_enabled", "phi_ar_enabled", "priming_enabled"):
        assert cfg[key] is True
    # Restore defaults for the other tests.
    client.post("/config", json={
        "recurrence_enabled": False, "reality_monitor_enabled": False,
        "intero_inference_enabled": False, "temporality_enabled": False,
        "inner_speech_enabled": False, "phi_ar_enabled": False,
        "priming_enabled": False})


def test_tick_exposes_phase5_sub_objects_when_enabled():
    client.post("/config", json={"temporality_enabled": True,
                                 "inner_speech_enabled": True,
                                 "intero_inference_enabled": True})
    try:
        r = client.post("/tick")
        assert r.status_code == 200
        j = r.json()
        assert j["temporality"] is not None
        assert j["inner_speech"] is not None
        assert j["interoception"] is not None
        r2 = client.get("/agent/consciousness")
        assert r2.status_code == 200
        assert "temporality" in r2.json() and "reality_monitor" in r2.json()
    finally:
        client.post("/config", json={"temporality_enabled": False,
                                     "inner_speech_enabled": False,
                                     "intero_inference_enabled": False})


def test_psychophysics_battery_endpoints():
    for name in ("masking", "blink", "priming"):
        r = client.post(f"/battery/{name}", json={"seed": 42, "ticks": 3})
        assert r.status_code == 200
        j = r.json()
        assert j["test"] == name and j["score"] > 0.5
        assert "not" in j["disclaimer"].lower()
    r = client.post("/battery/reality_monitor", json={"seed": 42, "ticks": 30})
    assert r.status_code == 200
    assert 0.0 <= r.json()["score"] <= 1.0


def test_coverage_endpoint_is_honest_and_reflects_config():
    r = client.get("/agent/coverage")
    assert r.status_code == 200
    j = r.json()
    assert j["total"] >= 20
    assert 0 < j["active_count"] <= j["total"]
    assert "NOT a measure of consciousness" in j["disclaimer"]
    flags = {i["flag"] for i in j["items"]}
    assert "recurrence_enabled" in flags and "phi_ar_enabled" in flags
    # Flip a flag: active count moves with it.
    before = j["active_count"]
    client.post("/config", json={"recurrence_enabled": True})
    try:
        after = client.get("/agent/coverage").json()["active_count"]
        assert after == before + 1
    finally:
        client.post("/config", json={"recurrence_enabled": False})
