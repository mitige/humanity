# core/concepts.py
"""Online concept formation (Phase 3): emergent prototype categories.

FUNCTIONAL NOTE: percept feature vectors are clustered online into a bounded set
of prototypes (nearest-prototype assignment with a drift update; a new prototype
is spawned when nothing is close enough and capacity remains). Deterministic
(prototypes are initialised from observed percepts, never randomly). The dominant
recognized concept becomes a 'concept' workspace bid. These are learned
categories over internal features, not subjective concepts.
"""
from __future__ import annotations

import numpy as np

from schemas.models import ConceptState, SimConfig

_SPAWN_SIM_BELOW = 0.6  # spawn a new concept when the best match is weaker than this


class ConceptFormation:
    """Bounded online prototype clustering of percept feature vectors."""

    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.prototypes: list[np.ndarray] = []

    def observe(self, feature_vector, config: SimConfig) -> ConceptState:
        if not config.concepts_enabled:
            return ConceptState()
        x = np.asarray([float(v) for v in feature_vector], dtype=float)
        n = len(self.prototypes)
        if x.size == 0:
            return ConceptState(dominant_concept=None, match=0.0, n_concepts=n)
        cid, sim = self._nearest(x)
        if cid is None or (sim < _SPAWN_SIM_BELOW and n < int(config.n_concepts)):
            self.prototypes.append(x.copy())
            return ConceptState(dominant_concept=n, match=1.0, n_concepts=n + 1)
        # At capacity (or a close-enough match): assimilate to the nearest
        # prototype and drift it toward this percept — intentionally no new spawn.
        lr = float(max(0.0, min(1.0, config.concept_lr)))
        self.prototypes[cid] = self.prototypes[cid] + lr * (x - self.prototypes[cid])
        return ConceptState(dominant_concept=int(cid), match=round(float(sim), 4), n_concepts=n)

    def _nearest(self, x: np.ndarray):
        """Return (index, similarity in [0,1]) of the closest prototype, or (None, 0)."""
        if not self.prototypes:
            return None, 0.0
        best_i, best_sim = 0, -1.0
        for i, p in enumerate(self.prototypes):
            d = float(np.linalg.norm(x - p))
            sim = 1.0 / (1.0 + d)
            if sim > best_sim:
                best_sim, best_i = sim, i
        return best_i, best_sim
