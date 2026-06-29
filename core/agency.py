# core/agency.py
"""Sense of agency (Phase 2): did my own action cause the outcome I predicted?

FUNCTIONAL NOTE: agency = 1 - normalized error between the chosen action's
predicted self-effect (energy delta + goal progress) and the actual outcome.
High when the agent's own action unfolds as predicted (self-causation), low under
surprise. A bounded scalar; no subjective ownership is implied.
"""
from __future__ import annotations

from schemas.models import AgencyState, Prediction, StepResult

_ENERGY_NORM = 10.0


class Agency:
    """Computes an agency scalar from the executed action's prediction vs result."""

    def compute(self, chosen_prediction: Prediction, result: StepResult) -> AgencyState:
        pred_e = float(chosen_prediction.expected_energy_delta)
        pred_g = float(chosen_prediction.expected_goal_progress)
        act_e = float(result.energy_delta)
        act_g = float(result.actual.get("goal_progress", 0.0))
        err_e = min(1.0, abs(pred_e - act_e) / _ENERGY_NORM)
        err_g = min(1.0, abs(pred_g - act_g))
        err = max(0.0, min(1.0, 0.5 * err_e + 0.5 * err_g))
        return AgencyState(
            agency=round(float(1.0 - err), 4),
            predicted_self_effect=round(pred_e + pred_g, 4),
            actual_self_effect=round(act_e + act_g, 4),
        )
