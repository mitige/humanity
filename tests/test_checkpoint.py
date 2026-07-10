"""Run checkpoints: save / resume the full society state."""
import json
from pathlib import Path

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


def test_checkpoint_after_consumed_food_has_consistent_spawn_metadata(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    manager = _mgr(n_agents=1, n_objects=0, world_dynamics_enabled=False)
    body = manager.world.agents[0]
    food = manager.world.inject_object(
        "food", x=body.x, y=body.y, intensity=1.0)

    manager.world._apply_interact(body, food, [])

    assert food.id not in manager.world.objects
    assert food.id not in manager.world._spawn_meta
    checkpoint.save(manager, "after-meal")
    resumed = _mgr()
    checkpoint.load(resumed, "after-meal")
    assert food.id not in resumed.world.objects


def test_checkpoint_keeps_vector_index_lazy_when_feature_is_off(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    manager = _mgr(
        n_objects=0,
        memory_importance_threshold=0.0,
        vector_memory_enabled=False,
    )
    for _ in range(20):
        manager.tick()
    assert manager.agent(0).memory.count() == 20
    assert manager.agent(0).vector_index.size() == 0

    checkpoint.save(manager, "lazy-vector")
    resumed = _mgr()
    checkpoint.load(resumed, "lazy-vector")

    assert resumed.agent(0).memory.count() == 20
    assert resumed.agent(0).vector_index.size() == 0


def test_checkpoint_resumes_next_phase7_trace_exactly(tmp_path, monkeypatch):
    """Every opt-in Horizon mechanism continues bit-for-bit after a restore."""
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    horizon = {
        "phi_causal_enabled": True,
        "phi_causal_nodes": 3,
        "phi_causal_window": 16,
        "phi_causal_every": 1,
        "hierarchy_enabled": True,
        "planning_enabled": True,
        "vector_memory_enabled": True,
        "td_learning_enabled": True,
        "mind_wandering_enabled": True,
        "world_dynamics_enabled": True,
        "tasks_enabled": True,
    }
    source = _mgr(n_agents=1, n_objects=5, random_seed=73, **horizon)
    for _ in range(24):
        source.tick()
    checkpoint.save(source, "phase7")

    expected = [trace.model_dump() for trace in source.tick()]
    resumed = _mgr(n_agents=1, random_seed=999)
    checkpoint.load(resumed, "phase7")
    actual = [trace.model_dump() for trace in resumed.tick()]

    assert actual == expected
    assert actual[0]["hierarchy"] is not None
    assert actual[0]["planning"] is not None
    assert actual[0]["semantic_memory"] is not None
    assert actual[0]["wandering"] is not None
    assert actual[0]["task"] is not None


def test_list_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    mgr = _mgr()
    checkpoint.save(mgr, "a")
    checkpoint.save(mgr, "b")
    listed = checkpoint.listing()
    assert {"a", "b"} <= {m["name"] for m in listed}
    assert all(m["compatible"] is True for m in listed)
    assert checkpoint.delete("a") is True
    assert "a" not in {m["name"] for m in checkpoint.listing()}
    assert checkpoint.delete("a") is False


def test_load_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        checkpoint.load(_mgr(), "nope")


@pytest.mark.parametrize("name", ["CON", "prn.txt", "AUX", "COM1", "lpt9.log"])
def test_reserved_windows_checkpoint_names_are_made_portable(name):
    assert checkpoint._safe(name).startswith("_")


def test_listing_marks_legacy_checkpoints_incompatible(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    checkpoint.save(_mgr(), "current")
    (tmp_path / "legacy.pkl").write_bytes(b"legacy")
    (tmp_path / "legacy.json").write_text(
        json.dumps({"name": "legacy", "tick": 3}), encoding="utf-8")

    by_name = {item["name"]: item for item in checkpoint.listing()}

    assert by_name["current"]["compatible"] is True
    assert by_name["legacy"]["compatible"] is False


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


def test_failed_checkpoint_overwrite_preserves_both_previous_files(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    manager = _mgr()
    checkpoint.save(manager, "stable")
    pkl = tmp_path / "stable.pkl"
    meta = tmp_path / "stable.json"
    before = (pkl.read_bytes(), meta.read_bytes())

    original_replace = Path.replace

    def fail_metadata_install(self, target):
        if self.name.endswith(".json.tmp"):
            raise OSError("synthetic metadata commit failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_metadata_install)
    manager.tick()

    with pytest.raises(OSError, match="metadata commit"):
        checkpoint.save(manager, "stable")

    assert (pkl.read_bytes(), meta.read_bytes()) == before
    assert not list(tmp_path.glob("*.tmp"))
    assert not list(tmp_path.glob("*.rollback"))


def test_checkpoint_double_fault_retains_metadata_recovery_copy(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    manager = _mgr()
    checkpoint.save(manager, "stable")
    meta = tmp_path / "stable.json"
    old_meta = meta.read_bytes()
    original_replace = Path.replace

    def fail_commit_and_rollback(self, target):
        target_path = Path(target)
        if target_path.name == "stable.json" and (
                self.name.endswith(".json.tmp")
                or self.name.endswith(".rollback")):
            raise OSError("synthetic checkpoint double fault")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_commit_and_rollback)

    with pytest.raises(
            checkpoint.InvalidCheckpointError,
            match="recovery copies were retained"):
        checkpoint.save(manager, "stable")

    recovery = list(tmp_path.glob(".stable.json.*.rollback"))
    assert len(recovery) == 1
    assert recovery[0].read_bytes() == old_meta


def test_checkpoint_restores_managed_memory_and_trace_branch(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from storage.persistence import MemoryStore
    from storage.trace_logger import TraceLogger

    memory_path = tmp_path / "memory.json"
    trace_path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path / "checkpoints")
    monkeypatch.setattr(
        MemoryStore, "for_agent",
        classmethod(lambda cls, agent_id, n_agents: cls(memory_path)),
    )
    monkeypatch.setattr(
        TraceLogger, "for_agent",
        classmethod(lambda cls, agent_id, n_agents: cls(trace_path)),
    )
    manager = _mgr(
        n_agents=1,
        n_objects=0,
        world_noise=0.0,
        memory_importance_threshold=0.0,
        persist_memory=True,
        trace_logging=True,
    )
    manager.tick()
    manager.tick()
    checkpoint.save(manager, "branch")
    saved_records = json.loads(memory_path.read_text(encoding="utf-8"))
    saved_lines = trace_path.read_text(encoding="utf-8").splitlines()

    manager.tick()
    manager.tick()
    assert len(trace_path.read_text(encoding="utf-8").splitlines()) == 4
    checkpoint.load(manager, "branch")

    assert json.loads(memory_path.read_text(encoding="utf-8")) == saved_records
    assert trace_path.read_text(encoding="utf-8").splitlines() == saved_lines

    resumed = _mgr(
        n_agents=1,
        n_objects=0,
        world_noise=0.0,
        memory_importance_threshold=0.0,
        persist_memory=True,
        trace_logging=True,
    )
    assert [record.model_dump(mode="json")
            for record in resumed.agent(0).memory._records] == saved_records

    manager.tick()
    ticks = [json.loads(line)["tick"] for line in
             trace_path.read_text(encoding="utf-8").splitlines()]
    assert ticks == [1, 2, 3]
