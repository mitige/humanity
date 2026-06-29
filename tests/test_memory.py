"""Tests for autobiographical memory and JSON persistence round-trip."""
from __future__ import annotations

import os

import pytest

from core.autobiographical_memory import AutobiographicalMemory
from schemas.models import ActionType, EmotionState, MemoryRecord, Percept, SimConfig
from storage.persistence import MemoryStore


def _percept(object_id: int, danger: float = 0.0, energy_value: float = 0.0) -> Percept:
    """Build a minimal percept for memory feature tests."""
    return Percept(
        object_id=object_id,
        kind="curio",
        dx=0,
        dy=0,
        distance=1.0,
        danger=danger,
        novelty=0.1,
        utility=0.0,
        energy_value=energy_value,
    )


def test_importance_gating_drops_low_importance() -> None:
    """Experiences below the importance threshold are not retained."""
    mem = AutobiographicalMemory(SimConfig(memory_importance_threshold=0.25))
    dropped = mem.store_experience(
        tick=0,
        perception=[],
        action=ActionType.OBSERVE,
        result_energy_delta=0.0,
        prediction_error=0.0,
        emotion=EmotionState(),
    )
    assert dropped is None
    assert mem.count() == 0


def test_importance_gating_keeps_high_importance() -> None:
    """A high-importance experience is retained and assigned a fresh id."""
    mem = AutobiographicalMemory(SimConfig(memory_importance_threshold=0.25))
    kept = mem.store_experience(
        tick=1,
        perception=[_percept(0, danger=0.9)],
        action=ActionType.INTERACT,
        result_energy_delta=-9.0,
        prediction_error=0.8,
        emotion=EmotionState(fear=0.9),
    )
    assert kept is not None
    assert kept.id > 0
    assert mem.count() == 1


def test_explicit_importance_override() -> None:
    """A high explicit importance forces retention regardless of inputs."""
    mem = AutobiographicalMemory(SimConfig(memory_importance_threshold=0.25))
    kept = mem.store_experience(
        tick=0,
        perception=[],
        action=ActionType.REST,
        result_energy_delta=0.0,
        prediction_error=0.0,
        emotion=EmotionState(),
        importance=0.9,
    )
    assert kept is not None
    assert mem.count() == 1


def test_retrieve_similar_returns_most_similar_first() -> None:
    """retrieve_similar ranks the closest feature-vector record first."""
    mem = AutobiographicalMemory(SimConfig(memory_importance_threshold=0.0))
    danger_percepts = [_percept(0, danger=0.9)]
    energy_percepts = [_percept(1, energy_value=9.0)]
    rec_danger = mem.store_experience(
        tick=0, perception=danger_percepts, action=ActionType.AVOID,
        result_energy_delta=-1.0, prediction_error=0.1, emotion=EmotionState(),
        importance=0.5,
    )
    mem.store_experience(
        tick=1, perception=energy_percepts, action=ActionType.INTERACT,
        result_energy_delta=9.0, prediction_error=0.1, emotion=EmotionState(),
        importance=0.5,
    )
    results = mem.retrieve_similar(danger_percepts, k=2)
    assert len(results) == 2
    assert results[0].id == rec_danger.id


def test_retrieve_similar_respects_k_and_empty() -> None:
    """retrieve_similar caps at k and returns [] for empty store or k<=0."""
    mem = AutobiographicalMemory(SimConfig(memory_importance_threshold=0.0))
    assert mem.retrieve_similar([_percept(0)], k=3) == []
    for i in range(4):
        mem.store_experience(
            tick=i, perception=[_percept(i)], action=ActionType.OBSERVE,
            result_energy_delta=0.0, prediction_error=0.0, emotion=EmotionState(),
            importance=0.5,
        )
    assert len(mem.retrieve_similar([_percept(0)], k=2)) == 2
    assert mem.retrieve_similar([_percept(0)], k=0) == []


def test_feature_vector_shape_and_empty() -> None:
    """feature_vector returns a length-6 vector (zeros when no percepts)."""
    fv = AutobiographicalMemory.feature_vector([_percept(0, danger=0.5)])
    assert fv.shape == (6,)
    empty = AutobiographicalMemory.feature_vector([])
    assert empty.shape == (6,)
    assert float(empty.sum()) == 0.0


def test_recent_returns_newest_last() -> None:
    """recent(n) returns the n most recent records with newest last."""
    mem = AutobiographicalMemory(SimConfig(memory_importance_threshold=0.0))
    ids = []
    for i in range(5):
        rec = mem.store_experience(
            tick=i, perception=[_percept(i)], action=ActionType.OBSERVE,
            result_energy_delta=0.0, prediction_error=0.0, emotion=EmotionState(),
            importance=0.5,
        )
        ids.append(rec.id)
    recent = mem.recent(3)
    assert len(recent) == 3
    assert recent[-1].id == ids[-1]


def test_memory_store_roundtrips_records(tmp_path) -> None:
    """MemoryStore writes and reads back records via JSON in a temp path."""
    path = tmp_path / "memory.json"
    store = MemoryStore(path)
    record = MemoryRecord(
        id=1,
        tick=3,
        perception=[_percept(0, danger=0.4)],
        action=ActionType.INTERACT,
        target_id=0,
        result_energy_delta=4.5,
        prediction_error=0.2,
        emotion=EmotionState(curiosity=0.3),
        importance=0.7,
        summary="test record",
    )
    store.save_records([record])
    assert os.path.exists(path)
    loaded = store.load_records()
    assert len(loaded) == 1
    assert loaded[0].id == record.id
    assert loaded[0].action == ActionType.INTERACT
    assert loaded[0].result_energy_delta == pytest.approx(4.5)
    assert loaded[0].summary == "test record"


def test_memory_store_robust_to_missing_file(tmp_path) -> None:
    """load_records returns [] when the backing file does not exist."""
    store = MemoryStore(tmp_path / "does_not_exist.json")
    assert store.load_records() == []


def test_memory_store_clear(tmp_path) -> None:
    """clear() removes persisted records and is safe when already absent."""
    path = tmp_path / "memory.json"
    store = MemoryStore(path)
    store.clear()  # absent file: must not raise
    store.save_records([])
    store.clear()
    assert store.load_records() == []


def test_store_round_trips_through_autobiographical_memory(tmp_path) -> None:
    """A store-backed memory persists retained records to disk."""
    path = tmp_path / "memory.json"
    store = MemoryStore(path)
    mem = AutobiographicalMemory(SimConfig(memory_importance_threshold=0.0), store)
    mem.store_experience(
        tick=0, perception=[_percept(0, danger=0.5)], action=ActionType.AVOID,
        result_energy_delta=-2.0, prediction_error=0.3, emotion=EmotionState(),
        importance=0.6,
    )
    reloaded = MemoryStore(path).load_records()
    assert len(reloaded) == 1
