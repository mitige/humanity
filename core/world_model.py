"""Predictive world model for Humanity.

FUNCTIONAL note: this module implements a simple learned forward model. It holds
per-action expectations over outcome dimensions and refines them with a
delta-rule from observed results. It is a statistical predictor, not a mind: the
"beliefs" and "uncertainty" here are numeric variables, not subjective states.

Active inference (Friston): each :class:`Prediction` now also carries an
expected-free-energy (EFE) decomposition — a pragmatic (goal-directed) value
and an epistemic (information-gain) value. The scalar ``value`` is defined as
``-EFE`` so that "higher value is better" still holds and the existing
argmax-on-value policy selection is unchanged. The delta-rule learning of the
beliefs/uncertainty is untouched.
"""
from __future__ import annotations

import numpy as np

from schemas.models import (
    ActionType,
    Observation,
    Percept,
    Prediction,
    SimConfig,
    StepResult,
)
from core.constants import (
    EMOTION_EMA,
    PREDICTION_DIMS,
)

# Normalizer for the energy_delta dimension (≈ 10 energy units => 1.0 error).
_ENERGY_NORM: float = 10.0


class WorldModel:
    """Learned forward model mapping action labels to expected outcomes.

    ``beliefs[action_label]`` holds expected values for the four PREDICTION_DIMS
    (energy_delta, danger, novelty, goal_progress). These are blended with the
    target's observed features for target-directed actions to form a Prediction.
    """

    def __init__(self, config: SimConfig) -> None:
        """Initialize sensible per-action priors and uncertainty bookkeeping."""
        self.config = config
        self.beliefs: dict[str, dict[str, float]] = {}
        self.uncertainty: dict[str, float] = {}
        for action in ActionType:
            self.beliefs[action.value] = self._prior_for(action)
            self.uncertainty[action.value] = 0.5
        self.current_uncertainty: float = 0.5

    # --------------------------------------------------------------- priors
    @staticmethod
    def _prior_for(action: ActionType) -> dict[str, float]:
        """Reasonable starting expectations per action (kept conservative)."""
        if action == ActionType.REST:
            return {"energy_delta": 5.0, "danger": 0.0, "novelty": 0.0, "goal_progress": 0.0}
        if action == ActionType.INTERACT:
            return {"energy_delta": 2.0, "danger": 0.2, "novelty": 0.3, "goal_progress": 0.3}
        if action == ActionType.APPROACH:
            return {"energy_delta": -1.0, "danger": 0.1, "novelty": 0.2, "goal_progress": 0.2}
        if action == ActionType.AVOID:
            return {"energy_delta": -1.0, "danger": 0.0, "novelty": 0.1, "goal_progress": 0.1}
        if action in (ActionType.OBSERVE, ActionType.ANALYZE):
            return {"energy_delta": -0.6, "danger": 0.0, "novelty": 0.3, "goal_progress": 0.05}
        if action in (ActionType.MOVE, ActionType.EXPLORE):
            return {"energy_delta": -1.2, "danger": 0.05, "novelty": 0.3, "goal_progress": 0.1}
        # VERBALIZE
        return {"energy_delta": -0.1, "danger": 0.0, "novelty": 0.0, "goal_progress": 0.0}

    # --------------------------------------------------------------- predict
    def predict(
        self,
        observation: Observation,
        action: ActionType,
        target: Percept | None,
    ) -> Prediction:
        """Combine learned beliefs with target features into a Prediction."""
        belief = self.beliefs[action.value]
        exp_energy = float(belief["energy_delta"])
        exp_danger = float(belief["danger"])
        exp_novelty = float(belief["novelty"])
        exp_goal = float(belief["goal_progress"])

        # Target-directed actions ground their prediction in observed features.
        if target is not None and action in (
            ActionType.APPROACH,
            ActionType.INTERACT,
            ActionType.AVOID,
            ActionType.OBSERVE,
            ActionType.ANALYZE,
        ):
            if action == ActionType.INTERACT:
                exp_energy = exp_energy * 0.3 + target.energy_value * 0.7
                exp_danger = exp_danger * 0.3 + target.danger * 0.7
                exp_novelty = exp_novelty * 0.3 + target.novelty * 0.7
                exp_goal = exp_goal * 0.4 + (
                    min(target.energy_value / _ENERGY_NORM, 1.0) + 0.3 * target.utility
                ) * 0.6
            elif action == ActionType.APPROACH:
                exp_danger = exp_danger * 0.5 + target.danger * 0.5
                exp_novelty = exp_novelty * 0.5 + target.novelty * 0.5
                exp_goal = exp_goal * 0.5 + 0.2 * (
                    target.utility + min(target.energy_value / _ENERGY_NORM, 1.0)
                ) * 0.5
            elif action == ActionType.AVOID:
                # Avoiding reduces exposure to the target's danger.
                exp_danger = max(0.0, exp_danger * 0.5)
                exp_goal = exp_goal * 0.5 + 0.1 * target.danger * 0.5
            else:  # OBSERVE / ANALYZE
                exp_novelty = exp_novelty * 0.5 + target.novelty * 0.5
                exp_danger = exp_danger * 0.5 + target.danger * 0.5

        exp_danger = float(np.clip(exp_danger, 0.0, 1.0))
        exp_novelty = float(np.clip(exp_novelty, 0.0, 1.0))
        exp_goal = float(max(0.0, exp_goal))
        uncertainty = float(np.clip(self.uncertainty[action.value], 0.0, 1.0))

        # --- Active inference (Friston): expected free energy decomposition. ---
        # The agent is modelled as selecting policies that minimize *expected*
        # free energy (EFE), which splits into a pragmatic (goal-directed) term
        # and an epistemic (information-gain / uncertainty-reduction) term.

        # Pragmatic value: how well the outcome serves the agent's goals/needs
        # (energy gain + goal progress, penalized by anticipated danger).
        pragmatic_value = (
            exp_energy / _ENERGY_NORM
            + exp_goal
            - exp_danger * float(self.config.caution)
        )

        # Epistemic value: expected information gain. Higher when the action is
        # currently uncertain (resolving uncertainty) or expected to be novel.
        epistemic_value = uncertainty + 0.5 * exp_novelty

        # Expected free energy: negative of the precision-weighted sum of the
        # pragmatic and epistemic values. Lower EFE = more desirable policy.
        expected_free_energy = -(
            float(self.config.pragmatic_weight) * pragmatic_value
            + float(self.config.epistemic_weight) * epistemic_value
        )

        # Scalar "value" used by the policy is the negative EFE, so that the
        # existing argmax-on-value selection still picks the best (lowest-EFE)
        # policy without any change to the policy's optimization direction.
        value = -expected_free_energy

        return Prediction(
            action=action,
            target_id=(target.object_id if target is not None else None),
            expected_energy_delta=round(float(exp_energy), 4),
            expected_danger=round(exp_danger, 4),
            expected_novelty=round(exp_novelty, 4),
            expected_goal_progress=round(exp_goal, 4),
            uncertainty=round(uncertainty, 4),
            value=round(float(value), 4),
            pragmatic_value=round(float(pragmatic_value), 4),
            epistemic_value=round(float(epistemic_value), 4),
            expected_free_energy=round(float(expected_free_energy), 4),
        )

    def predict_all(
        self,
        observation: Observation,
        candidates: list[tuple[ActionType, Percept | None]],
    ) -> list[Prediction]:
        """Predict outcomes for every candidate (action, target) pair."""
        return [self.predict(observation, action, target) for action, target in candidates]

    # --------------------------------------------------------------- error
    def compute_error(self, prediction: Prediction, result: StepResult) -> float:
        """Normalized mean absolute error across PREDICTION_DIMS, clipped 0..1."""
        actual = result.actual
        # Map prediction fields to the actual outcome channels.
        predicted = {
            "energy_delta": prediction.expected_energy_delta,
            "danger": prediction.expected_danger,
            "novelty": prediction.expected_novelty,
            "goal_progress": prediction.expected_goal_progress,
        }
        observed = {
            "energy_delta": float(result.energy_delta),
            "danger": float(actual.get("danger", 0.0)),
            "novelty": float(actual.get("novelty", 0.0)),
            "goal_progress": float(actual.get("goal_progress", 0.0)),
        }
        errors: list[float] = []
        for dim in PREDICTION_DIMS:
            diff = abs(predicted[dim] - observed[dim])
            if dim == "energy_delta":
                diff = diff / _ENERGY_NORM
            errors.append(diff)
        mean_error = float(np.mean(errors)) if errors else 0.0
        return round(float(np.clip(mean_error, 0.0, 1.0)), 6)

    # --------------------------------------------------------------- update
    def update(self, prediction: Prediction, result: StepResult, lr_override: float | None = None) -> None:
        """Delta-rule update of beliefs and uncertainty from an observed result.

        Repeated identical (action, outcome) pairs drive beliefs toward the
        observed values, so the per-action prediction error shrinks over time.
        """
        action_label = prediction.action.value
        lr = float(self.config.learning_rate if lr_override is None else lr_override)
        lr = float(max(0.0, min(1.0, lr)))
        belief = self.beliefs[action_label]
        actual = result.actual

        observed = {
            "energy_delta": float(result.energy_delta),
            "danger": float(actual.get("danger", 0.0)),
            "novelty": float(actual.get("novelty", 0.0)),
            "goal_progress": float(actual.get("goal_progress", 0.0)),
        }
        for dim in PREDICTION_DIMS:
            current = float(belief[dim])
            belief[dim] = round(current + lr * (observed[dim] - current), 6)

        # Uncertainty for this action tracks the observed error (EMA).
        error = self.compute_error(prediction, result)
        prev_unc = float(self.uncertainty[action_label])
        new_unc = (1.0 - lr) * prev_unc + lr * error
        self.uncertainty[action_label] = round(float(np.clip(new_unc, 0.0, 1.0)), 6)

        # Global current uncertainty is an EMA of recent error.
        self.current_uncertainty = round(
            float(
                np.clip(
                    (1.0 - EMOTION_EMA) * self.current_uncertainty + EMOTION_EMA * error,
                    0.0,
                    1.0,
                )
            ),
            6,
        )
