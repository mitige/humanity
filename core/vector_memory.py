# core/vector_memory.py
"""Deterministic semantic vector memory (Phase 7) — numpy-only retrieval index.

FUNCTIONAL NOTE: this module is a level-2 functional mechanism — variables and
algorithms only. It embeds episodic memory records into a fixed 64-dimensional
vector (16 structured-feature dims + 48 hashed char-3-gram text dims) and ranks
them by cosine similarity blended with importance and recency. "Semantic" here
means distributional similarity of records, not understanding; retrieval is a
dot product, not remembering in any subjective sense. Nothing in this module
implies subjective experience; the agent is not conscious.

Determinism: no wall-clock, no unseeded randomness, no Python ``hash()`` (which
is salted per process) — text hashing uses ``zlib.crc32`` exclusively, so the
same record always yields the same vector in every process.
"""
from __future__ import annotations

import zlib

import numpy as np

from core.autobiographical_memory import AutobiographicalMemory
from core.constants import (
    VECTOR_DIM_FEATURES,
    VECTOR_DIM_TEXT,
    VECTOR_RECENCY_HALF_LIFE,
)
from schemas.models import MemoryRecord, Percept, SimConfig

# Total embedding dimensionality (feature block + text block).
_DIM_TOTAL = VECTOR_DIM_FEATURES + VECTOR_DIM_TEXT

# Fixed signed-permutation projection for the hashed text block.  A seeded
# orthogonal transform breaks the accidental meaning of raw hash-bucket axes
# while preserving every cosine exactly.  Signed permutation is preferable to
# QR here: its values are exact across NumPy/BLAS builds, so checkpoint and
# cross-process reproducibility do not depend on floating-point factorization.
_PROJECTION_RNG = np.random.default_rng(0x48554D41)  # "HUMA"
_TEXT_PERMUTATION = _PROJECTION_RNG.permutation(VECTOR_DIM_TEXT)
_TEXT_SIGNS = _PROJECTION_RNG.choice((-1.0, 1.0), size=VECTOR_DIM_TEXT)
_TEXT_PROJECTION = np.zeros((VECTOR_DIM_TEXT, VECTOR_DIM_TEXT), dtype=float)
_TEXT_PROJECTION[np.arange(VECTOR_DIM_TEXT), _TEXT_PERMUTATION] = _TEXT_SIGNS
_TEXT_PROJECTION.setflags(write=False)

# Per-dimension scaling of the 6 aggregate percept features so all live in
# comparable ranges: [danger, novelty, utility, energy_value/10, distance/12,
# count/6]. The first three are already in [0, 1].
_FEATURE_SCALE = np.array([1.0, 1.0, 1.0, 10.0, 12.0, 6.0], dtype=float)

# Weights of the non-cosine terms in the blended retrieval score.
_IMPORTANCE_WEIGHT = 0.25
_RECENCY_WEIGHT = 0.15


def _l2_normalize(vector: np.ndarray) -> np.ndarray:
    """Return ``vector`` scaled to unit L2 norm (zero-safe: zero stays zero)."""
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        return vector
    return vector / norm


class VectorMemoryIndex:
    """Deterministic cosine-similarity index over autobiographical records.

    Vectors are cached in lock-step with the record list handed in by the
    caller; :meth:`sync` performs a cheap drift check (length + last id) and
    rebuilds only when the caller's records changed underneath the index.
    """

    def __init__(self) -> None:
        """Initialize an empty index (no records, no cached vectors)."""
        self._vectors: list[np.ndarray] = []
        self._ids: list[int] = []

    # ------------------------------------------------------------------ #
    # Embedding
    # ------------------------------------------------------------------ #
    def embed_record(self, record: MemoryRecord) -> np.ndarray:
        """Embed a memory record into the deterministic 64-dim vector.

        The feature block aggregates the record's percepts; the text block
        hashes ``"{action} {summary} {sorted percept kinds}"`` (lowercased)
        into signed char-3-gram buckets.
        """
        kinds = " ".join(sorted({p.kind for p in record.perception}))
        text = f"{record.action.value} {record.summary} {kinds}"
        return self._assemble(self._feature_block(record.perception),
                              self._text_block(text))

    def embed_query(self, percepts: list[Percept], context_text: str) -> np.ndarray:
        """Embed a retrieval query from current percepts plus free context text.

        Mirrors :meth:`embed_record`: the feature block comes from ``percepts``
        and the text block from ``context_text`` with the sorted percept kinds
        appended (so kind words can match the record side).
        """
        kinds = " ".join(sorted({p.kind for p in percepts}))
        text = f"{context_text} {kinds}"
        return self._assemble(self._feature_block(percepts),
                              self._text_block(text))

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a text-only query (feature block all zeros)."""
        return self._assemble(np.zeros(VECTOR_DIM_FEATURES, dtype=float),
                              self._text_block(text))

    @staticmethod
    def _feature_block(percepts: list[Percept]) -> np.ndarray:
        """Structured-feature block: the 6 aggregate percept features, scaled.

        Uses :meth:`AutobiographicalMemory.feature_vector` exactly, then scales
        each dimension into a comparable range; the remaining 10 dims stay 0.
        """
        block = np.zeros(VECTOR_DIM_FEATURES, dtype=float)
        raw = AutobiographicalMemory.feature_vector(percepts)
        block[: raw.shape[0]] = raw / _FEATURE_SCALE
        return block

    @staticmethod
    def _text_block(text: str) -> np.ndarray:
        """Hashed char-3-gram block over ``text`` (lowercased, space-padded).

        Each 3-gram is hashed with ``zlib.crc32``; the bucket is ``h % 48`` and
        the sign is ``+1`` when bit 16 of the hash is set, else ``-1``. Signs
        accumulate per bucket. Never uses Python's salted ``hash()``.
        """
        block = np.zeros(VECTOR_DIM_TEXT, dtype=float)
        cleaned = " ".join(text.lower().split())
        if not cleaned:
            return block
        padded = f"  {cleaned}  "
        for i in range(len(padded) - 2):
            gram = padded[i:i + 3]
            h = zlib.crc32(gram.encode("utf-8"))
            bucket = h % VECTOR_DIM_TEXT
            sign = 1.0 if (h >> 16) & 1 else -1.0
            block[bucket] += sign
        return _TEXT_PROJECTION @ block

    @staticmethod
    def _assemble(feature_block: np.ndarray, text_block: np.ndarray) -> np.ndarray:
        """L2-normalize each block separately, concatenate, normalize the whole."""
        full = np.concatenate([_l2_normalize(feature_block),
                               _l2_normalize(text_block)])
        return _l2_normalize(full)

    # ------------------------------------------------------------------ #
    # Index maintenance
    # ------------------------------------------------------------------ #
    def rebuild(self, records: list[MemoryRecord]) -> None:
        """Recompute the cached vector for every record (full rebuild)."""
        self._vectors = [self.embed_record(r) for r in records]
        self._ids = [r.id for r in records]

    def append(self, record: MemoryRecord) -> None:
        """Embed and append a single new record to the index."""
        self._vectors.append(self.embed_record(record))
        self._ids.append(record.id)

    def size(self) -> int:
        """Return the number of vectors currently held by the index."""
        return len(self._vectors)

    def sync(self, records: list[MemoryRecord]) -> None:
        """Rebuild the index if the caller's records drifted from the cache.

        Cheap drift check only: record count plus the id of the last record.
        This catches appends, prunes and reloads without hashing every record;
        when nothing drifted this is a no-op.
        """
        in_sync = len(records) == len(self._ids) and (
            not records or records[-1].id == self._ids[-1]
        )
        if not in_sync:
            self.rebuild(records)

    def vector_map(self, records: list[MemoryRecord]) -> dict[int, np.ndarray]:
        """Return cached record vectors by id, rebuilding only on real drift."""
        self.sync(records)
        return dict(zip(self._ids, self._vectors))

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    def retrieve(self, records: list[MemoryRecord], percepts: list[Percept],
                 context_text: str, k: int, config: SimConfig,
                 now_tick: int) -> tuple[list[MemoryRecord], float]:
        """Return (top-k records, mean cosine of the returned ones).

        Score per record = ``config.semantic_weight * cosine + 0.25 *
        importance + 0.15 * recency`` with ``recency = 0.5 ** ((now_tick -
        record.tick) / VECTOR_RECENCY_HALF_LIFE)`` clipped into [0, 1]. Ties
        break by original record order, so the ranking is fully deterministic.
        Returns ``([], 0.0)`` when there is nothing to return.
        """
        self.sync(records)
        if k <= 0 or not records:
            return [], 0.0
        query = self.embed_query(percepts, context_text)
        cosines = np.stack(self._vectors) @ query
        scored: list[tuple[float, int]] = []
        for idx, record in enumerate(records):
            # Clamp the age at 0 BEFORE the pow: a record dated after now_tick
            # (caller bug, reloaded trace) must yield recency 1.0, and a large
            # negative exponent would raise OverflowError, not return inf.
            age = max(0, now_tick - record.tick)
            recency = 0.5 ** (age / VECTOR_RECENCY_HALF_LIFE)
            recency = min(1.0, max(0.0, recency))
            score = (
                float(config.semantic_weight) * float(cosines[idx])
                + _IMPORTANCE_WEIGHT * float(record.importance)
                + _RECENCY_WEIGHT * recency
            )
            scored.append((score, idx))
        scored.sort(key=lambda item: (-item[0], item[1]))
        top = scored[:k]
        mean_cosine = float(np.mean([float(cosines[i]) for _, i in top]))
        return [records[i] for _, i in top], round(mean_cosine, 4)

    def search_text(self, records: list[MemoryRecord], text: str,
                    k: int) -> list[tuple[MemoryRecord, float]]:
        """Pure-cosine text search: top-k ``(record, cosine)`` pairs, descending.

        Uses :meth:`embed_text` for the query (feature block zeroed), so only
        the text blocks of the records can contribute to the score.
        """
        self.sync(records)
        if k <= 0 or not records:
            return []
        query = self.embed_text(text)
        cosines = np.stack(self._vectors) @ query
        order = sorted(range(len(records)),
                       key=lambda i: (-float(cosines[i]), i))
        return [(records[i], round(float(cosines[i]), 4)) for i in order[:k]]

    # ------------------------------------------------------------------ #
    # Similarity graph
    # ------------------------------------------------------------------ #
    def graph(self, records: list[MemoryRecord], limit: int = 60,
              top_edges: int = 3) -> dict:
        """Similarity graph over the last ``limit`` records.

        Nodes carry ``{id, tick, action, importance, summary, valence}`` where
        valence = satisfaction - fear. Edges connect each node to its
        ``top_edges`` nearest others by cosine, deduplicated (i < j) and sorted
        deterministically. Edge count is therefore <= ``limit * top_edges``.
        """
        self.sync(records)
        limit = max(0, int(limit))
        subset = records[-limit:] if limit > 0 else []
        vectors = self._vectors[len(records) - len(subset):]
        nodes = [
            {
                "id": r.id,
                "tick": r.tick,
                "action": r.action.value,
                "importance": round(float(r.importance), 3),
                "summary": r.summary[:80],
                "valence": round(float(r.emotion.satisfaction - r.emotion.fear), 3),
            }
            for r in subset
        ]
        n = len(subset)
        edge_map: dict[tuple[int, int], float] = {}
        for i in range(n):
            sims = [
                (float(np.dot(vectors[i], vectors[j])), j)
                for j in range(n)
                if j != i
            ]
            sims.sort(key=lambda item: (-item[0], item[1]))
            for cosine, j in sims[: max(0, int(top_edges))]:
                key = (min(i, j), max(i, j))
                if key not in edge_map:
                    edge_map[key] = cosine
        edges = [
            {
                "source": subset[i].id,
                "target": subset[j].id,
                "similarity": round(edge_map[(i, j)], 3),
            }
            for i, j in sorted(edge_map)
        ]
        return {"nodes": nodes, "edges": edges}
