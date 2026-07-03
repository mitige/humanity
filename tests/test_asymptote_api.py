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


def test_get_config_returns_live_config():
    r = client.get("/config")
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert "recurrence_enabled" in cfg and "n_agents" in cfg


def test_config_patch_resumes_a_running_loop():
    """A config patch applied mid-run must not kill the run (the /config route
    resumes the loop on the rebuilt society), and in particular the OLD
    cancelled loop's finally must not clobber its successor's running flag.
    Exercised at the manager level (TestClient cannot host a live asyncio
    background loop across requests)."""
    import asyncio

    from core.society import SocietyManager
    from schemas.models import ConfigPatch, RunRequest, SimConfig

    async def scenario():
        mgr = SocietyManager(SimConfig(world_noise=0.0, random_seed=3,
                                       persist_memory=False, trace_logging=False))
        await mgr.run(RunRequest(tps=200.0))
        await asyncio.sleep(0.05)
        assert mgr.running is True
        # What POST /config does: reset, then resume because it was running.
        was_running = bool(mgr.running)
        resume = mgr.last_run_request
        mgr.reset(ConfigPatch(priming_enabled=True))
        assert mgr.running is False          # reset itself pauses...
        if was_running:
            await mgr.run(resume or RunRequest())
        # ...and the resumed loop must SURVIVE the cancelled loop's finally.
        await asyncio.sleep(0.2)
        assert mgr.running is True
        assert mgr.config.priming_enabled is True
        # An explicit pause still pauses for good.
        mgr.pause()
        await asyncio.sleep(0.05)
        assert mgr.running is False

    asyncio.run(scenario())


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
