# tests/test_vector_memory.py
"""Unit tests for core.vector_memory (deterministic semantic vector memory).

Pure unit tests: records are constructed by hand, no HTTP, no storage writes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from core.constants import VECTOR_DIM_FEATURES, VECTOR_DIM_TEXT
import core.vector_memory as vector_memory
from core.vector_memory import VectorMemoryIndex
from schemas.models import ActionType, EmotionState, MemoryRecord, Percept, SimConfig


def _percept(kind: str = "food", danger: float = 0.1, novelty: float = 0.3,
             utility: float = 0.2, energy_value: float = 4.0,
             distance: float = 2.0) -> Percept:
    """Build a percept with controllable aggregate features."""
    return Percept(
        object_id=1, kind=kind, dx=1, dy=0, distance=distance,
        danger=danger, novelty=novelty, utility=utility,
        energy_value=energy_value,
    )


def _record(record_id: int, tick: int, action: ActionType, summary: str,
            percepts: list[Percept] | None = None, importance: float = 0.5,
            satisfaction: float = 0.0, fear: float = 0.0) -> MemoryRecord:
    """Build a memory record by hand."""
    return MemoryRecord(
        id=record_id, tick=tick,
        perception=percepts if percepts is not None else [_percept()],
        action=action, target_id=None, result_energy_delta=1.0,
        prediction_error=0.1,
        emotion=EmotionState(satisfaction=satisfaction, fear=fear),
        importance=importance, summary=summary,
    )


def _config(**overrides) -> SimConfig:
    """SimConfig with vector memory on and any extra overrides."""
    return SimConfig(vector_memory_enabled=True, **overrides)


def test_semantic_separation_mutual_nearest_neighbours() -> None:
    """(a) Similar summaries/actions are mutual nearest neighbours."""
    index = VectorMemoryIndex()
    r1 = _record(1, 10, ActionType.INTERACT, "ate a ripe apple near the tree",
                 [_percept("food")])
    r2 = _record(2, 20, ActionType.INTERACT, "ate another apple by the tree",
                 [_percept("food")])
    r3 = _record(3, 30, ActionType.AVOID, "fled from a burning hazard zone",
                 [_percept("hazard", danger=0.9, energy_value=-5.0)])
    v1, v2, v3 = (index.embed_record(r) for r in (r1, r2, r3))
    assert float(v1 @ v2) > float(v1 @ v3)
    assert float(v2 @ v1) > float(v2 @ v3)
    # Vectors have the documented shape and unit norm.
    assert v1.shape == (VECTOR_DIM_FEATURES + VECTOR_DIM_TEXT,)
    assert abs(float(np.linalg.norm(v1)) - 1.0) < 1e-9


def test_embedding_determinism_across_instances() -> None:
    """(b) Same record embeds to the identical vector, even in fresh indexes."""
    record = _record(7, 42, ActionType.EXPLORE, "wandered north past the curio",
                     [_percept("curio", novelty=0.8)])
    index_a = VectorMemoryIndex()
    index_b = VectorMemoryIndex()
    v1 = index_a.embed_record(record)
    v2 = index_a.embed_record(record)
    v3 = index_b.embed_record(record)
    assert np.array_equal(v1, v2)
    assert np.array_equal(v1, v3)
    # Text-only embedding is deterministic too and keeps the feature block zero.
    t1 = index_a.embed_text("apple tree")
    t2 = index_b.embed_text("apple tree")
    assert np.array_equal(t1, t2)
    assert np.all(t1[:VECTOR_DIM_FEATURES] == 0.0)


def test_text_projection_is_fixed_nontrivial_and_orthogonal() -> None:
    """The text block uses the documented fixed seeded projection."""
    assert hasattr(vector_memory, "_TEXT_PROJECTION")
    projection = vector_memory._TEXT_PROJECTION
    assert projection.shape == (VECTOR_DIM_TEXT, VECTOR_DIM_TEXT)
    assert np.allclose(projection.T @ projection, np.eye(VECTOR_DIM_TEXT))
    assert not np.array_equal(projection, np.eye(VECTOR_DIM_TEXT))


def test_embedding_is_stable_across_python_hash_seeds() -> None:
    """A fresh interpreter must reproduce the exact embedding bytes."""
    root = Path(__file__).resolve().parents[1]
    script = (
        "import json; from core.vector_memory import VectorMemoryIndex; "
        "print(json.dumps(VectorMemoryIndex().embed_text('red berries by a tree').tolist()))"
    )
    outputs = []
    for hash_seed in ("1", "987654"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        outputs.append(subprocess.check_output(
            [sys.executable, "-c", script], cwd=root, env=env, text=True,
        ).strip())
    assert json.loads(outputs[0]) == json.loads(outputs[1])


def test_retrieve_respects_k_and_blends_importance() -> None:
    """(c) retrieve returns at most k and importance can beat a close cosine."""
    percepts = [_percept("food")]
    high = _record(1, 100, ActionType.INTERACT, "found food near river",
                   percepts, importance=0.95)
    low = _record(2, 100, ActionType.INTERACT, "found food near river bank",
                  percepts, importance=0.05)
    filler = _record(3, 100, ActionType.REST, "rested in the dark cave",
                     [_percept("hazard", danger=0.7)], importance=0.05)
    records = [high, low, filler]
    index = VectorMemoryIndex()
    config = _config()

    # Pin the premise: 'low' really does have the (slightly) better cosine, so
    # the win of 'high' below is attributable to the importance term, not to a
    # silently reversed cosine ordering.
    query = index.embed_query(percepts, "found food near river bank")
    assert float(index.embed_record(low) @ query) > \
        float(index.embed_record(high) @ query)

    top, mean_cos = index.retrieve(records, percepts, "found food near river bank",
                                   k=2, config=config, now_tick=100)
    assert len(top) == 2
    # 'low' matches the query text slightly better, but the importance term
    # (0.25 * 0.9 gap) dominates the small cosine difference.
    assert top[0].id == high.id
    assert -1.0 <= mean_cos <= 1.0
    # k is respected and the empty cases return the documented defaults.
    only_one, _ = index.retrieve(records, percepts, "food", 1, config, 100)
    assert len(only_one) == 1
    none, cos0 = index.retrieve(records, percepts, "food", 0, config, 100)
    assert none == [] and cos0 == 0.0
    empty, cos_empty = index.retrieve([], percepts, "food", 3, config, 100)
    assert empty == [] and cos_empty == 0.0


def test_search_text_finds_record_by_summary_word() -> None:
    """(d) search_text ranks the record containing the query word first."""
    records = [
        _record(1, 10, ActionType.INTERACT, "gathered berries in the meadow"),
        _record(2, 20, ActionType.AVOID, "escaped the smoking crater",
                [_percept("hazard", danger=0.9)]),
        _record(3, 30, ActionType.REST, "slept beside the warm rock"),
    ]
    index = VectorMemoryIndex()
    results = index.search_text(records, "berries", k=3)
    assert len(results) == 3
    assert results[0][0].id == 1
    # Descending cosine order.
    cosines = [cos for _, cos in results]
    assert cosines == sorted(cosines, reverse=True)
    assert index.search_text(records, "berries", k=0) == []


def test_graph_shape_and_bounds() -> None:
    """(e) graph node/edge keys, edge count bound, similarity in [-1, 1]."""
    records = [
        _record(i, i * 10, ActionType.EXPLORE, f"walked to landmark number {i}",
                [_percept("curio")], satisfaction=0.4, fear=0.1)
        for i in range(1, 7)
    ]
    index = VectorMemoryIndex()
    limit, top_edges = 5, 2
    result = index.graph(records, limit=limit, top_edges=top_edges)
    assert set(result) == {"nodes", "edges"}
    assert len(result["nodes"]) == limit  # last `limit` of the 6 records
    for node in result["nodes"]:
        assert set(node) == {"id", "tick", "action", "importance", "summary",
                             "valence"}
        assert isinstance(node["action"], str)
        assert len(node["summary"]) <= 80
        assert node["valence"] == round(0.4 - 0.1, 3)
    assert len(result["edges"]) <= limit * top_edges
    for edge in result["edges"]:
        assert set(edge) == {"source", "target", "similarity"}
        assert -1.0 <= edge["similarity"] <= 1.0
    # Determinism: same call, identical output.
    assert index.graph(records, limit=limit, top_edges=top_edges) == result


def test_sync_detects_appended_records() -> None:
    """(f) sync rebuilds when the caller's record list drifted."""
    records = [
        _record(1, 10, ActionType.OBSERVE, "watched the horizon"),
        _record(2, 20, ActionType.MOVE, "moved two steps east"),
    ]
    index = VectorMemoryIndex()
    index.rebuild(records)
    assert index.size() == 2
    # No drift: sync is a no-op.
    index.sync(records)
    assert index.size() == 2
    # Drift by append: sync detects the new last record.
    records.append(_record(3, 30, ActionType.REST, "paused to recover"))
    index.sync(records)
    assert index.size() == 3
    # Drift by replacement of the last record (same length, new id).
    records[-1] = _record(9, 35, ActionType.REST, "paused again")
    index.sync(records)
    assert index.size() == 3
    top = index.search_text(records, "paused again", k=1)
    assert top[0][0].id == 9


def test_recency_breaks_ties_between_equal_records() -> None:
    """(g) With equal cosine and importance the more recent record wins."""
    percepts = [_percept("food")]
    old = _record(1, 10, ActionType.INTERACT, "shared the same meal",
                  percepts, importance=0.5)
    recent = _record(2, 400, ActionType.INTERACT, "shared the same meal",
                     percepts, importance=0.5)
    index = VectorMemoryIndex()
    top, _ = index.retrieve([old, recent], percepts, "shared the same meal",
                            k=2, config=_config(), now_tick=400)
    assert top[0].id == recent.id
    assert top[1].id == old.id


def test_retrieve_survives_future_dated_record() -> None:
    """(h) A record dated after now_tick must not overflow the recency pow.

    ``0.5 ** (negative/HALF_LIFE)`` grows without bound and raises
    OverflowError for large negative ages; the age is clamped at 0 instead,
    so a future-dated record simply gets the maximal recency of 1.0.
    """
    percepts = [_percept("food")]
    past = _record(1, 10, ActionType.INTERACT, "shared the same meal",
                   percepts, importance=0.5)
    future = _record(2, 10_000_000, ActionType.INTERACT, "shared the same meal",
                     percepts, importance=0.5)
    index = VectorMemoryIndex()
    top, _ = index.retrieve([past, future], percepts, "shared the same meal",
                            k=2, config=_config(), now_tick=20)
    assert len(top) == 2
    # Clamped recency 1.0 beats the past record's decayed recency.
    assert top[0].id == future.id
