"""Release-blocking safety regressions for destructive state transitions."""
from __future__ import annotations

import asyncio
import json
import pickle
import threading
import time

import pytest
from fastapi.testclient import TestClient

import core.agent as agent_module
import core.checkpoint as checkpoint
from app.main import app
from core.constants import TASK_FORAGE_COUNT
from core.scenario import ScenarioRunner
from core.society import SocietyManager
from core.test_battery import ConsciousnessTestBattery
from core.world_tasks import TaskManager
from schemas.models import (
    ActionType,
    BatteryResult,
    ConfigPatch,
    EmotionState,
    MemoryRecord,
    SimConfig,
)
from storage.persistence import MemoryStore


class _CancelableTask:
    def __init__(self) -> None:
        self.cancel_called = False

    def cancel(self) -> None:
        self.cancel_called = True


@pytest.fixture()
def release_client() -> tuple[TestClient, SocietyManager]:
    manager = SocietyManager(SimConfig(
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
    ))
    agent_module._MANAGER = manager
    with TestClient(app) as client:
        try:
            yield client, manager
        finally:
            manager.pause()
            agent_module._MANAGER = None


def _activate(manager: SocietyManager) -> _CancelableTask:
    task = _CancelableTask()
    manager.running = True
    manager._task = task
    return task


def _snapshot(manager: SocietyManager) -> dict:
    return {
        "config": manager.config,
        "config_dump": manager.config.model_dump(),
        "world": manager.world,
        "agents": manager.agents,
        "agent_objects": tuple(manager.agents.values()),
        "recorder": manager.recorder,
        "tick": manager.world.tick,
        "running": manager.running,
        "task": manager._task,
    }


def _assert_snapshot(manager: SocietyManager, before: dict) -> None:
    assert manager.config is before["config"]
    assert manager.config.model_dump() == before["config_dump"]
    assert manager.world is before["world"]
    assert manager.agents is before["agents"]
    assert tuple(manager.agents.values()) == before["agent_objects"]
    assert manager.recorder is before["recorder"]
    assert manager.world.tick == before["tick"]
    assert manager.running is before["running"]
    assert manager._task is before["task"]
    assert all(agent.config is manager.config for agent in manager.agents.values())
    assert all(
        agent._shared_world is manager.world
        for agent in manager.agents.values()
    )


def _install_surrogate_store(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "memory.json"
    record = MemoryRecord(
        id=1,
        tick=0,
        perception=[],
        action=ActionType.OBSERVE,
        result_energy_delta=0.0,
        prediction_error=0.0,
        emotion=EmotionState(),
        importance=0.5,
        summary="\ud800",
    )
    path.write_text(
        json.dumps([record.model_dump(mode="json")]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        MemoryStore,
        "for_agent",
        classmethod(lambda cls, agent_id, n_agents: cls(path)),
    )


def test_ask_bootstraps_a_complete_recorded_society_tick() -> None:
    manager = SocietyManager(SimConfig(
        n_agents=2,
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
    ))
    agent_module._MANAGER = manager
    try:
        with pytest.raises(RuntimeError, match="SocietyManager.tick"):
            manager.agent(0).ask("Who are you?")

        with TestClient(app) as client:
            response = client.post(
                "/agent/ask", json={"question": "Who are you?"})

        assert response.status_code == 200
        assert manager.world.tick == 1
        assert all(agent.last_trace is not None
                   for agent in manager.agents.values())
        assert len(manager.recorder.series().rows) == 2
        assert {row["agent_id"] for row in manager.recorder.series().rows} == {0, 1}
    finally:
        manager.pause()
        agent_module._MANAGER = None


def test_reset_build_failure_is_fully_atomic(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SocietyManager(SimConfig(
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
    ))
    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)
    _install_surrogate_store(tmp_path, monkeypatch)

    with pytest.raises(UnicodeEncodeError):
        manager.reset(ConfigPatch(
            persist_memory=True,
            vector_memory_enabled=True,
        ))

    _assert_snapshot(manager, before)
    assert task.cancel_called is False


@pytest.mark.parametrize("endpoint", ["/reset", "/society/config"])
def test_reset_routes_preserve_state_and_propagate_unexpected_build_errors(
    release_client, tmp_path, monkeypatch: pytest.MonkeyPatch, endpoint: str,
) -> None:
    client, manager = release_client
    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)
    _install_surrogate_store(tmp_path, monkeypatch)

    with pytest.raises(UnicodeEncodeError):
        client.post(endpoint, json={
            "persist_memory": True,
            "vector_memory_enabled": True,
        })

    _assert_snapshot(manager, before)
    assert task.cancel_called is False


def test_missing_checkpoint_api_never_pauses_live_run(
    release_client, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)

    response = client.post("/checkpoint/load", json={"name": "missing"})

    assert response.status_code == 404
    _assert_snapshot(manager, before)
    assert task.cancel_called is False


@pytest.mark.parametrize("state", [
    {"schema": 1},
    {"schema": 999},
])
def test_invalid_checkpoint_api_is_400_and_atomic(
    release_client, tmp_path, monkeypatch: pytest.MonkeyPatch, state: dict,
) -> None:
    client, manager = release_client
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    (tmp_path / "broken.pkl").write_bytes(pickle.dumps(state))
    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)

    response = client.post("/checkpoint/load", json={"name": "broken"})

    assert response.status_code == 400
    _assert_snapshot(manager, before)
    assert task.cancel_called is False


def test_checkpoint_with_corrupt_world_tick_is_rejected_before_commit(
    release_client, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    checkpoint.save(manager, "corrupt-tick")
    path = tmp_path / "corrupt-tick.pkl"
    state = pickle.loads(path.read_bytes())
    state["world"].tick = "corrupt"
    path.write_bytes(pickle.dumps(state))

    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)

    response = client.post(
        "/checkpoint/load", json={"name": "corrupt-tick"})

    assert response.status_code == 400
    _assert_snapshot(manager, before)
    assert task.cancel_called is False


def test_checkpoint_state_preview_is_validated_before_commit(
    release_client, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    checkpoint.save(manager, "corrupt-world")
    path = tmp_path / "corrupt-world.pkl"
    state = pickle.loads(path.read_bytes())
    state["world"].objects = None
    path.write_bytes(pickle.dumps(state))

    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)

    response = client.post(
        "/checkpoint/load", json={"name": "corrupt-world"})

    assert response.status_code == 400
    _assert_snapshot(manager, before)
    assert task.cancel_called is False


@pytest.mark.parametrize("corruption", [
    "memory_records",
    "memory_nan",
    "phi_buffer",
    "phi_row_shape",
    "td_q",
    "spawn_metadata",
    "spawn_value",
    "task_counter",
    "task_grid",
    "disabled_store",
    "agent_body",
])
def test_corrupt_phase7_checkpoint_internals_are_rejected_atomically(
    release_client, tmp_path, monkeypatch: pytest.MonkeyPatch, corruption: str,
) -> None:
    client, manager = release_client
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    source = SocietyManager(SimConfig(
        n_objects=2,
        world_noise=0.0,
        memory_importance_threshold=0.0,
        persist_memory=False,
        trace_logging=False,
        phi_ar_enabled=True,
        phi_causal_enabled=True,
        vector_memory_enabled=True,
        td_learning_enabled=True,
        tasks_enabled=True,
    ))
    source.tick()
    checkpoint.save(source, "corrupt-internal")
    path = tmp_path / "corrupt-internal.pkl"
    state = pickle.loads(path.read_bytes())
    agent = state["agents"][0]
    if corruption == "memory_records":
        agent.memory._records = {}
    elif corruption == "memory_nan":
        agent.memory._records[0].importance = float("nan")
    elif corruption == "phi_buffer":
        agent.phi_causal_monitor._buffer = None
    elif corruption == "phi_row_shape":
        agent.phi_causal_monitor._buffer.append(
            agent.phi_causal_monitor._buffer[0][:1])
    elif corruption == "td_q":
        agent.td_learner.q = []
    elif corruption == "spawn_metadata":
        state["world"]._spawn_meta = None
    elif corruption == "spawn_value":
        first_id = next(iter(state["world"]._spawn_meta))
        state["world"]._spawn_meta[first_id]["max_energy"] = "bad"
    elif corruption == "task_counter":
        state["world"].task_manager._forage_eaten = "bad"
    elif corruption == "task_grid":
        state["world"].task_manager.grid_size += 1
    elif corruption == "disabled_store":
        agent.memory_store = MemoryStore(tmp_path / "unexpected.json")
        agent.memory._store = agent.memory_store
    elif corruption == "agent_body":
        state["world"].agents[0] = None
    path.write_bytes(pickle.dumps(state))

    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)

    response = client.post(
        "/checkpoint/load", json={"name": "corrupt-internal"})

    assert response.status_code == 400
    _assert_snapshot(manager, before)
    assert task.cancel_called is False


@pytest.mark.parametrize("payload", [
    {"name": "   "},
    {"name": "valid", "extra": True},
])
def test_checkpoint_request_validation_is_strict_and_non_mutating(
    release_client, payload: dict,
) -> None:
    client, manager = release_client
    manager.tick()
    task = _activate(manager)
    before = _snapshot(manager)

    response = client.post("/checkpoint/load", json=payload)

    assert response.status_code == 422
    _assert_snapshot(manager, before)
    assert task.cancel_called is False


def test_checkpoint_load_stops_a_real_background_run_without_late_ticks(
    release_client, tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    checkpoint.save(manager, "before-run")
    assert client.post(
        "/run", json={"tps": 100.0, "max_ticks": 1000}).status_code == 200
    deadline = time.time() + 3.0
    while manager.world.tick < 1 and time.time() < deadline:
        time.sleep(0.01)
    assert manager.world.tick >= 1

    response = client.post(
        "/checkpoint/load", json={"name": "before-run"})

    assert response.status_code == 200
    assert manager.running is False
    assert manager._task is None
    assert manager.world.tick == 0
    time.sleep(0.08)
    assert manager.world.tick == 0


def test_checkpoint_load_rolls_back_if_commit_fails(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    source = SocietyManager(SimConfig(
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
    ))
    checkpoint.save(source, "valid")
    target = SocietyManager(SimConfig(
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
        random_seed=999,
    ))
    task = _activate(target)
    before = _snapshot(target)

    def failing_pause() -> None:
        target.running = False
        target._task = None
        raise RuntimeError("synthetic checkpoint commit failure")

    monkeypatch.setattr(target, "pause", failing_pause)

    with pytest.raises(RuntimeError, match="synthetic checkpoint commit failure"):
        checkpoint.load(target, "valid")

    _assert_snapshot(target, before)
    assert task.cancel_called is False


def test_grid_one_tasks_rotate_through_reachable_bounded_targets() -> None:
    manager = TaskManager(grid_size=1)
    assert manager.grid_size == 1

    for _ in range(TASK_FORAGE_COUNT):
        manager.on_step(
            action=ActionType.INTERACT,
            events=[],
            agent_x=0,
            agent_y=0,
            ate_food=True,
        )

    reach = manager.state()
    assert reach.kind == "reach"
    assert reach.target == [0, 0]
    manager.on_step(
        action=ActionType.MOVE,
        events=[],
        agent_x=0,
        agent_y=0,
        ate_food=False,
    )

    assert manager.state().kind == "patrol"
    waypoints = manager._patrol_waypoints()
    assert waypoints == [(0, 0)]
    assert all(0 <= x < 1 and 0 <= y < 1 for x, y in waypoints)
    manager.on_step(
        action=ActionType.MOVE,
        events=[],
        agent_x=0,
        agent_y=0,
        ate_food=False,
    )
    assert manager.state().kind == "forage"
    assert manager.completed_total == 3


@pytest.mark.parametrize(("endpoint", "payload"), [
    ("/scenario/run", {"ticks": -1}),
    ("/scenario/run", {"ticks": 100_001}),
    ("/scenario/run", {"seed": -1}),
    ("/scenario/run", {"seed": 2**32}),
    ("/scenario/run", {"unexpected": True}),
    ("/train", {"ticks": -1}),
    ("/train", {"ticks": 100_001}),
    ("/train", {"unexpected": True}),
    ("/battery/mirror", {"ticks": -1}),
    ("/battery/mirror", {"ticks": 100_001}),
    ("/battery/mirror", {"seed": -1}),
    ("/battery/mirror", {"seed": 2**32}),
    ("/battery/mirror", {"unexpected": True}),
])
def test_probe_bodies_reject_negative_absurd_and_extra_values(
    release_client, monkeypatch: pytest.MonkeyPatch,
    endpoint: str, payload: dict,
) -> None:
    client, manager = release_client

    def unexpected_execution(*args, **kwargs):
        raise AssertionError("invalid probe body reached synchronous execution")

    monkeypatch.setattr(ScenarioRunner, "run", unexpected_execution)
    monkeypatch.setattr(manager, "train", unexpected_execution)
    monkeypatch.setattr(
        ConsciousnessTestBattery, "mirror_test", unexpected_execution)

    response = client.post(
        endpoint,
        content=json.dumps(payload, allow_nan=True),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(("endpoint", "payload"), [
    ("/world/stimulus", {"kind": "garbage", "intensity": 1.0}),
    ("/world/stimulus", {"kind": "food", "intensity": float("nan")}),
    ("/agent/inject", {"content": "x", "activation": float("nan")}),
    ("/agent/inject", {"content": "x", "ttl": 0}),
    ("/agent/attend", {"target_id": 0, "strength": float("nan")}),
    ("/agent/attend", {"target_id": 0, "ttl": 0}),
    ("/agent/perturb", {"type": "unknown", "magnitude": 1.0}),
])
def test_live_interventions_reject_non_finite_unknown_and_inert_payloads(
    release_client, endpoint: str, payload: dict,
) -> None:
    client, manager = release_client
    before_objects = dict(manager.world.objects)
    before_pending = list(manager.agent(0)._pending_injections)
    before_attend = manager.agent(0)._attend_bias

    response = client.post(
        endpoint,
        content=json.dumps(payload, allow_nan=True),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert manager.world.objects == before_objects
    assert manager.agent(0)._pending_injections == before_pending
    assert manager.agent(0)._attend_bias is before_attend


@pytest.mark.parametrize("intervention", [
    {"at_tick": 0, "type": "stimlus", "agent_id": 0, "params": {}},
    {"at_tick": -1, "type": "stimulus", "agent_id": 0, "params": {}},
    {"at_tick": 0, "type": "stimulus", "agent_id": 999, "params": {}},
    {"at_tick": 1, "type": "stimulus", "agent_id": 0, "params": {}},
    {"at_tick": 0, "type": "stimulus", "agent_id": 0,
     "params": {"kind": "food", "intensity": float("nan")}},
    {"at_tick": 0, "type": "goal", "agent_id": 0, "params": {}},
    {"at_tick": 0, "type": "attend", "agent_id": 0,
     "params": {"target_id": 0, "ttl": 0}},
    {"at_tick": 0, "type": "stimulus", "agent_id": 0,
     "params": {}, "unexpected": True},
])
def test_scenario_rejects_noop_or_malformed_interventions(
    release_client, intervention: dict,
) -> None:
    client, _ = release_client

    response = client.post(
        "/scenario/run",
        content=json.dumps(
            {"ticks": 1, "interventions": [intervention]},
            allow_nan=True,
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_scenario_intervention_count_is_bounded(release_client) -> None:
    client, _ = release_client
    intervention = {
        "at_tick": 0,
        "type": "stimulus",
        "agent_id": 0,
        "params": {"kind": "curio"},
    }

    response = client.post(
        "/scenario/run",
        json={"ticks": 1, "interventions": [intervention] * 1001},
    )

    assert response.status_code == 422


def _outside_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return True
    return False


def test_train_offloads_atomically_and_live_reads_fail_fast(
    release_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    started = threading.Event()
    release = threading.Event()
    read_done = threading.Event()
    train_responses = []
    read_responses = []
    observed: dict[str, object] = {}

    def train(ticks: int) -> dict:
        observed.update({
            "ticks": ticks,
            "lock_held": manager._lock.locked(),
            "offloaded": _outside_event_loop(),
        })
        started.set()
        assert release.wait(timeout=5)
        return {
            "ticks_run": ticks,
            "tick": manager.world.tick,
            "n_agents": len(manager.agents),
        }

    monkeypatch.setattr(manager, "train", train)

    train_thread = threading.Thread(
        target=lambda: train_responses.append(
            client.post("/train", json={"ticks": 51})),
    )

    def read_state() -> None:
        read_responses.append(client.get("/state"))
        read_done.set()

    train_thread.start()
    assert started.wait(timeout=5)
    read_thread = threading.Thread(target=read_state)
    read_thread.start()
    responsive_before_release = read_done.wait(timeout=0.5)
    release.set()
    train_thread.join(timeout=5)
    read_thread.join(timeout=5)

    assert responsive_before_release
    assert observed == {"ticks": 51, "lock_held": True, "offloaded": True}
    assert read_responses[0].status_code == 503
    assert read_responses[0].headers["retry-after"] == "1"
    assert train_responses[0].status_code == 200
    assert train_responses[0].json()["ticks_run"] == 51
    assert client.get("/state").status_code == 200


def test_checkpoint_save_is_offloaded_and_live_reads_fail_fast(
    release_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    started = threading.Event()
    release = threading.Event()
    read_done = threading.Event()
    save_responses = []
    read_responses = []
    observed: dict[str, object] = {}

    def blocking_save(mgr, name: str) -> dict:
        observed.update({
            "manager": mgr,
            "name": name,
            "lock_held": manager._lock.locked(),
            "offloaded": _outside_event_loop(),
        })
        started.set()
        assert release.wait(timeout=5)
        return {"name": name, "tick": manager.world.tick, "n_agents": 1}

    monkeypatch.setattr(checkpoint, "save", blocking_save)
    save_thread = threading.Thread(
        target=lambda: save_responses.append(
            client.post("/checkpoint/save", json={"name": "busy"})),
    )

    def read_state() -> None:
        read_responses.append(client.get("/state"))
        read_done.set()

    save_thread.start()
    assert started.wait(timeout=5)
    read_thread = threading.Thread(target=read_state)
    read_thread.start()
    responsive_before_release = read_done.wait(timeout=0.5)
    release.set()
    save_thread.join(timeout=5)
    read_thread.join(timeout=5)

    assert responsive_before_release
    assert observed == {
        "manager": manager,
        "name": "busy",
        "lock_held": True,
        "offloaded": True,
    }
    assert read_responses[0].status_code == 503
    assert read_responses[0].headers["retry-after"] == "1"
    assert save_responses[0].status_code == 200
    assert client.get("/state").status_code == 200


def test_hot_config_migration_is_offloaded_and_live_reads_fail_fast(
    release_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    started = threading.Event()
    release = threading.Event()
    read_done = threading.Event()
    config_responses = []
    read_responses = []
    observed: dict[str, object] = {}
    original_prepare = manager._prepare_hot_config_migrations

    def blocking_prepare(old_values, candidate):
        observed.update({
            "old": dict(old_values),
            "offloaded": _outside_event_loop(),
            "lock_held": manager._lock.locked(),
        })
        started.set()
        assert release.wait(timeout=5)
        return original_prepare(old_values, candidate)

    monkeypatch.setattr(
        manager, "_prepare_hot_config_migrations", blocking_prepare)
    config_thread = threading.Thread(
        target=lambda: config_responses.append(
            client.post("/config", json={"vector_memory_enabled": True})),
    )

    def read_state() -> None:
        read_responses.append(client.get("/state"))
        read_done.set()

    config_thread.start()
    assert started.wait(timeout=5)
    read_thread = threading.Thread(target=read_state)
    read_thread.start()
    responsive_before_release = read_done.wait(timeout=0.5)
    release.set()
    config_thread.join(timeout=5)
    read_thread.join(timeout=5)

    assert responsive_before_release
    assert observed == {
        "old": {"vector_memory_enabled": False},
        "offloaded": True,
        "lock_held": True,
    }
    assert read_responses[0].status_code == 503
    assert read_responses[0].headers["retry-after"] == "1"
    assert config_responses[0].status_code == 200
    assert manager.config.vector_memory_enabled is True
    assert client.get("/state").status_code == 200


def test_llm_reporting_job_is_offloaded_and_live_reads_fail_fast(
    release_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.llm as llm

    client, manager = release_client
    started = threading.Event()
    release = threading.Event()
    read_done = threading.Event()
    job_responses = []
    read_responses = []
    observed: dict[str, bool] = {}

    class BlockingBackend(llm.LLMBackend):
        model = "test/blocking"

        def available(self) -> bool:
            return True

        def complete(self, system: str, user: str, **kwargs) -> str:
            observed["offloaded"] = _outside_event_loop()
            observed["lock_held"] = manager._lock.locked()
            started.set()
            assert release.wait(timeout=5)
            return "Grounded narration from the supplied variables."

    monkeypatch.setattr(llm, "get_backend", lambda: BlockingBackend())
    job_thread = threading.Thread(
        target=lambda: job_responses.append(client.post("/agent/narrate")),
    )

    def read_state() -> None:
        read_responses.append(client.get("/state"))
        read_done.set()

    job_thread.start()
    assert started.wait(timeout=5)
    read_thread = threading.Thread(target=read_state)
    read_thread.start()
    responsive_before_release = read_done.wait(timeout=0.5)
    release.set()
    job_thread.join(timeout=5)
    read_thread.join(timeout=5)

    assert responsive_before_release
    assert observed == {"offloaded": True, "lock_held": True}
    assert read_responses[0].status_code == 503
    assert job_responses[0].status_code == 200
    assert client.get("/state").status_code == 200


def test_semantic_memory_search_rebuild_is_offloaded_without_priming(
    release_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = release_client
    agent = manager.agent(0)
    observed: dict[str, bool] = {}

    def sync(records) -> None:
        observed["offloaded"] = _outside_event_loop()
        observed["lock_held"] = manager._lock.locked()

    monkeypatch.setattr(agent.vector_index, "sync", sync)
    monkeypatch.setattr(
        agent.vector_index, "search_text",
        lambda records, query, limit: [],
    )

    response = client.get(
        "/agent/memory/search", params={"q": "anything", "limit": 8})

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert observed == {"offloaded": True, "lock_held": True}
    assert manager.world.tick == 0
    assert agent.last_trace is None


def test_scenario_run_offloads_cpu_work(
    release_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = release_client
    observed: dict[str, bool] = {}
    original_run = ScenarioRunner.run

    def run(self, scenario):
        observed["offloaded"] = _outside_event_loop()
        return original_run(self, scenario)

    monkeypatch.setattr(ScenarioRunner, "run", run)

    response = client.post("/scenario/run", json={"ticks": 0})

    assert response.status_code == 200
    assert observed == {"offloaded": True}


def test_battery_probe_offloads_cpu_work(
    release_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = release_client
    observed: dict[str, bool] = {}

    def mirror(self, seed: int, ticks: int) -> BatteryResult:
        observed["offloaded"] = _outside_event_loop()
        return BatteryResult(
            test="mirror",
            score=0.0,
            detail={"seed": seed, "ticks": ticks},
            interpretation="test",
            disclaimer="test",
        )

    monkeypatch.setattr(ConsciousnessTestBattery, "mirror_test", mirror)

    response = client.post(
        "/battery/mirror", json={"seed": 42, "ticks": 1})

    assert response.status_code == 200
    assert observed == {"offloaded": True}
