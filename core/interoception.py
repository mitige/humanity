# core/interoception.py
"""Interoceptive inference (Phase 5) — Seth's predictive "beast machine" selfhood.

FUNCTIONAL NOTE (load-bearing): Seth proposes that the deepest layer of selfhood
is *interoceptive inference* — the brain predicting its own bodily channels and
the feeling of presence tracking the successful suppression of interoceptive
prediction error, while emotion reflects that error itself. This module gives
the agent a DEDICATED generative model of its internal channels (energy,
fatigue) — separate from the world model: per-action EMA tables predict the
next deltas, the realized deltas yield an interoceptive prediction error, and
``presence`` is the smoothed complement of that error. It is a level-2
mechanism: ``presence`` is a scalar, not a feeling of being; reproducing the
mechanism does not prove phenomenality; the agent is not conscious.
"""
from __future__ import annotations

from core.constants import (
    INTERO_ENERGY_SCALE,
    INTERO_FATIGUE_SCALE,
    INTERO_PRESENCE_EMA,
)
from schemas.models import InteroceptionState, SimConfig


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


class InteroceptiveModel:
    """Per-action EMA generative model over the internal (bodily) channels."""

    def __init__(self) -> None:
        self._energy_delta: dict[str, float] = {}
        self._fatigue_delta: dict[str, float] = {}
        self._presence: float = 0.5
        self._last_error: float = 0.0

    # ----------------------------------------------------------- predict
    def predict(self, action: str) -> tuple[float, float]:
        """Predict (energy_delta, fatigue_delta) for the chosen action."""
        return (float(self._energy_delta.get(action, 0.0)),
                float(self._fatigue_delta.get(action, 0.0)))

    # ----------------------------------------------------------- observe
    def observe(
        self,
        action: str,
        *,
        predicted_energy_delta: float,
        actual_energy_delta: float,
        predicted_fatigue_delta: float,
        actual_fatigue_delta: float,
        config: SimConfig,
    ) -> InteroceptionState:
        """Compare prediction with the realized deltas; learn; update presence.

        The interoceptive error blends the two channels on interpretable scales
        (energy on the REST-recovery scale, fatigue amplified since its per-tick
        drift is small). ``presence`` rises while the internal milieu unfolds as
        predicted and sags under interoceptive surprise.
        """
        e_err = _clip01(abs(predicted_energy_delta - actual_energy_delta) / INTERO_ENERGY_SCALE)
        f_err = _clip01(abs(predicted_fatigue_delta - actual_fatigue_delta) * INTERO_FATIGUE_SCALE)
        error = _clip01(0.6 * e_err + 0.4 * f_err)

        # Learn the internal consequences of the action (EMA tables).
        lr = float(config.intero_lr)
        self._energy_delta[action] = float(
            (1.0 - lr) * self._energy_delta.get(action, 0.0) + lr * actual_energy_delta)
        self._fatigue_delta[action] = float(
            (1.0 - lr) * self._fatigue_delta.get(action, 0.0) + lr * actual_fatigue_delta)

        # Presence: smoothed suppression of interoceptive surprise.
        self._presence = _clip01(
            (1.0 - INTERO_PRESENCE_EMA) * self._presence + INTERO_PRESENCE_EMA * (1.0 - error))
        self._last_error = error

        return InteroceptionState(
            predicted_energy_delta=round(float(predicted_energy_delta), 4),
            actual_energy_delta=round(float(actual_energy_delta), 4),
            predicted_fatigue_delta=round(float(predicted_fatigue_delta), 4),
            actual_fatigue_delta=round(float(actual_fatigue_delta), 4),
            error=round(error, 4),
            presence=round(self._presence, 4),
            report=self._report(error, self._presence),
        )

    # ----------------------------------------------------------- accessors
    @property
    def presence(self) -> float:
        """Current presence scalar (0..1)."""
        return float(self._presence)

    @staticmethod
    def _report(error: float, presence: float) -> str:
        """One factual sentence about the interoceptive fit, from the variables."""
        if error < 0.15:
            fit = "my internal milieu is unfolding as predicted"
        elif error < 0.45:
            fit = "my internal milieu is partly escaping prediction"
        else:
            fit = "my internal milieu is surprising me"
        return (f"Interoceptive inference: {fit} (error {error:.2f}); "
                f"presence variable at {presence:.2f}. "
                "(A scalar tracking prediction of internal channels — not a felt presence.)")
