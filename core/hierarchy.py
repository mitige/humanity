# core/hierarchy.py
"""Hierarchical generative model (Phase 7) — slow context level + explicit VFE.

FUNCTIONAL NOTE (load-bearing): hierarchical predictive processing posits slow
contextual levels sitting above fast sensorimotor ones: the slow level infers a
discrete latent regime of the environment (abundance / scarcity / peril / calm)
from slow evidence — ambient danger, resource richness, prediction-error
volatility — and modulates the fast world model top-down (here: a bounded
multiplicative factor on its learning rate). The module also makes the
free-energy talk EXPLICIT: a variational free energy scalar is computed each
tick as accuracy (precision-weighted squared prediction error) plus complexity
(KL divergence between successive regime posteriors), then smoothed. This is a
level-2 mechanism: variables and algorithms only. Inferring a regime is not
appraising a situation, and reducing a free-energy scalar is not relief —
nothing subjective is implied; the agent is not conscious.
"""
from __future__ import annotations

import numpy as np

from core.constants import HIERARCHY_REGIMES, HIERARCHY_VFE_EMA
from schemas.models import HierarchyState, Percept, SimConfig

_EPS = 1e-12          # numerical floor for logs and normalizations
_ERROR_WINDOW = 8     # recent prediction errors entering the volatility cue


class HierarchicalModel:
    """Slow discrete-context level over the fast world model (tempered Bayes)."""

    def __init__(self) -> None:
        """Start from a uniform posterior over regimes; VFE at 0, gain neutral."""
        n = len(HIERARCHY_REGIMES)
        self._posterior: np.ndarray = np.full(n, 1.0 / n, dtype=float)
        self._vfe: float = 0.0
        self._lr_factor: float = 1.0

    # ------------------------------------------------------------- accessors
    def lr_factor(self) -> float:
        """Multiplicative modulation of the fast level's learning rate.

        1.0 is neutral (also the value before the first update). Rationale:
        volatile/adverse contexts (peril, scarcity) warrant faster relearning
        of the fast world model, while safe settled contexts (calm, abundance)
        warrant consolidation, i.e. slower updates.
        """
        return float(self._lr_factor)

    # ------------------------------------------------------------- updating
    def update(self, percepts: list[Percept], prediction_error: float,
               recent_errors: list[float], config: SimConfig) -> HierarchyState:
        """One tick of context inference: evidence -> tempered posterior -> gain -> VFE."""
        # 1. Slow evidence scalars extracted from the current perceptual scene.
        if percepts:
            danger = float(np.mean([float(p.danger) for p in percepts]))
            richness = float(np.mean(
                [min(float(p.energy_value) / 10.0, 1.0) for p in percepts]))
        else:
            danger = 0.0
            richness = 0.0
        tail = [float(e) for e in list(recent_errors)[-_ERROR_WINDOW:]]
        volatility = float(np.std(tail)) if len(tail) >= 2 else 0.0

        # 2. Smooth deterministic likelihoods, floored at 0.15 so no regime ever
        # dies. The floor is enforced on every entry: Percept.danger and
        # energy_value are unconstrained floats, and a negative likelihood fed
        # to np.power(x, lr) would turn the whole posterior into NaN for good.
        lik = {
            "peril": 0.15 + danger,
            "abundance": 0.15 + richness,
            "scarcity": 0.15 + max(0.0, 0.5 - richness) * 1.7,
            "calm": 0.15 + max(0.0, 1.0 - 2.0 * danger - 2.0 * volatility),
        }
        likelihood = np.array(
            [max(0.15, lik[r]) for r in HIERARCHY_REGIMES], dtype=float)

        # 3. Tempered Bayesian update: posterior^(1-lr) * likelihood^lr, renormalized.
        lr = float(config.hierarchy_lr)
        previous = self._posterior.copy()
        mixed = np.power(previous, 1.0 - lr) * np.power(likelihood, lr)
        self._posterior = mixed / max(float(mixed.sum()), _EPS)

        # 4. MAP regime; np.argmax keeps the first maximum, so ties break
        # deterministically in HIERARCHY_REGIMES order.
        best = int(np.argmax(self._posterior))
        regime = HIERARCHY_REGIMES[best]
        context_precision = float(self._posterior[best])

        # 5. Top-down learning-rate factor. Rationale: volatile/adverse contexts
        # warrant faster relearning; benign contexts warrant consolidation.
        gain = float(config.hierarchy_gain)
        post = {r: float(self._posterior[i]) for i, r in enumerate(HIERARCHY_REGIMES)}
        raw = 1.0 + gain * (post["peril"] + post["scarcity"]
                            - post["calm"] - post["abundance"])
        self._lr_factor = float(min(1.0 + gain, max(1.0 - gain, raw)))

        # 6. Explicit variational free energy = accuracy + complexity, EMA-smoothed.
        accuracy_term = context_precision * float(prediction_error) ** 2
        complexity_term = float(np.sum(
            self._posterior * np.log((self._posterior + _EPS) / (previous + _EPS))))
        complexity_term = max(0.0, complexity_term)   # KL >= 0; clamp numerical noise
        self._vfe = float((1.0 - HIERARCHY_VFE_EMA) * self._vfe
                          + HIERARCHY_VFE_EMA * (accuracy_term + complexity_term))

        return HierarchyState(
            regime=regime,
            posterior={r: round(post[r], 4) for r in HIERARCHY_REGIMES},
            context_precision=round(context_precision, 4),
            top_down_gain=round(self._lr_factor, 4),
            vfe=round(self._vfe, 6),
            accuracy_term=round(accuracy_term, 6),
            complexity_term=round(complexity_term, 6),
            report=self._report(regime, context_precision, self._lr_factor, self._vfe),
        )

    # ------------------------------------------------------------- reporting
    @staticmethod
    def _report(regime: str, precision: float, factor: float, vfe: float) -> str:
        """One factual sentence about the context level, from the variables."""
        return (f"Context level: regime '{regime}' inferred (precision {precision:.2f}); "
                f"top-down lr factor {factor:.2f}; free energy {vfe:.4f}. "
                "(A discrete latent over variables — inferring a regime is not "
                "appraising a situation; the agent is not conscious.)")
