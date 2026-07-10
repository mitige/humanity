"""Regression tests for validated, non-destructive live configuration."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from core.society import SocietyManager  # noqa: E402
from schemas.models import (  # noqa: E402
    ActionType,
    ConfigPatch,
    EmotionState,
    MemoryRecord,
    RunRequest,
    SimConfig,
)


PHASE7_FLAGS = (
    "phi_causal_enabled",
    "hierarchy_enabled",
    "planning_enabled",
    "vector_memory_enabled",
    "td_learning_enabled",
    "mind_wandering_enabled",
    "world_dynamics_enabled",
    "tasks_enabled",
)


class _CancelableTask:
    """Minimal task stand-in that exposes whether reset attempted cancellation."""

    def __init__(self) -> None:
        self.cancel_called = False

    def cancel(self) -> None:
        self.cancel_called = True


def test_agent_cells_are_finite_unique_and_preserve_legacy_positions() -> None:
    from core.shared_world import _agent_cells

    cells = _agent_cells(grid_size=4, n_agents=10)
    legacy_first_nine = [
        (1, 1), (2, 1), (3, 1),
        (1, 2), (2, 2), (3, 2),
        (1, 3), (2, 3), (3, 3),
    ]

    assert cells[:9] == legacy_first_nine
    assert len(cells) == 10
    assert len(set(cells)) == 10
    assert all(0 <= x < 4 and 0 <= y < 4 for x, y in cells)


def test_config_rejects_more_agents_than_grid_cells() -> None:
    with pytest.raises(ValidationError, match="n_agents.*grid_size"):
        SimConfig(grid_size=1, n_agents=2)


@pytest.fixture()
def live_client() -> tuple[TestClient, SocietyManager]:
    """Expose a deterministic, in-memory society through the real API."""
    import core.agent as agent_module

    manager = SocietyManager(SimConfig(
        persist_memory=False,
        trace_logging=False,
        memory_importance_threshold=0.0,
        world_noise=0.0,
    ))
    agent_module._MANAGER = manager
    with TestClient(app) as client:
        try:
            yield client, manager
        finally:
            manager.pause()
            agent_module._MANAGER = None


def test_hot_config_preserves_accumulated_simulation_state(live_client) -> None:
    client, manager = live_client
    for _ in range(4):
        manager.tick()
    agent = manager.agent(0)
    agent.set_goal("keep-me")
    world = manager.world
    config = manager.config
    memory = agent.memory
    manager.tick()

    tick = world.tick
    self_state = agent.self_model_state()
    memory_count = memory.count()
    recorder_rows = list(manager.recorder.series().rows)

    response = client.post("/config", json={"ignition_threshold": 0.42})

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "hot"
    assert "ignition_threshold" in body["changed_fields"]
    assert manager.world is world
    assert manager.agent(0) is agent
    assert manager.config is config
    assert agent.memory is memory
    assert world.tick == tick
    after = agent.self_model_state()
    assert after.age_ticks == self_state.age_ticks
    assert after.active_goals == self_state.active_goals
    assert after.preferences == self_state.preferences
    assert memory.count() == memory_count
    assert manager.recorder.series().rows == recorder_rows

    shared_configs = (
        manager.config,
        manager.world.config,
        agent.config,
        agent.world.config,
        agent.world_model.config,
        agent.working_memory._config,
    )
    assert all(shared is config for shared in shared_configs)
    assert all(shared.ignition_threshold == 0.42 for shared in shared_configs)
    assert body["config"]["ignition_threshold"] == 0.42
    assert body["state"]["world"]["tick"] == tick
    assert body["disclaimer"]


def test_initial_energy_is_a_hot_reference_not_a_current_energy_reset(
    live_client,
) -> None:
    client, manager = live_client
    manager.tick()
    world = manager.world
    agent = manager.agent(0)
    config = manager.config
    tick = world.tick
    current_energy = world.agents[0].energy

    response = client.post("/config", json={"initial_energy": 150.0})

    assert response.status_code == 200
    assert response.json()["mode"] == "hot"
    assert manager.world is world
    assert manager.agent(0) is agent
    assert manager.config is config
    assert world.tick == tick
    assert world.agents[0].energy == current_energy
    assert manager.config.initial_energy == 150.0
    assert world.config is config
    assert agent.config is config
    assert agent.world.config is config


def test_hot_config_keeps_the_running_task_and_tick_monotonic() -> None:
    async def scenario() -> None:
        manager = SocietyManager(SimConfig(
            persist_memory=False,
            trace_logging=False,
            world_noise=0.0,
        ))
        task = None
        try:
            await manager.run(RunRequest(tps=120.0))
            await asyncio.sleep(0.04)
            task = manager._task
            world = manager.world
            agent = manager.agent(0)
            tick = world.tick
            assert tick > 0

            changed = await manager.apply_config(ConfigPatch(priming_enabled=True))

            assert changed == ["priming_enabled"]
            assert manager._task is task
            assert manager.world is world
            assert manager.agent(0) is agent
            assert manager.running is True
            assert world.tick >= tick
            await asyncio.sleep(0.03)
            assert world.tick >= tick
            assert world.tick != 0
        finally:
            manager.pause()
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


@pytest.mark.parametrize("payload", [
    {"n_agents": 0},
    {"contagion_rate": 2.0},
    {"phi_causal_nodes": 99},
    {"grid_size": 0},
    {"typo_flag": True},
    {"world_noise": -1.0},
    {"random_seed": 2**32},
    {"metrics_history_max": 1_000_001},
    {"attention_capacity": 1_000_000},
])
def test_invalid_config_is_rejected_atomically(live_client, payload) -> None:
    client, manager = live_client
    manager.tick()
    world = manager.world
    agent = manager.agent(0)
    tick = world.tick
    config = manager.config.model_dump()

    response = client.post("/config", json=payload)

    assert response.status_code == 422
    assert manager.world is world
    assert manager.agent(0) is agent
    assert world.tick == tick
    assert manager.config.model_dump() == config


def test_reset_rejects_impossible_agent_capacity_without_mutation(
    live_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = live_client
    manager.tick()
    world = manager.world
    agent = manager.agent(0)
    tick = world.tick
    config = manager.config.model_dump()

    def unexpected_reset(*args, **kwargs) -> None:
        raise AssertionError("invalid config reached the destructive reset route")

    monkeypatch.setattr(manager, "reset", unexpected_reset)

    response = client.post("/reset", json={"grid_size": 1, "n_agents": 2})

    assert response.status_code == 422
    assert manager.world is world
    assert manager.agent(0) is agent
    assert world.tick == tick
    assert manager.config.model_dump() == config


@pytest.mark.parametrize("endpoint", [
    "/config",
    "/reset",
    "/society/config",
])
def test_live_merge_validation_is_422_and_never_pauses(
    live_client, endpoint: str,
) -> None:
    client, manager = live_client
    manager.reset(ConfigPatch(
        grid_size=4,
        n_agents=4,
        persist_memory=False,
        trace_logging=False,
    ))
    manager.tick()
    world = manager.world
    agents = manager.agents
    agent_objects = tuple(manager.agents.values())
    config = manager.config
    config_dump = config.model_dump()
    tick = world.tick
    task = _CancelableTask()
    manager.running = True
    manager._task = task

    response = client.post(endpoint, json={"grid_size": 1})

    assert response.status_code == 422
    assert manager.world is world
    assert manager.agents is agents
    assert tuple(manager.agents.values()) == agent_objects
    assert manager.config is config
    assert manager.config.model_dump() == config_dump
    assert manager.world.tick == tick
    assert manager.running is True
    assert manager._task is task
    assert task.cancel_called is False


def test_direct_invalid_reset_validates_before_pause() -> None:
    manager = SocietyManager(SimConfig(
        grid_size=4,
        n_agents=4,
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
    ))
    manager.tick()
    world = manager.world
    agents = manager.agents
    config = manager.config
    config_dump = config.model_dump()
    tick = world.tick
    task = _CancelableTask()
    manager.running = True
    manager._task = task

    with pytest.raises(ValidationError, match="n_agents.*grid_size"):
        manager.reset({"grid_size": 1})

    assert manager.world is world
    assert manager.agents is agents
    assert manager.config is config
    assert manager.config.model_dump() == config_dump
    assert manager.world.tick == tick
    assert manager.running is True
    assert manager._task is task
    assert task.cancel_called is False


def test_hot_config_migrations_are_transactional_on_prepare_failure() -> None:
    manager = SocietyManager(SimConfig(
        n_agents=2,
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
        vector_memory_enabled=False,
    ))
    for agent_id, agent in manager.agents.items():
        agent.memory._records.append(MemoryRecord(
            id=agent_id + 1,
            tick=0,
            perception=[],
            action=ActionType.OBSERVE,
            result_energy_delta=0.0,
            prediction_error=0.0,
            emotion=EmotionState(),
            importance=0.5,
            summary=("valid summary" if agent_id == 0 else "\ud800"),
        ))

    world = manager.world
    agents = manager.agents
    agent_objects = tuple(manager.agents.values())
    config = manager.config
    config_dump = config.model_dump()
    memories = tuple(agent.memory for agent in agent_objects)
    record_lists = tuple(memory._records for memory in memories)
    records = tuple(tuple(memory._records) for memory in memories)
    indexes = tuple(agent.vector_index for agent in agent_objects)
    index_sizes = tuple(index.size() for index in indexes)
    recorder_rows = list(manager.recorder.series().rows)
    state = manager.state()

    with pytest.raises(UnicodeEncodeError):
        asyncio.run(manager.apply_config(ConfigPatch(
            vector_memory_enabled=True)))

    assert manager.world is world
    assert manager.agents is agents
    assert tuple(manager.agents.values()) == agent_objects
    assert manager.config is config
    assert manager.config.model_dump() == config_dump
    assert manager.config.vector_memory_enabled is False
    assert tuple(agent.memory for agent in agent_objects) == memories
    assert tuple(memory._records for memory in memories) == record_lists
    assert tuple(tuple(memory._records) for memory in memories) == records
    assert tuple(agent.vector_index for agent in agent_objects) == indexes
    assert tuple(index.size() for index in indexes) == index_sizes
    assert manager.recorder.series().rows == recorder_rows
    assert manager.state() == state


def test_hot_config_rolls_back_if_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = SocietyManager(SimConfig(
        n_agents=2,
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
        tasks_enabled=False,
    ))
    config = manager.config
    config_dump = config.model_dump()
    world_task_manager = manager.world.task_manager
    agent_task_managers = tuple(
        agent.world.task_manager for agent in manager.agents.values()
    )

    def fail_commit(plan: dict) -> None:
        manager.world.task_manager = object()
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(
        manager,
        "_commit_hot_config_migrations",
        fail_commit,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        asyncio.run(manager.apply_config(ConfigPatch(tasks_enabled=True)))

    assert manager.config is config
    assert manager.config.model_dump() == config_dump
    assert manager.world.task_manager is world_task_manager
    assert tuple(
        agent.world.task_manager for agent in manager.agents.values()
    ) == agent_task_managers


def test_hot_config_cancellation_waits_for_worker_and_never_exposes_partial_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    manager = SocietyManager(SimConfig(
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
        vector_memory_enabled=False,
    ))
    started = threading.Event()
    release = threading.Event()
    original_commit = manager._commit_hot_config_migrations

    def blocking_commit(plan: dict) -> None:
        started.set()
        assert release.wait(timeout=5)
        original_commit(plan)

    monkeypatch.setattr(
        manager, "_commit_hot_config_migrations", blocking_commit)

    async def exercise() -> None:
        task = asyncio.create_task(manager.apply_config(
            ConfigPatch(vector_memory_enabled=True)))
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert manager._exclusive_worker is True
        assert manager._lock.locked()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    assert manager.config.vector_memory_enabled is True
    assert manager._exclusive_worker is False
    assert manager._lock.locked() is False


def test_structural_config_requires_explicit_reset(live_client) -> None:
    client, manager = live_client
    manager.tick()
    old_world = manager.world
    old_agent = manager.agent(0)
    old_config = manager.config.model_dump()
    old_tick = old_world.tick
    patch = {"n_agents": 2, "grid_size": 20}

    rejected = client.post("/config", json=patch)

    assert rejected.status_code == 409
    detail = rejected.json()["detail"]
    assert set(detail["fields"]) == {"grid_size", "n_agents"}
    assert "/reset" in detail["instruction"]
    assert manager.world is old_world
    assert manager.agent(0) is old_agent
    assert manager.world.tick == old_tick
    assert manager.config.model_dump() == old_config

    reset = client.post("/reset", json=patch)

    assert reset.status_code == 200
    assert manager.world is not old_world
    assert manager.agent(0) is not old_agent
    assert manager.world.tick == 0
    assert manager.config.n_agents == 2
    assert manager.config.grid_size == 20
    assert len(manager.agents) == 2
    assert reset.json()["mode"] == "reset"
    assert reset.json()["world"]["tick"] == 0


def test_society_config_is_an_explicit_destructive_reset(live_client) -> None:
    client, manager = live_client
    manager.tick()
    old_world = manager.world
    old_agent = manager.agent(0)

    response = client.post("/society/config", json={
        "n_agents": 2,
        "persist_memory": False,
        "trace_logging": False,
    })

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "reset"
    assert body["world"]["tick"] == 0
    assert manager.world is not old_world
    assert manager.agent(0) is not old_agent
    assert manager.config.n_agents == 2
    assert len(manager.agents) == 2


def test_phase7_flags_and_task_manager_migrate_hot(live_client) -> None:
    client, manager = live_client
    for _ in range(4):
        manager.tick()
    world = manager.world
    agent = manager.agent(0)
    tick = world.tick
    memory_count = agent.memory.count()
    assert memory_count > 0

    enabled = client.post(
        "/config", json={flag: True for flag in PHASE7_FLAGS})

    assert enabled.status_code == 200
    assert enabled.json()["mode"] == "hot"
    assert set(enabled.json()["changed_fields"]) == set(PHASE7_FLAGS)
    assert manager.world is world
    assert manager.agent(0) is agent
    assert world.tick == tick
    assert agent.vector_index.size() == memory_count
    assert world.task_manager is not None
    assert agent.world.task_manager is not None

    disabled = client.post("/config", json={"tasks_enabled": False})

    assert disabled.status_code == 200
    assert manager.world is world
    assert manager.agent(0) is agent
    assert world.tick == tick
    assert world.task_manager is None
    assert agent.world.task_manager is None


def test_goal_persistence_and_trace_flags_migrate_hot(
    live_client, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, manager = live_client
    for _ in range(3):
        manager.tick()
    agent = manager.agent(0)
    memory = agent.memory
    records = list(memory._records)
    io_calls: list[str] = []

    from storage.persistence import MemoryStore

    monkeypatch.setattr(
        MemoryStore, "load_records",
        lambda self: io_calls.append("load") or [],
    )
    monkeypatch.setattr(
        "core.society.atomic_save_batch",
        lambda entries: io_calls.append("save"),
    )

    enabled = client.post("/config", json={
        "language_drive_enabled": True,
        "individuation_enabled": True,
        "trace_logging": True,
    })

    assert enabled.status_code == 200
    goals = agent.self_model_state().active_goals
    assert goals.count("invent a language") == 1
    assert goals.count("become someone") == 1
    assert agent._last_individuation is not None
    assert manager.config.trace_logging is True

    repeated = client.post("/config", json={
        "language_drive_enabled": True,
        "individuation_enabled": True,
    })
    assert repeated.status_code == 200
    goals = agent.self_model_state().active_goals
    assert goals.count("invent a language") == 1
    assert goals.count("become someone") == 1

    persistence_on = client.post("/config", json={"persist_memory": True})

    assert persistence_on.status_code == 200
    assert agent.memory is memory
    assert memory._records == records
    assert agent.memory_store is not None
    assert memory._store is agent.memory_store
    assert io_calls == ["save"]

    persistence_off = client.post("/config", json={"persist_memory": False})

    assert persistence_off.status_code == 200
    assert agent.memory is memory
    assert memory._records == records
    assert agent.memory_store is None
    assert memory._store is None
    assert io_calls == ["save"]

    disabled = client.post("/config", json={
        "language_drive_enabled": False,
        "individuation_enabled": False,
        "trace_logging": False,
    })

    assert disabled.status_code == 200
    goals = agent.self_model_state().active_goals
    assert "invent a language" not in goals
    assert "become someone" not in goals
    assert agent._last_individuation is None
    assert manager.config.trace_logging is False


def test_persistent_paths_are_isolated_per_agent_and_legacy_for_solo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from storage.persistence import MemoryStore

    monkeypatch.setattr(MemoryStore, "load_records", lambda self: [])
    multi = SocietyManager(SimConfig(
        n_agents=3,
        n_objects=0,
        world_noise=0.0,
        persist_memory=True,
        trace_logging=True,
    ))

    memory_names = {
        Path(agent.memory_store.path()).name
        for agent in multi.agents.values()
    }
    trace_names = {
        Path(agent.trace_logger.path()).name
        for agent in multi.agents.values()
    }
    assert memory_names == {
        "memory-agent-0.json",
        "memory-agent-1.json",
        "memory-agent-2.json",
    }
    assert trace_names == {
        "traces-agent-0.jsonl",
        "traces-agent-1.jsonl",
        "traces-agent-2.jsonl",
    }

    solo = SocietyManager(SimConfig(
        n_agents=1,
        n_objects=0,
        world_noise=0.0,
        persist_memory=True,
        trace_logging=True,
    ))
    assert solo.agent(0).memory_store.path().endswith("memory.json")
    assert solo.agent(0).trace_logger.path().endswith("traces.jsonl")


def test_hot_persistence_enable_uses_distinct_paths_without_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from storage.persistence import MemoryStore

    load_calls: list[str] = []
    save_calls: list[str] = []
    monkeypatch.setattr(
        MemoryStore,
        "load_records",
        lambda self: load_calls.append(self.path()) or [],
    )
    def capture_batch(entries):
        save_calls.extend(store.path() for store, _rows in entries)

    monkeypatch.setattr("core.society.atomic_save_batch", capture_batch)
    manager = SocietyManager(SimConfig(
        n_agents=3,
        n_objects=0,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
    ))

    changed = asyncio.run(manager.apply_config(ConfigPatch(persist_memory=True)))

    assert changed == ["persist_memory"]
    paths = [
        agent.memory_store.path()
        for agent in manager.agents.values()
    ]
    assert len(set(paths)) == 3
    assert load_calls == []
    assert set(save_calls) == set(paths)


def test_hot_persistence_enable_flushes_existing_ram_history(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from storage.persistence import MemoryStore

    path = tmp_path / "memory.json"
    monkeypatch.setattr(
        MemoryStore,
        "for_agent",
        classmethod(lambda cls, agent_id, n_agents: cls(path)),
    )
    manager = SocietyManager(SimConfig(
        n_agents=1,
        n_objects=0,
        world_noise=0.0,
        memory_importance_threshold=0.0,
        persist_memory=False,
        trace_logging=False,
    ))
    manager.agent(0).memory.store_experience(
        tick=0,
        perception=[],
        action=ActionType.OBSERVE,
        result_energy_delta=0.0,
        prediction_error=0.0,
        emotion=EmotionState(),
        importance=0.7,
        summary="already in RAM",
    )

    changed = asyncio.run(manager.apply_config(
        ConfigPatch(persist_memory=True)))
    reloaded = MemoryStore(path).load_records()

    assert changed == ["persist_memory"]
    assert [record.summary for record in reloaded] == ["already in RAM"]


def test_hot_persistence_multi_agent_failure_rolls_back_every_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A late store failure cannot leave an earlier agent newly persisted."""
    from pathlib import Path
    from storage.persistence import MemoryStore

    def store_for_agent(cls, agent_id, n_agents):
        return cls(tmp_path / f"memory-{agent_id}.json")

    monkeypatch.setattr(
        MemoryStore, "for_agent", classmethod(store_for_agent))
    manager = SocietyManager(SimConfig(
        n_agents=2,
        n_objects=0,
        world_noise=0.0,
        memory_importance_threshold=0.0,
        persist_memory=False,
        trace_logging=False,
    ))
    for agent_id, agent in manager.agents.items():
        agent.memory.store_experience(
            tick=0,
            perception=[],
            action=ActionType.OBSERVE,
            result_energy_delta=0.0,
            prediction_error=0.0,
            emotion=EmotionState(),
            importance=0.7,
            summary=f"RAM agent {agent_id}",
        )
        Path(tmp_path / f"memory-{agent_id}.json").write_text(
            "[]", encoding="utf-8")

    original_replace = Path.replace

    def fail_second_install(self, target):
        target_path = Path(target)
        if (self.name.endswith(".tmp")
                and target_path.name == "memory-1.json"):
            raise OSError("synthetic second-store failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_second_install)

    with pytest.raises(OSError, match="second-store"):
        asyncio.run(manager.apply_config(ConfigPatch(persist_memory=True)))

    assert manager.config.persist_memory is False
    assert all(agent.memory_store is None for agent in manager.agents.values())
    assert all(
        (tmp_path / f"memory-{agent_id}.json").read_text(encoding="utf-8")
        == "[]"
        for agent_id in range(2)
    )


def test_memory_batch_double_fault_retains_a_recovery_copy(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from storage.persistence import MemoryStore, atomic_save_batch

    stores = [MemoryStore(tmp_path / f"memory-{i}.json") for i in range(2)]
    for store in stores:
        Path(store.path()).write_text("[]", encoding="utf-8")
    manager = SocietyManager(SimConfig(
        n_agents=2, n_objects=0, world_noise=0.0,
        memory_importance_threshold=0.0,
        persist_memory=False, trace_logging=False,
    ))
    for agent_id, agent in manager.agents.items():
        agent.memory.store_experience(
            tick=0, perception=[], action=ActionType.OBSERVE,
            result_energy_delta=0.0, prediction_error=0.0,
            emotion=EmotionState(), importance=0.7,
            summary=f"RAM agent {agent_id}",
        )

    original_replace = Path.replace

    def fail_commit_and_one_rollback(self, target):
        target_path = Path(target)
        if target_path.name == "memory-1.json" and (
                self.name.endswith(".tmp")
                or self.name.endswith(".rollback")):
            raise OSError("synthetic commit/rollback double fault")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_commit_and_one_rollback)

    with pytest.raises(RuntimeError, match="recovery copies were retained"):
        atomic_save_batch([
            (stores[i], manager.agents[i].memory._records)
            for i in range(2)
        ])

    recovery = list(tmp_path.glob(".memory-1.json.*.rollback"))
    assert len(recovery) == 1
    assert recovery[0].read_text(encoding="utf-8") == "[]"
    assert Path(stores[0].path()).read_text(encoding="utf-8") == "[]"


def test_user_goals_survive_system_drive_enable_disable(live_client) -> None:
    client, manager = live_client
    agent = manager.agent(0)
    agent.set_goal("invent a language")
    agent.set_goal("become someone")

    enabled = client.post("/config", json={
        "language_drive_enabled": True,
        "individuation_enabled": True,
    })
    disabled = client.post("/config", json={
        "language_drive_enabled": False,
        "individuation_enabled": False,
    })

    assert enabled.status_code == 200
    assert disabled.status_code == 200
    goals = agent.self_model_state().active_goals
    assert goals.count("invent a language") == 1
    assert goals.count("become someone") == 1


@pytest.mark.parametrize("payload", [
    {"tps": 0},
    {"tps": -1},
    {"tps": 1000.1},
    {"tps": 1_000_000},
    {"max_ticks": 0},
    {"max_ticks": -1},
    {"max_ticks": 1_000_001},
])
def test_run_request_rejects_nonpositive_and_absurd_bounds(
    live_client, payload,
) -> None:
    client, _ = live_client
    response = client.post("/run", json=payload)
    assert response.status_code == 422
