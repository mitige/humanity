"""Autobiographical (episodic) memory for the simulated agent.

FUNCTIONAL NOTE: this module stores structured records of past cognitive cycles
and retrieves similar past records by feature similarity. These are operations
over internal variables — they functionally resemble episodic recall but are not
evidence of subjective memory or experience. The agent is not conscious,
sentient, or alive.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from schemas.models import (
    ActionType,
    EmotionState,
    MemoryRecord,
    Percept,
    SimConfig,
)

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from storage.persistence import MemoryStore

# Dimensionality of the aggregated feature vector produced by ``feature_vector``.
_FEATURE_DIM = 6


class AutobiographicalMemory:
    """Importance-gated episodic store with similarity-based retrieval.

    Experiences are only retained when their computed ``importance`` reaches
    ``config.memory_importance_threshold``. Retained records can be persisted via
    an optional :class:`storage.persistence.MemoryStore`.
    """

    def __init__(self, config: SimConfig, store: "MemoryStore | None" = None) -> None:
        """Initialize an empty memory bound to ``config`` and an optional store.

        If ``store`` is provided and already holds records, they are loaded so the
        agent resumes with its previously persisted autobiographical memory.
        """
        self.config = config
        self._store = store
        self._records: list[MemoryRecord] = []
        # Cached feature vectors, kept in lock-step with ``self._records`` (a
        # record's perception never changes, so its vector is computed once at
        # store/load time instead of being recomputed on every retrieval).
        self._vectors: list[np.ndarray] = []
        self._next_id: int = 1
        if store is not None:
            loaded = store.load_records()
            if loaded:
                self._records = list(loaded)
                self._vectors = [self.feature_vector(r.perception) for r in loaded]
                self._next_id = max(r.id for r in loaded) + 1

    # ------------------------------------------------------------------ #
    # Feature extraction
    # ------------------------------------------------------------------ #
    @staticmethod
    def feature_vector(percepts: list[Percept]) -> np.ndarray:
        """Aggregate ``percepts`` into a fixed-length feature vector.

        Layout: ``[mean_danger, mean_novelty, mean_utility, mean_energy_value,
        mean_distance, count]``. With no percepts all values are zero. Used as the
        basis for cosine similarity during retrieval.
        """
        if not percepts:
            return np.zeros(_FEATURE_DIM, dtype=float)
        # Single pure-Python pass: for the tiny percept lists this is markedly
        # faster than five separate ``np.mean`` calls (a per-tick hot path during
        # retrieval), and yields the same means.
        danger = novelty = utility = energy_value = distance = 0.0
        for p in percepts:
            danger += p.danger
            novelty += p.novelty
            utility += p.utility
            energy_value += p.energy_value
            distance += p.distance
        inv = 1.0 / len(percepts)
        return np.array(
            [danger * inv, novelty * inv, utility * inv, energy_value * inv,
             distance * inv, float(len(percepts))],
            dtype=float,
        )

    @staticmethod
    def compute_importance(
        *,
        energy_delta: float,
        danger: float,
        prediction_error: float,
        emotion: EmotionState,
    ) -> float:
        """Compute a salience-style importance score in ``[0, 1]``.

        Importance grows with the magnitude of the energy change, the danger
        experienced, the prediction error (surprise) and the strongest emotion.
        This determines whether an experience is worth retaining.
        """
        max_emotion = max(
            emotion.fear,
            emotion.curiosity,
            emotion.satisfaction,
            emotion.fatigue,
            emotion.confusion,
        )
        # |energy_delta| normalized by a typical scale of ~10 energy units.
        energy_term = min(abs(energy_delta) / 10.0, 1.0)
        raw = (
            0.35 * energy_term
            + 0.25 * _clip01(danger)
            + 0.25 * _clip01(prediction_error)
            + 0.15 * _clip01(max_emotion)
        )
        return float(_clip01(raw))

    # ------------------------------------------------------------------ #
    # Storage
    # ------------------------------------------------------------------ #
    def store_experience(
        self,
        record: MemoryRecord | None = None,
        *,
        tick: int | None = None,
        perception: list[Percept] | None = None,
        action: ActionType | None = None,
        target_id: int | None = None,
        result_energy_delta: float | None = None,
        prediction_error: float | None = None,
        emotion: EmotionState | None = None,
        importance: float | None = None,
        summary: str | None = None,
    ) -> MemoryRecord | None:
        """Store an experience if important enough; return the stored record or ``None``.

        Two calling styles are supported:

        * pass a fully built :class:`MemoryRecord` as ``record``; or
        * pass the individual fields as keyword arguments.

        When ``importance`` is omitted it is derived from the energy delta, danger,
        prediction error and emotion. The record is dropped (returns ``None``) when
        its importance is below ``config.memory_importance_threshold``. A fresh id is
        always assigned, and the record is persisted via the store when present.
        """
        if record is None:
            if (
                tick is None
                or action is None
                or result_energy_delta is None
                or prediction_error is None
                or emotion is None
            ):
                raise ValueError(
                    "store_experience requires either a MemoryRecord or the full "
                    "set of field keyword arguments."
                )
            percepts = perception if perception is not None else []
            danger_now = max((p.danger for p in percepts), default=0.0)
            if importance is None:
                importance = self.compute_importance(
                    energy_delta=result_energy_delta,
                    danger=danger_now,
                    prediction_error=prediction_error,
                    emotion=emotion,
                )
            record = MemoryRecord(
                id=0,  # placeholder, reassigned below
                tick=tick,
                perception=list(percepts),
                action=action,
                target_id=target_id,
                result_energy_delta=float(result_energy_delta),
                prediction_error=float(prediction_error),
                emotion=emotion,
                importance=float(importance),
                summary=summary if summary is not None else "",
            )

        # Importance gate: low-importance experiences are not retained.
        if record.importance < self.config.memory_importance_threshold:
            return None

        # Assign a fresh monotonic id and append (caching its feature vector).
        record = record.model_copy(update={"id": self._next_id})
        self._next_id += 1
        self._records.append(record)
        self._vectors.append(self.feature_vector(record.perception))

        if self._store is not None:
            self._store.save_records(self._records)
        return record

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #
    def retrieve_similar(self, percepts: list[Percept], k: int) -> list[MemoryRecord]:
        """Return up to ``k`` records most similar to ``percepts`` (cosine similarity).

        Records are scored by cosine similarity of their aggregated feature vectors
        and returned in descending similarity order.
        """
        if k <= 0 or not self._records:
            return []
        query = self.feature_vector(percepts)
        # Use the cached per-record vectors (no recomputation per retrieval).
        scored: list[tuple[float, MemoryRecord]] = [
            (_cosine_similarity(query, vector), record)
            for record, vector in zip(self._records, self._vectors)
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in scored[:k]]

    def recent(self, n: int) -> list[MemoryRecord]:
        """Return the ``n`` most recently stored records (newest last)."""
        if n <= 0:
            return []
        return list(self._records[-n:])

    def consolidate(self, k: int, boost: float, prune_threshold: float) -> tuple[int, int]:
        """Offline consolidation: reinforce the top-k important records and forget
        any record whose importance is below ``prune_threshold``.

        Returns (n_boosted, n_pruned). Persists via the store when present.
        """
        if not self._records:
            return 0, 0
        ordered = sorted(self._records, key=lambda r: r.importance, reverse=True)
        n_boost = max(0, int(k))
        boosted = 0
        for record in ordered[:n_boost]:
            new_imp = float(min(1.0, record.importance * float(boost)))
            if new_imp > record.importance:
                record.importance = round(new_imp, 6)
                boosted += 1
        before = len(self._records)
        thr = float(prune_threshold)
        kept_pairs = [
            (r, v) for r, v in zip(self._records, self._vectors) if r.importance >= thr
        ]
        pruned = before - len(kept_pairs)
        if pruned > 0:
            self._records = [r for r, _ in kept_pairs]
            self._vectors = [v for _, v in kept_pairs]
            if self._store is not None:
                self._store.save_records(self._records)
        return boosted, pruned

    def count(self) -> int:
        """Return the number of retained records."""
        return len(self._records)


# ---------------------------------------------------------------------- #
# Numeric helpers
# ---------------------------------------------------------------------- #
def _clip01(value: float) -> float:
    """Clamp ``value`` into ``[0, 1]``."""
    return float(min(1.0, max(0.0, value)))


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two vectors; ``0.0`` when either has zero norm."""
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
