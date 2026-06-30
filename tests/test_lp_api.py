from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_tick_carries_phase3_when_enabled():
    client.post("/config", json={"learning_enabled": True, "concepts_enabled": True,
                                 "meta_learning_enabled": True, "personality_enabled": True,
                                 "world_noise": 0.0})
    body = client.post("/tick").json()
    assert body["learning"] is not None and body["personality"] is not None
    assert "effective_learning_rate" in body["metrics"]


def test_tick_omits_phase3_by_default():
    client.post("/config", json={"learning_enabled": False, "concepts_enabled": False,
                                 "meta_learning_enabled": False, "personality_enabled": False})
    body = client.post("/tick").json()
    assert body["learning"] is None and body["personality"] is None
