# core/checkpoint.py
"""Run checkpoints: save and resume the full live society state.

Serializes the picklable core of a :class:`SocietyManager` — config, shared
world (including its RNG state), every agent's internal state (world-model
beliefs, learned Q-values, personality, self-model, memory, concepts…), and the
metrics recorder — to a local file, so a run can be resumed exactly where it
left off. The manager's asyncio lock/task are intentionally excluded and rebuilt
on load.

FUNCTIONAL NOTE: this is bookkeeping over internal variables; it captures no
"experience". Checkpoints are plain pickles for LOCAL, trusted use only (never
load an untrusted checkpoint). They are version-bound: load with the same code
that saved them.
"""
from __future__ import annotations

import gc
import json
import hashlib
import math
import os
import pickle
import re
import tempfile
import threading
import time
from collections import deque
from functools import wraps
from pathlib import Path

import numpy as np

from core.agent import CognitiveAgent
from core.constants import PHI_CAUSAL_MIN_SAMPLES
from core.gender_experience import GenderExperienceEngine
from core.gender_society import GenderSociety
from core.metrics_recorder import MetricsRecorder
from core.shared_world import AgentBody, SharedWorld
from core.world_tasks import TaskManager
from schemas.models import (
    GenderScenario,
    MemoryRecord,
    Message,
    SimConfig,
    WorldObject,
)

CKPT_DIR = Path("storage/checkpoints")
_SCHEMA = 3
_STATE_KEYS = {
    "schema", "config", "world", "agents", "recorder", "artifacts",
    "gender_society", "gender_scenario_manifest",
}
_ARTIFACT_KEYS = {
    "memory_managed", "memory_path",
    "trace_managed", "trace_path", "trace_existed", "trace_size",
    "trace_sha256",
}
_FILE_LOCK = threading.RLock()


class InvalidCheckpointError(ValueError):
    """Raised when a checkpoint cannot safely replace the live society."""


def _file_locked(func):
    """Serialize checkpoint save/load/list/delete within this process."""
    @wraps(func)
    def wrapped(*args, **kwargs):
        with _FILE_LOCK:
            return func(*args, **kwargs)
    return wrapped


def _safe(name: str) -> str:
    """Sanitize a checkpoint name to a safe filename stem."""
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(name).strip()).strip("-.")
    stem = stem[:64] or "checkpoint"
    # Win32 device names remain reserved even with an extension. Prefix them
    # everywhere so checkpoint names stay portable across filesystems.
    base = stem.split(".", 1)[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        f"{prefix}{number}"
        for prefix in ("COM", "LPT")
        for number in range(1, 10)
    }
    return f"_{stem}" if base in reserved else stem


def _hash_prefix(path: Path, size: int) -> str:
    digest = hashlib.sha256()
    remaining = int(size)
    with path.open("rb") as handle:
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                raise InvalidCheckpointError(
                    f"trace file {path} is shorter than its checkpoint offset")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def _artifact_manifest(manager) -> dict[int, dict]:
    manifest: dict[int, dict] = {}
    for agent_id, agent in sorted(manager.agents.items()):
        memory_managed = bool(
            manager.config.persist_memory and agent.memory_store is not None)
        memory_path = (
            str(Path(agent.memory_store.path()).resolve())
            if memory_managed else None
        )
        trace_managed = bool(manager.config.trace_logging)
        trace_path = (
            Path(agent.trace_logger.path()).resolve()
            if trace_managed else None
        )
        trace_existed = bool(trace_path is not None and trace_path.exists())
        trace_size = int(trace_path.stat().st_size) if trace_existed else 0
        manifest[int(agent_id)] = {
            "memory_managed": memory_managed,
            "memory_path": memory_path,
            "trace_managed": trace_managed,
            "trace_path": str(trace_path) if trace_path is not None else None,
            "trace_existed": trace_existed,
            "trace_size": trace_size,
            "trace_sha256": (
                _hash_prefix(trace_path, trace_size) if trace_existed else None
            ),
        }
    return manifest


def _temp_path(target: Path, suffix: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=suffix)
    os.close(fd)
    return Path(name)


def _prepare_pickle(path: Path, value: object) -> Path:
    temp = _temp_path(path, ".pkl.tmp")
    try:
        with temp.open("wb") as handle:
            pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
            handle.flush()
            os.fsync(handle.fileno())
        return temp
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def _prepare_text(path: Path, value: str) -> Path:
    temp = _temp_path(path, ".json.tmp")
    try:
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        return temp
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


@_file_locked
def save(manager, name: str) -> dict:
    """Atomically save core state plus managed persistence branch metadata."""
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    stem = _safe(name)
    state = {
        "schema": _SCHEMA,
        "config": manager.config,
        "world": manager.world,
        "agents": manager.agents,
        "recorder": manager.recorder,
        "gender_society": manager.gender_society,
        "gender_scenario_manifest": manager.gender_scenario_manifest,
        "artifacts": _artifact_manifest(manager),
    }
    checkpoint_path = CKPT_DIR / f"{stem}.pkl"
    meta_path = CKPT_DIR / f"{stem}.json"
    prepared: list[dict] = []
    tokens: list[dict] = []
    try:
        pickle_temp = _prepare_pickle(checkpoint_path, state)
        prepared.append({"target": checkpoint_path, "desired": pickle_temp})
        meta = {
            "name": stem,
            "tick": int(manager.world.tick),
            "n_agents": len(manager.agents),
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "bytes": pickle_temp.stat().st_size,
            "schema": _SCHEMA,
        }
        meta_temp = _prepare_text(
            meta_path, json.dumps(meta, ensure_ascii=False))
        prepared.append({"target": meta_path, "desired": meta_temp})
        tokens = _apply_artifact_files(prepared)
    except Exception:
        _finalize_artifact_files(prepared, [])
        raise
    _finalize_artifact_files(prepared, tokens)
    return meta


def _finite(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(float(value))


def _validate_task_manager(
    task: object, *, label: str, expected_grid_size: int | None = None,
) -> None:
    if task is None:
        return
    if not isinstance(task, TaskManager):
        raise InvalidCheckpointError(f"{label} has the wrong task-manager type")
    integer_fields = (
        "grid_size", "completed_total", "_ticks_on_task",
        "_forage_eaten", "_patrol_visited",
    )
    for field in integer_fields:
        value = getattr(task, field, None)
        minimum = 1 if field == "grid_size" else 0
        if type(value) is not int or value < minimum:
            raise InvalidCheckpointError(
                f"{label}.{field} must be an integer >= {minimum}")
    if expected_grid_size is not None \
            and task.grid_size != int(expected_grid_size):
        raise InvalidCheckpointError(
            f"{label}.grid_size disagrees with checkpoint config")
    if getattr(task, "_kind", None) not in {"forage", "reach", "patrol"}:
        raise InvalidCheckpointError(f"{label} has an invalid task kind")
    progress = getattr(task, "_progress", None)
    if not _finite(progress) or not 0.0 <= float(progress) <= 1.0:
        raise InvalidCheckpointError(f"{label} has invalid task progress")
    task.state()


def _validate_world_internals(world: SharedWorld, config: SimConfig) -> None:
    """Validate latent environment state even when its feature flag is off."""
    grid = int(config.grid_size)
    objects = getattr(world, "objects", None)
    seen = getattr(world, "seen_counts", None)
    spawn = getattr(world, "_spawn_meta", None)
    if not isinstance(objects, dict) or not isinstance(seen, dict) \
            or not isinstance(spawn, dict):
        raise InvalidCheckpointError("checkpoint world object state is invalid")
    object_ids = set(objects)
    if set(seen) != object_ids or set(spawn) != object_ids:
        raise InvalidCheckpointError(
            "checkpoint world object metadata is incomplete")
    for object_id, obj in objects.items():
        if type(object_id) is not int or not isinstance(obj, WorldObject) \
                or obj.id != object_id or obj.kind not in {
                    "food", "hazard", "tool", "curio"} \
                or type(obj.x) is not int or not 0 <= obj.x < grid \
                or type(obj.y) is not int or not 0 <= obj.y < grid \
                or not all(_finite(value) for value in (
                    obj.energy_value, obj.danger, obj.novelty, obj.utility)):
            raise InvalidCheckpointError(
                f"checkpoint world object {object_id} is invalid")
        if type(seen[object_id]) is not int or seen[object_id] < 0:
            raise InvalidCheckpointError(
                f"checkpoint world seen count {object_id} is invalid")
        meta = spawn[object_id]
        if not isinstance(meta, dict) or set(meta) != {
                "max_energy", "base_danger"} \
                or not all(_finite(meta.get(key)) for key in (
                    "max_energy", "base_danger")) \
                or float(meta["max_energy"]) < 0.0 \
                or not 0.0 <= float(meta["base_danger"]) <= 1.0:
            raise InvalidCheckpointError(
                f"checkpoint world spawn metadata {object_id} is invalid")
    next_id = getattr(world, "_next_id", None)
    if type(next_id) is not int \
            or next_id < max(object_ids, default=-1) + 1:
        raise InvalidCheckpointError("checkpoint world next object id is invalid")
    if not isinstance(getattr(world, "rng", None), np.random.Generator):
        raise InvalidCheckpointError("checkpoint world RNG is invalid")

    bodies = getattr(world, "agents", None)
    if not isinstance(bodies, dict):
        raise InvalidCheckpointError("checkpoint world agent bodies are invalid")
    for agent_id, body in bodies.items():
        if type(agent_id) is not int or not isinstance(body, AgentBody) \
                or body.id != agent_id \
                or type(body.x) is not int or not 0 <= body.x < grid \
                or type(body.y) is not int or not 0 <= body.y < grid \
                or not _finite(body.energy) or not _finite(body.valence):
            raise InvalidCheckpointError(
                f"checkpoint world agent body {agent_id} is invalid")

    messages = getattr(world, "messages", None)
    if not isinstance(messages, list) or not all(
            isinstance(message, Message) for message in messages):
        raise InvalidCheckpointError("checkpoint world messages are invalid")
    try:
        for message in messages:
            Message.model_validate(message.model_dump())
            if not all(_finite(value) for value in message.vector):
                raise ValueError("non-finite message vector")
    except Exception as exc:
        raise InvalidCheckpointError(
            f"checkpoint world messages are invalid: {exc}") from exc


def _validate_agent_internals(agent: CognitiveAgent, *, agent_id: int,
                              config: SimConfig) -> None:
    label = f"checkpoint agent {agent_id}"
    memory = agent.memory
    records = getattr(memory, "_records", None)
    vectors = getattr(memory, "_vectors", None)
    norms = getattr(memory, "_vector_norms", None)
    if not isinstance(records, list) or not all(
            isinstance(record, MemoryRecord) for record in records):
        raise InvalidCheckpointError(f"{label} memory records are invalid")
    validated_records: list[MemoryRecord] = []
    try:
        for record in records:
            clean = MemoryRecord.model_validate(record.model_dump())
            numeric = (
                clean.result_energy_delta,
                clean.prediction_error,
                clean.importance,
                clean.emotion.fear,
                clean.emotion.curiosity,
                clean.emotion.satisfaction,
                clean.emotion.fatigue,
                clean.emotion.confusion,
            )
            if type(clean.id) is not int or clean.id < 1 \
                    or type(clean.tick) is not int or clean.tick < 0 \
                    or not all(_finite(value) for value in numeric):
                raise ValueError("invalid memory scalar")
            for percept in clean.perception:
                if type(percept.object_id) is not int \
                        or type(percept.dx) is not int \
                        or type(percept.dy) is not int \
                        or not isinstance(percept.kind, str) \
                        or not all(_finite(value) for value in (
                            percept.distance, percept.danger, percept.novelty,
                            percept.utility, percept.energy_value,
                        )):
                    raise ValueError("invalid memory percept")
            validated_records.append(clean)
    except Exception as exc:
        raise InvalidCheckpointError(
            f"{label} memory records are invalid: {exc}") from exc
    record_ids = [record.id for record in validated_records]
    if record_ids != sorted(set(record_ids)):
        raise InvalidCheckpointError(
            f"{label} memory ids must be unique and increasing")
    # Derived caches are rebuilt from authoritative, validated records.
    memory._records = validated_records
    memory._vectors = [memory.feature_vector(r.perception)
                       for r in validated_records]
    memory._vector_norms = [float(np.linalg.norm(v))
                            for v in memory._vectors]
    next_id = getattr(memory, "_next_id", None)
    minimum_next = max(record_ids, default=0) + 1
    if type(next_id) is not int or next_id < minimum_next:
        raise InvalidCheckpointError(f"{label} memory next id is invalid")
    if config.persist_memory:
        if agent.memory_store is None or memory._store is not agent.memory_store:
            raise InvalidCheckpointError(
                f"{label} persistent-memory references are inconsistent")
    elif agent.memory_store is not None or memory._store is not None:
        raise InvalidCheckpointError(
            f"{label} has a store while persistence is disabled")

    index = agent.vector_index
    if config.vector_memory_enabled:
        index._ids = []
        index._vectors = []
        index.rebuild(validated_records)
    else:
        # Keep the opt-in cost truly off. Search/graph endpoints call sync()
        # inside their explicit background job and rebuild lazily on demand.
        index._ids = []
        index._vectors = []

    td = agent.td_learner
    for field in ("q", "traces"):
        table = getattr(td, field, None)
        if not isinstance(table, dict) or any(
            not isinstance(key, tuple) or len(key) != 2
            or not all(isinstance(part, str) for part in key)
            or not _finite(value)
            for key, value in table.items()
        ):
            raise InvalidCheckpointError(f"{label} TD {field} is invalid")
    pending = getattr(td, "_pending", None)
    if pending is not None and (
        not isinstance(pending, tuple) or len(pending) != 3
        or not isinstance(pending[0], str)
        or not isinstance(pending[1], str)
        or not _finite(pending[2])
    ):
        raise InvalidCheckpointError(f"{label} TD pending state is invalid")
    if not _finite(getattr(td, "_last_td_error", None)) \
            or not _finite(getattr(td, "_last_reward", None)) \
            or (getattr(td, "_last_context", None) is not None
                and not isinstance(td._last_context, str)):
        raise InvalidCheckpointError(f"{label} TD latest state is invalid")

    for monitor_name in ("phi_causal_monitor", "phi_ar_monitor"):
        monitor = getattr(agent, monitor_name, None)
        buffer = getattr(monitor, "_buffer", None)
        sources = getattr(monitor, "sources", None)
        expected_maxlen = (
            max(PHI_CAUSAL_MIN_SAMPLES, int(config.phi_causal_window))
            if monitor_name == "phi_causal_monitor"
            else max(10, int(config.phi_ar_window))
        )
        valid_sources = (
            isinstance(sources, list)
            and bool(sources)
            and all(isinstance(source, str) and source for source in sources)
            and len(set(sources)) == len(sources)
        )
        valid_rows = isinstance(buffer, deque) and all(
            isinstance(row, np.ndarray)
            and row.shape == (len(sources),)
            and np.issubdtype(row.dtype, np.number)
            and np.isfinite(row).all()
            for row in buffer
        ) if valid_sources else False
        if not valid_sources or not valid_rows \
                or buffer.maxlen != expected_maxlen:
            raise InvalidCheckpointError(
                f"{label} {monitor_name} buffer is invalid")
    _validate_task_manager(
        getattr(agent.world, "task_manager", None),
        label=f"{label}.world.task_manager",
        expected_grid_size=config.grid_size,
    )
    engine = getattr(agent, "gender_experience", None)
    if not isinstance(engine, GenderExperienceEngine):
        raise InvalidCheckpointError(
            f"{label} gender experience engine is invalid")
    if engine.config is not config or engine.agent_id != agent_id:
        raise InvalidCheckpointError(
            f"{label} gender engine references are inconsistent")
    profile = getattr(engine, "_profile", None)
    life_course = getattr(engine, "_life_course_plan", None)
    lifecycle = getattr(engine, "_lifecycle", None)
    if profile is None:
        if life_course is not None or lifecycle is not None \
                or engine.current_state is not None:
            raise InvalidCheckpointError(
                f"{label} has partial gender configuration")
    else:
        try:
            type(profile).model_validate(profile.model_dump())
            type(life_course).model_validate(life_course.model_dump())
            if engine._checksum(profile) != engine.profile_checksum:
                raise ValueError("profile checksum mismatch")
            if lifecycle is None:
                raise ValueError("missing lifecycle")
            if engine.current_state is not None:
                type(engine.current_state).model_validate(
                    engine.current_state.model_dump())
            for event in (
                engine.pending_events + engine.event_ledger
            ):
                type(event).model_validate(event.model_dump())
        except Exception as exc:
            raise InvalidCheckpointError(
                f"{label} gender engine state is invalid: {exc}") from exc


def _validate_artifacts(state: dict, expected_ids: set[int]) -> None:
    artifacts = state.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != expected_ids:
        raise InvalidCheckpointError(
            "checkpoint artifact ids do not match the society")
    config = state["config"]
    for agent_id in sorted(expected_ids):
        entry = artifacts[agent_id]
        if not isinstance(entry, dict) or set(entry) != _ARTIFACT_KEYS:
            raise InvalidCheckpointError(
                f"checkpoint artifact {agent_id} has an invalid shape")
        agent = state["agents"][agent_id]
        memory_managed = entry["memory_managed"]
        trace_managed = entry["trace_managed"]
        if type(memory_managed) is not bool \
                or memory_managed is not bool(config.persist_memory):
            raise InvalidCheckpointError(
                f"checkpoint artifact {agent_id} memory mode is inconsistent")
        if type(trace_managed) is not bool \
                or trace_managed is not bool(config.trace_logging):
            raise InvalidCheckpointError(
                f"checkpoint artifact {agent_id} trace mode is inconsistent")
        if memory_managed:
            expected = str(Path(agent.memory_store.path()).resolve())
            if entry["memory_path"] != expected:
                raise InvalidCheckpointError(
                    f"checkpoint artifact {agent_id} memory path is inconsistent")
        elif entry["memory_path"] is not None:
            raise InvalidCheckpointError(
                f"checkpoint artifact {agent_id} has an unmanaged memory path")
        if trace_managed:
            expected = str(Path(agent.trace_logger.path()).resolve())
            if entry["trace_path"] != expected:
                raise InvalidCheckpointError(
                    f"checkpoint artifact {agent_id} trace path is inconsistent")
            if type(entry["trace_existed"]) is not bool \
                    or type(entry["trace_size"]) is not int \
                    or entry["trace_size"] < 0:
                raise InvalidCheckpointError(
                    f"checkpoint artifact {agent_id} trace metadata is invalid")
            digest = entry["trace_sha256"]
            if entry["trace_existed"]:
                if not isinstance(digest, str) or not re.fullmatch(
                        r"[0-9a-f]{64}", digest):
                    raise InvalidCheckpointError(
                        f"checkpoint artifact {agent_id} trace digest is invalid")
            elif entry["trace_size"] != 0 or digest is not None:
                raise InvalidCheckpointError(
                    f"checkpoint artifact {agent_id} absent trace is inconsistent")
        elif any(entry[key] is not None for key in (
                "trace_path", "trace_sha256")) \
                or entry["trace_existed"] is not False \
                or entry["trace_size"] != 0:
            raise InvalidCheckpointError(
                f"checkpoint artifact {agent_id} has unmanaged trace metadata")


def _read_validated_payload(path: Path) -> dict:
    """Deserialize and validate a complete checkpoint without live mutation."""
    try:
        with path.open("rb") as handle:
            state = pickle.load(handle)
    except FileNotFoundError:
        raise
    except Exception as exc:
        raise InvalidCheckpointError(
            f"checkpoint payload is unreadable: {exc}") from exc

    if not isinstance(state, dict):
        raise InvalidCheckpointError("checkpoint payload must be a dictionary")
    if state.get("schema") != _SCHEMA:
        raise InvalidCheckpointError(
            f"unsupported checkpoint schema {state.get('schema')!r}; "
            f"expected {_SCHEMA}")
    keys = set(state)
    if keys != _STATE_KEYS:
        missing = sorted(_STATE_KEYS - keys)
        extra = sorted(keys - _STATE_KEYS)
        raise InvalidCheckpointError(
            f"checkpoint keys mismatch; missing={missing}, extra={extra}")

    config = state["config"]
    world = state["world"]
    agents = state["agents"]
    recorder = state["recorder"]
    gender_society = state["gender_society"]
    gender_manifest = state["gender_scenario_manifest"]
    if not isinstance(config, SimConfig):
        raise InvalidCheckpointError("checkpoint config has the wrong type")
    try:
        SimConfig.model_validate(config.model_dump())
    except Exception as exc:
        raise InvalidCheckpointError(
            f"checkpoint config is invalid: {exc}") from exc
    if not isinstance(world, SharedWorld):
        raise InvalidCheckpointError("checkpoint world has the wrong type")
    if not isinstance(agents, dict):
        raise InvalidCheckpointError("checkpoint agents must be a dictionary")
    if not isinstance(recorder, MetricsRecorder):
        raise InvalidCheckpointError("checkpoint recorder has the wrong type")
    if not isinstance(gender_society, GenderSociety):
        raise InvalidCheckpointError(
            "checkpoint gender society has the wrong type")
    if gender_society.config is not config:
        raise InvalidCheckpointError(
            "checkpoint gender society/config relationship is inconsistent")
    if gender_manifest is not None and not isinstance(
            gender_manifest, GenderScenario):
        raise InvalidCheckpointError(
            "checkpoint gender scenario manifest has the wrong type")
    try:
        if gender_manifest is not None:
            GenderScenario.model_validate(gender_manifest.model_dump())
        gender_society.state()
        for event in gender_society.pending_events:
            type(event).model_validate(event.model_dump())
    except Exception as exc:
        raise InvalidCheckpointError(
            f"checkpoint gender society is invalid: {exc}") from exc
    if type(world.tick) is not int or world.tick < 0:
        raise InvalidCheckpointError(
            "checkpoint world tick must be a non-negative integer")

    expected_ids = set(range(int(config.n_agents)))
    if set(agents) != expected_ids or set(world.agents) != expected_ids:
        raise InvalidCheckpointError(
            "checkpoint agent ids do not match config/world")
    if world.config is not config:
        raise InvalidCheckpointError(
            "checkpoint world/config relationship is inconsistent")
    _validate_world_internals(world, config)
    _validate_task_manager(
        getattr(world, "task_manager", None),
        label="checkpoint world.task_manager",
        expected_grid_size=config.grid_size,
    )
    if bool(config.tasks_enabled) is not (world.task_manager is not None):
        raise InvalidCheckpointError(
            "checkpoint world task mode is inconsistent with config")

    for agent_id in sorted(expected_ids):
        agent = agents[agent_id]
        body = world.agents[agent_id]
        if not isinstance(agent, CognitiveAgent):
            raise InvalidCheckpointError(
                f"checkpoint agent {agent_id} has the wrong type")
        if agent.agent_id != agent_id or body.id != agent_id:
            raise InvalidCheckpointError(
                f"checkpoint agent {agent_id} identity is inconsistent")
        if agent._shared_world is not world:
            raise InvalidCheckpointError(
                f"checkpoint agent {agent_id} points at another shared world")
        config_refs = (
            agent.config,
            agent.world.config,
            agent.world_model.config,
            agent.working_memory._config,
            agent.memory.config,
            agent.self_model.config,
            agent.gender_experience.config,
        )
        if any(ref is not config for ref in config_refs):
            raise InvalidCheckpointError(
                f"checkpoint agent {agent_id} has split config references")
        _validate_agent_internals(
            agent, agent_id=agent_id, config=config)

    _validate_artifacts(state, expected_ids)

    return state


def _read_validated(path: Path) -> dict:
    """Turn every malformed-payload failure into the public validation error."""
    try:
        return _read_validated_payload(path)
    except (FileNotFoundError, InvalidCheckpointError):
        raise
    except Exception as exc:
        raise InvalidCheckpointError(
            f"checkpoint validation failed safely: {exc}") from exc


def _preflight_state(state: dict) -> dict:
    """Exercise the public state projection without touching the live manager."""
    from core.society import SocietyManager

    probe = SocietyManager.__new__(SocietyManager)
    probe.config = state["config"]
    probe.world = state["world"]
    probe.agents = state["agents"]
    probe.recorder = state["recorder"]
    probe.gender_society = state["gender_society"]
    probe.gender_scenario_manifest = state["gender_scenario_manifest"]
    probe.running = False
    try:
        preview = SocietyManager.state(probe)
        # FastAPI ultimately has to serialize this shape.  Reject broken or
        # non-finite nested values before the live references are replaced.
        json.dumps(preview, allow_nan=False)
        # Exercise this disposable graph in place, then deserialize a fresh
        # graph for commit. This avoids a simultaneous 300+ MB clone and blob.
        state["config"].persist_memory = False
        state["config"].trace_logging = False
        tick_probe = SocietyManager.__new__(SocietyManager)
        tick_probe.config = state["config"]
        tick_probe.world = state["world"]
        tick_probe.agents = state["agents"]
        tick_probe.recorder = state["recorder"]
        tick_probe.gender_society = state["gender_society"]
        tick_probe.gender_scenario_manifest = state[
            "gender_scenario_manifest"]
        tick_probe.running = False
        tick_probe._task = None
        tick_probe.last_run_request = None
        for probe_agent in tick_probe.agents.values():
            probe_agent.memory_store = None
            probe_agent.memory._store = None
            probe_agent._defer_trace_logging = True
        tick_probe.tick()
        json.dumps(SocietyManager.state(tick_probe), allow_nan=False)
    except Exception as exc:
        raise InvalidCheckpointError(
            f"checkpoint state cannot be projected safely: {exc}") from exc
    return preview


def _prepare_memory_file(path: Path, records: list[MemoryRecord]) -> Path:
    temp = _temp_path(path, ".memory.tmp")
    try:
        payload = [record.model_dump(mode="json") for record in records]
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        return temp
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def _prepare_trace_file(path: Path, size: int, digest: str) -> Path:
    if not path.exists() or path.stat().st_size < size:
        raise InvalidCheckpointError(
            f"trace file {path} no longer contains the checkpoint branch")
    if _hash_prefix(path, size) != digest:
        raise InvalidCheckpointError(
            f"trace file {path} prefix differs from the checkpoint branch")
    temp = _temp_path(path, ".trace.tmp")
    try:
        remaining = int(size)
        with path.open("rb") as source, temp.open("wb") as target:
            while remaining > 0:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise InvalidCheckpointError(
                        f"trace file {path} ended before its checkpoint offset")
                target.write(chunk)
                remaining -= len(chunk)
            target.flush()
            os.fsync(target.fileno())
        return temp
    except Exception:
        try:
            temp.unlink()
        except OSError:
            pass
        raise


def _prepare_artifact_files(state: dict) -> list[dict]:
    plan: list[dict] = []
    targets: set[Path] = set()
    try:
        for agent_id, agent in sorted(state["agents"].items()):
            entry = state["artifacts"][agent_id]
            if entry["memory_managed"]:
                target = Path(entry["memory_path"])
                if target in targets:
                    raise InvalidCheckpointError(
                        f"duplicate checkpoint artifact path {target}")
                targets.add(target)
                plan.append({
                    "target": target,
                    "desired": _prepare_memory_file(
                        target, agent.memory._records),
                })
            if entry["trace_managed"]:
                target = Path(entry["trace_path"])
                if target in targets:
                    raise InvalidCheckpointError(
                        f"duplicate checkpoint artifact path {target}")
                targets.add(target)
                desired = (
                    _prepare_trace_file(
                        target,
                        int(entry["trace_size"]),
                        str(entry["trace_sha256"]),
                    )
                    if entry["trace_existed"] else None
                )
                plan.append({"target": target, "desired": desired})
    except Exception:
        for operation in plan:
            desired = operation.get("desired")
            if isinstance(desired, Path):
                try:
                    desired.unlink()
                except OSError:
                    pass
        raise
    return plan


def _rollback_file_swaps(tokens: list[dict]) -> list[str]:
    errors: list[str] = []
    for token in reversed(tokens):
        target = token["target"]
        backup = token.get("backup")
        try:
            if isinstance(backup, Path) and backup.exists():
                # Replace atomically; never unlink the installed target first
                # or a failed recovery could destroy both available copies.
                backup.replace(target)
            elif backup is None and target.exists():
                target.unlink()
        except OSError as exc:
            errors.append(
                f"{target} (recovery copy: {backup}): {exc}")
    return errors


def _apply_artifact_files(plan: list[dict]) -> list[dict]:
    tokens: list[dict] = []
    try:
        for operation in plan:
            target: Path = operation["target"]
            desired: Path | None = operation["desired"]
            backup: Path | None = None
            if target.exists():
                backup = _temp_path(target, ".rollback")
                backup.unlink()
                target.replace(backup)
            token = {"target": target, "backup": backup}
            tokens.append(token)
            if desired is not None:
                desired.replace(target)
        return tokens
    except Exception as exc:
        rollback_errors = _rollback_file_swaps(tokens)
        if rollback_errors:
            raise InvalidCheckpointError(
                "checkpoint file commit failed and rollback was incomplete; "
                "recovery copies were retained: " + "; ".join(rollback_errors)
            ) from exc
        raise


def _finalize_artifact_files(plan: list[dict], tokens: list[dict]) -> None:
    for token in tokens:
        backup = token.get("backup")
        if isinstance(backup, Path):
            try:
                backup.unlink()
            except OSError:
                pass
    for operation in plan:
        desired = operation.get("desired")
        if isinstance(desired, Path):
            try:
                desired.unlink()
            except OSError:
                pass


@_file_locked
def load(manager, name: str) -> dict:
    """Validate fully, then atomically restore the manager in place."""
    stem = _safe(name)
    path = CKPT_DIR / f"{stem}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"checkpoint '{stem}' not found")
    validation_state = _read_validated(path)
    state_preview = _preflight_state(validation_state)
    del validation_state
    gc.collect()
    # Preflight advanced/disarmed its disposable state. Read a pristine graph.
    state = _read_validated(path)
    artifact_plan = _prepare_artifact_files(state)
    # Build the response entirely before touching the live manager.  This keeps
    # even future formatting/shape changes on the validation side of commit.
    info = {
        "name": stem,
        "tick": state["world"].tick,
        "n_agents": len(state["agents"]),
        "state": state_preview,
    }
    prior = {
        "config": manager.config,
        "world": manager.world,
        "agents": manager.agents,
        "recorder": manager.recorder,
        "gender_society": manager.gender_society,
        "gender_scenario_manifest": manager.gender_scenario_manifest,
        "running": manager.running,
        "task": manager._task,
        "last_run_request": manager.last_run_request,
    }
    artifact_tokens: list[dict] = []
    try:
        artifact_tokens = _apply_artifact_files(artifact_plan)
        manager.pause()
        manager.config = state["config"]
        manager.world = state["world"]
        manager.agents = state["agents"]
        manager.recorder = state["recorder"]
        manager.gender_society = state["gender_society"]
        manager.gender_scenario_manifest = state[
            "gender_scenario_manifest"]
    except Exception as exc:
        manager.config = prior["config"]
        manager.world = prior["world"]
        manager.agents = prior["agents"]
        manager.recorder = prior["recorder"]
        manager.gender_society = prior["gender_society"]
        manager.gender_scenario_manifest = prior[
            "gender_scenario_manifest"]
        manager.running = prior["running"]
        manager._task = prior["task"]
        manager.last_run_request = prior["last_run_request"]
        rollback_errors = _rollback_file_swaps(artifact_tokens)
        _finalize_artifact_files(artifact_plan, [])
        if rollback_errors:
            raise InvalidCheckpointError(
                "checkpoint load commit failed and artifact rollback was "
                "incomplete; recovery copies were retained: "
                + "; ".join(rollback_errors)
            ) from exc
        raise
    _finalize_artifact_files(artifact_plan, artifact_tokens)
    return info


@_file_locked
def listing() -> list[dict]:
    """Return metadata for all saved checkpoints, newest first."""
    if not CKPT_DIR.exists():
        return []
    metas: list[dict] = []
    for meta_file in CKPT_DIR.glob("*.json"):
        if not (CKPT_DIR / f"{meta_file.stem}.pkl").exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["compatible"] = meta.get("schema") == _SCHEMA
            metas.append(meta)
        except (ValueError, OSError):
            continue
    return sorted(metas, key=lambda m: str(m.get("saved_at", "")), reverse=True)


@_file_locked
def delete(name: str) -> bool:
    """Delete a checkpoint (both the pickle and its metadata). Returns found."""
    stem = _safe(name)
    found = False
    for suffix in (".pkl", ".json"):
        f = CKPT_DIR / f"{stem}{suffix}"
        if f.exists():
            f.unlink()
            found = True
    return found
