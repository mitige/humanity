"""Run checkpoints: save / resume the full society state."""
import pytest

import core.checkpoint as checkpoint
from core.society import SocietyManager
from schemas.models import SimConfig


def _mgr(**kw):
    kw.setdefault("world_noise", 0.1)
    kw.setdefault("random_seed", 1)
    kw.setdefault("persist_memory", False)
    kw.setdefault("trace_logging", False)
    return SocietyManager(SimConfig(**kw))


def _fingerprint(mgr):
    out = {}
    for aid, ag in mgr.agents.items():
        s = ag.self_model.snapshot()
        out[aid] = (round(float(s.confidence), 6), round(float(s.energy), 4),
                    {k: round(float(v), 6) for k, v in ag.policy_learner.values().items()})
    return out, int(mgr.world.tick)


def test_save_writes_files_and_sanitizes_name(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    mgr = _mgr(n_agents=2, learning_enabled=True)
    for _ in range(15):
        mgr.tick()
    meta = checkpoint.save(mgr, "my run!")
    assert meta["name"] == "my-run" and meta["tick"] == 15 and meta["n_agents"] == 2
    assert (tmp_path / "my-run.pkl").exists() and (tmp_path / "my-run.json").exists()


def test_load_restores_full_state(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    src = _mgr(n_agents=2, learning_enabled=True, individuation_enabled=True, personality_enabled=True)
    for _ in range(20):
        src.tick()
    checkpoint.save(src, "cp")
    src_fp = _fingerprint(src)
    # load into a fresh, deliberately different manager
    dst = _mgr(n_agents=1, random_seed=999)
    info = checkpoint.load(dst, "cp")
    assert info["tick"] == 20 and info["n_agents"] == 2
    assert _fingerprint(dst) == src_fp
    assert all(ag._shared_world is dst.world for ag in dst.agents.values())


def test_checkpoint_resumes_run_identically(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    mgr = _mgr(n_agents=2, learning_enabled=True, world_noise=0.2, random_seed=7)
    for _ in range(20):
        mgr.tick()
    checkpoint.save(mgr, "cp")
    for _ in range(12):
        mgr.tick()
    continued = _fingerprint(mgr)
    # resume from the checkpoint and run the same 12 ticks — must match bit for bit
    resumed = _mgr(n_agents=1)
    checkpoint.load(resumed, "cp")
    for _ in range(12):
        resumed.tick()
    assert _fingerprint(resumed) == continued


def test_list_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    mgr = _mgr()
    checkpoint.save(mgr, "a")
    checkpoint.save(mgr, "b")
    assert {"a", "b"} <= {m["name"] for m in checkpoint.listing()}
    assert checkpoint.delete("a") is True
    assert "a" not in {m["name"] for m in checkpoint.listing()}
    assert checkpoint.delete("a") is False


def test_load_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        checkpoint.load(_mgr(), "nope")


def test_checkpoint_endpoints(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    c.post("/society/config", json={"n_agents": 2, "world_noise": 0.0,
                                    "persist_memory": False, "trace_logging": False})
    c.post("/train", json={"ticks": 8})
    saved = c.post("/checkpoint/save", json={"name": "api-cp"})
    assert saved.status_code == 200 and saved.json()["tick"] == 8
    assert any(m["name"] == "api-cp" for m in c.get("/checkpoint/list").json()["checkpoints"])
    loaded = c.post("/checkpoint/load", json={"name": "api-cp"})
    assert loaded.status_code == 200 and loaded.json()["tick"] == 8 and "state" in loaded.json()
    assert c.post("/checkpoint/load", json={"name": "ghost"}).status_code == 404
