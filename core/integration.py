"""Integrated-information proxy (IIT-inspired) for Humanity v2.

HONESTY note: This is a *heuristic proxy*, NOT a real Integrated Information
Theory (IIT, Tononi) Phi computation. True Phi requires evaluating every
bipartition of the system's cause-effect structure to find the minimum
information partition (MIB), which is computationally intractable here and would
demand a full cause-effect repertoire we do not model. Instead we approximate the
two intuitions IIT formalizes:

  * differentiation (the state is one of many possible / informative) via the
    normalized Shannon entropy of the competition's activation distribution, and
  * integration (the parts act as a unified whole, not independently) via the
    broadcast-bound mean pairwise cosine similarity of the coalition vectors.

phi_proxy = sqrt(differentiation * integration). This is a deliberately simple,
transparent stand-in and must not be read as a measurement of consciousness.
"""
from __future__ import annotations

import numpy as np

from schemas.models import Coalition, IntegrationState


class IntegrationMonitor:
    """Computes a bounded, heuristic Phi-proxy from the workspace competition."""

    _PARTITION_LABEL = "MIB-proxy: activation-entropy x broadcast-bound similarity"

    def phi_proxy(
        self,
        coalitions: list[Coalition],
        broadcast_strength: float,
    ) -> IntegrationState:
        """Return an IntegrationState with a heuristic phi_proxy in [0,1].

        differentiation D = normalized Shannon entropy of the normalized
            activation distribution p_i (0 when one coalition dominates, 1 when
            activation is spread uniformly across many coalitions).
        integration I = broadcast_strength * mean_pairwise_cosine_similarity of the
            coalition feature vectors (clipped to [0,1]); with fewer than 2 usable
            vectors, I = broadcast_strength.
        phi_proxy = sqrt(max(0,D) * max(0,I)), clipped to [0,1].
        """
        n_elements = len(coalitions)
        bcast = float(np.clip(float(broadcast_strength), 0.0, 1.0))

        # Degenerate cases: no integrated structure to speak of.
        if n_elements == 0:
            return IntegrationState(
                phi_proxy=0.0,
                n_elements=0,
                partition=self._PARTITION_LABEL,
                differentiation=0.0,
                integration=0.0,
            )

        # --- Differentiation: normalized Shannon entropy of activations. ---
        activations = np.array([max(0.0, float(c.activation)) for c in coalitions], dtype=float)
        total = float(np.sum(activations))
        if total > 0.0:
            p = activations / total
        else:
            # Uniform fallback if every activation is zero.
            p = np.full(n_elements, 1.0 / n_elements)

        if n_elements > 1:
            # Shannon entropy in nats, normalized by log(n) -> [0,1].
            nz = p[p > 0.0]
            entropy = float(-np.sum(nz * np.log(nz)))
            differentiation = float(entropy / np.log(n_elements))
        else:
            # A single element cannot be differentiated against alternatives.
            differentiation = 0.0
        differentiation = float(np.clip(differentiation, 0.0, 1.0))

        # --- Integration: broadcast-bound mean pairwise cosine similarity. ---
        vectors = [
            np.array([float(v) for v in c.vector], dtype=float)
            for c in coalitions
            if c.vector
        ]
        if len(vectors) >= 2:
            similarity = self._mean_pairwise_cosine(vectors)
            integration = float(np.clip(bcast * similarity, 0.0, 1.0))
        else:
            # Too few vectors to assess inter-part binding: lean on broadcast.
            integration = bcast

        # --- Phi proxy: geometric mean of the two bounded quantities. ---
        phi = float(np.sqrt(max(0.0, differentiation) * max(0.0, integration)))
        phi = float(np.clip(phi, 0.0, 1.0))

        return IntegrationState(
            phi_proxy=round(phi, 6),
            n_elements=int(n_elements),
            partition=self._PARTITION_LABEL,
            differentiation=round(differentiation, 6),
            integration=round(integration, 6),
        )

    # ------------------------------------------------------ cosine helper
    @staticmethod
    def _mean_pairwise_cosine(vectors: list[np.ndarray]) -> float:
        """Mean cosine similarity over all distinct vector pairs, clipped to [0,1].

        Vectors are zero-padded to a common length so heterogeneous feature
        vectors can still be compared. Zero-norm vectors contribute 0 similarity.
        """
        max_len = max(v.shape[0] for v in vectors)
        padded = [
            np.concatenate([v, np.zeros(max_len - v.shape[0])]) if v.shape[0] < max_len else v
            for v in vectors
        ]
        sims: list[float] = []
        for i in range(len(padded)):
            for j in range(i + 1, len(padded)):
                a, b = padded[i], padded[j]
                na = float(np.linalg.norm(a))
                nb = float(np.linalg.norm(b))
                if na == 0.0 or nb == 0.0:
                    sims.append(0.0)
                else:
                    sims.append(float(np.dot(a, b) / (na * nb)))
        if not sims:
            return 0.0
        # Cosine can be negative; clip into [0,1] since negative "anti-binding"
        # should not count as integration.
        return float(np.clip(float(np.mean(sims)), 0.0, 1.0))
