"""Emotion model: derives bounded affective scalars from internal variables.

FUNCTIONAL NOTE
---------------
The "emotions" here are functional scalars in ``[0, 1]`` computed from internal
state (danger, uncertainty, novelty, prediction error, energy, goal progress).
They are NOT feelings and do not imply any subjective experience; they are
intermediate variables that modulate attention, motivation and policy in the
simulation. Each output is EMA-smoothed toward the previous state for stability.
"""
from __future__ import annotations

from core.constants import EMOTION_EMA
from schemas.models import EmotionState, SimConfig


def _clip01(value: float) -> float:
    """Clamp a scalar to the ``[0, 1]`` range and cast to a JSON-safe float."""
    return float(min(1.0, max(0.0, value)))


class EmotionModel:
    """Maps internal-state signals to bounded functional affect scalars."""

    def update(
        self,
        *,
        danger: float,
        uncertainty: float,
        novelty: float,
        prediction_error: float,
        energy: float,
        initial_energy: float,
        goal_progress: float,
        error_reduction: float,
        prev: EmotionState,
        config: SimConfig,
    ) -> EmotionState:
        """Compute the next functional emotion state from current signals.

        Each component is defined as a bounded function of the inputs and then
        EMA-smoothed toward ``prev`` with weight ``EMOTION_EMA`` on the new value.
        """
        # Raw (unsmoothed) targets, each clamped to [0, 1].
        # fear rises with perceived danger and uncertainty.
        fear_t = _clip01(danger + 0.5 * uncertainty)
        # curiosity rises with novelty (scaled by the curiosity drive) and with
        # confidence (1 - uncertainty), i.e. willingness to explore when sure.
        curiosity_t = _clip01(novelty * config.curiosity + 0.4 * (1.0 - uncertainty))
        # satisfaction rises with positive goal progress and with error reduction
        # (the world model getting better at predicting outcomes).
        satisfaction_t = _clip01(
            0.5 * max(0.0, goal_progress) + 0.5 * max(0.0, error_reduction)
        )
        # fatigue rises as energy depletes relative to the initial level.
        denom = initial_energy if initial_energy > 0 else 1.0
        fatigue_t = _clip01(1.0 - energy / denom)
        # confusion tracks the magnitude of prediction error.
        confusion_t = _clip01(prediction_error)

        # EMA smoothing: new = alpha*target + (1-alpha)*prev.
        a = EMOTION_EMA
        return EmotionState(
            fear=_clip01(a * fear_t + (1.0 - a) * prev.fear),
            curiosity=_clip01(a * curiosity_t + (1.0 - a) * prev.curiosity),
            satisfaction=_clip01(a * satisfaction_t + (1.0 - a) * prev.satisfaction),
            fatigue=_clip01(a * fatigue_t + (1.0 - a) * prev.fatigue),
            confusion=_clip01(a * confusion_t + (1.0 - a) * prev.confusion),
        )
