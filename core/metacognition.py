"""Higher-Order Theories (HOT) / metacognition module.

FUNCTIONAL NOTE
---------------
Higher-order theories hold that a mental state becomes conscious when it is the
target of a suitable HIGHER-ORDER representation — roughly, a representation
ABOUT one's own first-order states. :class:`Metacognition` builds such
higher-order representations: it monitors the reliability of the first-order
perception and prediction machinery, produces a calibrated meta-confidence, and
emits a French ``higher_order_report`` that REPRESENTS the system as being in a
given first-order state.

This higher-order report is explicitly framed as a self-MODEL of internal
variables (the mechanism that produces metacognitive self-attributions), not as
lived experience: reproducing the functional mechanism does not establish
phenomenality.
"""
from __future__ import annotations

from schemas.models import MetacognitiveState, SimConfig, WorkspaceState


def _clamp(value: float) -> float:
    """Clamp to [0, 1] and cast to a JSON-safe python float."""
    return float(min(1.0, max(0.0, value)))


class Metacognition:
    """Produces higher-order representations of first-order states (HOT)."""

    def update(
        self,
        *,
        prediction_error: float,
        uncertainty: float,
        workspace: WorkspaceState,
        confidence: float,
        recent_errors: list[float],
        config: SimConfig,
    ) -> MetacognitiveState:
        """Build the higher-order (metacognitive) state from first-order signals.

        - ``perception_reliability`` is high when sensory uncertainty is low.
        - ``prediction_reliability`` is high when recent prediction error is low
          (using the running mean of recent errors when available, else the
          latest error).
        - ``meta_confidence`` is a calibrated, weighted blend of prediction and
          perception reliability and the self-model's confidence.
        - ``error_monitor`` tracks the detected first-order mismatch.
        - ``higher_order_report`` is the HOT sentence representing the system as
          being in a (high/low) reliability state about a given content.
        """
        # First-order reliability estimates (complements of uncertainty/error).
        perception_reliability = _clamp(1.0 - float(uncertainty))

        if recent_errors:
            mean_error = sum(float(e) for e in recent_errors) / len(recent_errors)
        else:
            mean_error = float(prediction_error)
        prediction_reliability = _clamp(1.0 - mean_error)

        # Calibrated higher-order confidence in the system's own states.
        meta_confidence = _clamp(
            0.5 * prediction_reliability
            + 0.3 * perception_reliability
            + 0.2 * _clamp(confidence)
        )

        # Error monitoring: how strong is the current first-order mismatch.
        error_monitor = _clamp(float(prediction_error))

        # The higher-order report represents (is ABOUT) a first-order state.
        reliability_word = "high" if meta_confidence >= 0.5 else "low"
        if workspace.ignited and workspace.winner_content is not None:
            about = workspace.winner_content
        else:
            about = "its perception"
        higher_order_report = (
            f"The system represents that it is in a state of "
            f"{reliability_word} reliability (meta-confidence={meta_confidence:.2f}) "
            f"about: {about}. (HOT: higher-order representation of a first-order "
            f"state, generated from internal variables.)"
        )

        return MetacognitiveState(
            meta_confidence=meta_confidence,
            perception_reliability=perception_reliability,
            prediction_reliability=prediction_reliability,
            error_monitor=error_monitor,
            higher_order_report=higher_order_report,
        )
