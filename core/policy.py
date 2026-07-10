"""Policy: scores candidate actions and selects one for the current tick.

FUNCTIONAL NOTE
---------------
The policy is a deterministic scoring function over predicted outcomes,
learned preferences, episodic-memory bias, motivation pressures and functional
emotions. It produces an :class:`ActionDecision` with a confidence derived from
the score margin. None of this implies deliberation or volition in any
subjective sense; it is an argmax over internal variables. The agent is not
conscious, sentient, or alive.
"""
from __future__ import annotations

import math

import numpy as np

from core.constants import ACTION_COSTS, PLANNING_BONUS
from schemas.models import (
    ActionDecision,
    ActionType,
    EmotionState,
    GoalPressure,
    MemoryRecord,
    Percept,
    Prediction,
    SalientItem,
    SelfModelState,
    SimConfig,
)

# Thresholds for deciding which target-directed actions are worth proposing.
_HIGH_DANGER = 0.4
_USEFUL = 0.3

# Maps each action to the motivation need(s) whose pressure should amplify it.
# ``individuate`` (the "become someone" drive, gated) is served by self-building
# actions: experiencing the world (explore/observe/move → continuity + a distinct
# taste), relating and expressing (interact/approach/verbalize → a relational,
# voiced self) and integrating (analyze → coherence). REST/AVOID do not build a
# self. These weights are inert unless the individuate pressure is present.
_ACTION_NEED_WEIGHTS: dict[ActionType, dict[str, float]] = {
    ActionType.INTERACT: {"preserve_energy": 1.0, "achieve_goals": 0.5, "individuate": 0.4},
    ActionType.APPROACH: {"preserve_energy": 0.6, "explore_novelty": 0.4, "achieve_goals": 0.5, "individuate": 0.4, "language": 0.3},
    ActionType.AVOID: {"reduce_danger": 1.0},
    ActionType.EXPLORE: {"explore_novelty": 1.0, "improve_prediction": 0.5, "individuate": 0.6, "language": 0.25},
    ActionType.MOVE: {"explore_novelty": 0.5, "improve_prediction": 0.3, "individuate": 0.4, "language": 0.2},
    ActionType.OBSERVE: {"improve_prediction": 0.7, "explore_novelty": 0.3, "individuate": 0.4},
    ActionType.ANALYZE: {"improve_prediction": 1.0, "maintain_coherence": 0.3, "individuate": 0.5},
    ActionType.REST: {"preserve_energy": 1.0},
    # ``language`` (the invent-a-language drive, gated): served above all by
    # SPEAKING — naming what one sees so conventions can spread — and by moving
    # toward potential interlocutors. Inert unless the pressure is present.
    ActionType.VERBALIZE: {"maintain_coherence": 1.0, "individuate": 0.6, "language": 1.2},
}


def _label(action: ActionType, target_id: int | None) -> str:
    """Build a candidate label, e.g. ``"approach#3"`` or ``"rest"``."""
    return f"{action.value}#{target_id}" if target_id is not None else action.value


class Policy:
    """Builds candidate actions and chooses the highest-scoring one."""

    # ------------------------------------------------------------------ #
    # Candidate generation
    # ------------------------------------------------------------------ #
    def candidate_actions(
        self, salient: list[SalientItem], self_model: SelfModelState
    ) -> list[tuple[ActionType, Percept | None]]:
        """Enumerate (action, target) candidates for this tick.

        Always includes the target-free actions (OBSERVE, EXPLORE, REST,
        ANALYZE, VERBALIZE). For the most salient percepts it adds AVOID for
        dangerous objects and APPROACH/INTERACT for useful/energetic ones,
        plus OBSERVE on the single most salient target.
        """
        candidates: list[tuple[ActionType, Percept | None]] = [
            (ActionType.OBSERVE, None),
            (ActionType.EXPLORE, None),
            (ActionType.REST, None),
            (ActionType.ANALYZE, None),
            (ActionType.VERBALIZE, None),
        ]
        for idx, item in enumerate(salient):
            p = item.percept
            if p.danger >= _HIGH_DANGER:
                candidates.append((ActionType.AVOID, p))
            if p.energy_value > 0.0 or p.utility >= _USEFUL:
                candidates.append((ActionType.APPROACH, p))
                candidates.append((ActionType.INTERACT, p))
            # Examine the single most salient target explicitly.
            if idx == 0:
                candidates.append((ActionType.OBSERVE, p))
        return candidates

    # ------------------------------------------------------------------ #
    # Choice
    # ------------------------------------------------------------------ #
    def choose_action(
        self,
        predictions: list[Prediction],
        memory_matches: list[MemoryRecord],
        self_model: SelfModelState,
        motivations: list[GoalPressure],
        emotion: EmotionState,
        salient: list[SalientItem],
        config: SimConfig,
        imagined_best_action: ActionType | None = None,
        learned_values: dict[str, float] | None = None,
        planned_best_action: ActionType | None = None,
    ) -> ActionDecision:
        """Score each predicted candidate and return the best as an ActionDecision."""
        pressure_by_need = {g.need: max(0.0, float(g.pressure)) for g in motivations}

        # Satiation (gated): how full the agent is, in [0,1]. Used to discount the
        # appeal of energy-gaining actions (REST especially) when already sated, so
        # the agent does not collapse into an endless rest/eat loop.
        satiation = 0.0
        if config.satiation_enabled:
            init_energy = float(config.initial_energy) if config.initial_energy > 0 else 1.0
            satiation = max(0.0, min(1.0, float(self_model.energy) / init_energy))

        scored: list[tuple[float, Prediction]] = []
        candidate_scores: dict[str, float] = {}

        for pred in predictions:
            action = pred.action
            label = _label(action, pred.target_id)

            # 1) Predicted value weighted by matching motivation pressure.
            #    Under active inference, ``pred.value == -expected_free_energy``
            #    (the negative EFE = pragmatic value + epistemic value). Higher
            #    is still better, so selecting the argmax of the blended score
            #    minimizes expected free energy.
            need_weights = _ACTION_NEED_WEIGHTS.get(action, {})
            need_align = 1.0 + sum(
                w * pressure_by_need.get(need, 0.0)
                for need, w in need_weights.items()
            )
            value_term = float(pred.value) * need_align

            # 2) Learned preference for this action.
            pref_term = float(self_model.preferences.get(action.value, 0.5))

            # 3) Episodic-memory bias: average energy delta of similar past
            #    records that used this same action.
            memory_bias = self._memory_bias(memory_matches, action)

            # 4) Effort: action cost scaled by fatigue.
            effort_term = ACTION_COSTS.get(action.value, 0.0) * float(emotion.fatigue)

            # 5) Fear-weighted danger aversion.
            danger_term = (
                float(pred.expected_danger) * float(emotion.fear) * float(config.caution)
            )

            # 6) Curiosity-weighted novelty seeking.
            novelty_term = (
                float(pred.expected_novelty)
                * float(emotion.curiosity)
                * float(config.curiosity)
            )

            # 7) Certainty bonus.
            certainty_term = (1.0 - float(pred.uncertainty)) * 0.3

            # Imagination bonus: the action the mental rollout favoured gets a
            # small forward-looking lift (additive; None => no effect).
            imagination_term = 0.3 if (imagined_best_action is not None
                                       and action == imagined_best_action) else 0.0

            # Planning bonus (Phase 7, gated upstream): the first action of the
            # best multi-step EFE policy gets its own additive lift (None => 0).
            planning_term = PLANNING_BONUS if (planned_best_action is not None
                                               and action == planned_best_action) else 0.0

            # Learned-value bonus: the action's learned Q value (additive; None => 0).
            learned_term = (float(config.value_learning_weight) * float(learned_values.get(action.value, 0.0))
                            if learned_values else 0.0)

            # Satiation (gated): when full, IDLE energy-pumping (energy gain with
            # neither novelty nor goal progress — i.e. REST) is discounted, while
            # novel actions are boosted. Eating (energy + goal + novelty) is spared,
            # so a sated agent explores instead of resting endlessly. At low energy
            # (satiation≈0) this vanishes and recovery stays attractive.
            if config.satiation_enabled:
                w = float(config.satiation_weight)
                idle_energy = max(0.0, float(pred.expected_energy_delta)) * (
                    1.0 - min(1.0, float(pred.expected_novelty) + float(pred.expected_goal_progress))
                )
                explore_boost = w * satiation * float(pred.expected_novelty)
                satiation_term = w * satiation * idle_energy / 10.0 - explore_boost
            else:
                satiation_term = 0.0

            # Language drive (Phase 6, gated): speaking is how conventions
            # spread, but VERBALIZE carries ~no EFE value of its own, so the
            # MULTIPLICATIVE need alignment cannot lift it. The drive therefore
            # contributes an ADDITIVE term to the actions that serve it (its
            # entries in the weights table). Zero unless the pressure exists.
            lang_pressure = pressure_by_need.get("language", 0.0)
            language_term = (3.5 * lang_pressure * need_weights.get("language", 0.0)
                             if lang_pressure > 0.0 else 0.0)

            score = (
                value_term
                + pref_term
                + memory_bias
                - effort_term
                - danger_term
                + novelty_term
                + certainty_term
                + imagination_term
                + planning_term
                + learned_term
                + language_term
                - satiation_term
            )
            scored.append((float(score), pred))
            candidate_scores[label] = float(score)

        # Always return a valid action; default to OBSERVE if nothing scored.
        if not scored:
            return ActionDecision(
                action=ActionType.OBSERVE,
                target_id=None,
                direction=None,
                confidence=0.0,
                rationale="No candidate action; defaulting to observation.",
                candidate_scores={},
            )

        scored.sort(key=lambda sp: sp[0], reverse=True)
        best_score, best = scored[0]
        second_score = scored[1][0] if len(scored) > 1 else best_score

        confidence = self._softmax_margin(best_score, second_score)
        direction = self._direction_for(best, salient)
        rationale = self._rationale(best, emotion, pressure_by_need, config)

        return ActionDecision(
            action=best.action,
            target_id=best.target_id,
            direction=direction,
            confidence=round(float(confidence), 4),
            rationale=rationale,
            candidate_scores={k: round(v, 4) for k, v in candidate_scores.items()},
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _memory_bias(memory_matches: list[MemoryRecord], action: ActionType) -> float:
        """Average normalized energy delta of similar past records for ``action``."""
        deltas = [
            float(r.result_energy_delta)
            for r in memory_matches
            if r.action == action
        ]
        if not deltas:
            return 0.0
        # Normalize by ~10 energy units and keep the bias modest.
        return float(np.clip(np.mean(deltas) / 10.0, -1.0, 1.0)) * 0.5

    @staticmethod
    def _softmax_margin(best: float, second: float) -> float:
        """Confidence in ``[0, 1]`` from the softmax margin between top two scores."""
        margin = best - second
        # Logistic squashing of the margin -> 0.5 at margin 0, ->1 as it grows.
        return float(1.0 / (1.0 + math.exp(-margin)))

    @staticmethod
    def _direction_for(
        pred: Prediction, salient: list[SalientItem]
    ) -> list[int] | None:
        """Set a [dx, dy] step in {-1,0,1} for MOVE/EXPLORE; else ``None``."""
        if pred.action not in (ActionType.MOVE, ActionType.EXPLORE):
            return None
        # Head toward the most salient percept if any; else a neutral step.
        if salient:
            p = salient[0].percept
            dx = 1 if p.dx > 0 else (-1 if p.dx < 0 else 0)
            dy = 1 if p.dy > 0 else (-1 if p.dy < 0 else 0)
            return [int(dx), int(dy)]
        return [0, 0]

    @staticmethod
    def _rationale(
        pred: Prediction,
        emotion: EmotionState,
        pressure_by_need: dict[str, float],
        config: SimConfig,
    ) -> str:
        """Compose a concise French rationale citing the dominant factors."""
        factors: list[str] = []
        if pred.expected_energy_delta > 0.5:
            factors.append("expected energy gain")
        if pred.expected_danger > 0.3:
            factors.append("anticipated danger")
        if pred.expected_novelty > 0.3:
            factors.append("expected novelty")
        if pressure_by_need:
            top_need = max(pressure_by_need, key=pressure_by_need.get)
            if pressure_by_need[top_need] > 0.0:
                factors.append(f"pressure '{top_need}'")
        reason = ", ".join(factors) if factors else "highest predicted value"
        target_txt = (
            f" on target {pred.target_id}" if pred.target_id is not None else ""
        )
        return (
            f"Action '{pred.action.value}'{target_txt} chosen by minimizing "
            f"expected free energy (pragmatic + epistemic value), based on "
            f"internal variables: {reason} (value=-EFE {pred.value:.2f}, "
            f"pragmatic {pred.pragmatic_value:.2f}, epistemic "
            f"{pred.epistemic_value:.2f}, uncertainty {pred.uncertainty:.2f})."
        )
