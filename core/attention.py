"""Attention stage of the cognitive cycle.

FUNCTIONAL NOTE: This module simulates a salience-based attentional bottleneck.
It scores each percept by a weighted sum of functional drivers (danger,
novelty, goal relevance, prediction error, utility) minus a distance penalty,
then keeps only the top ``attention_capacity`` items. The "focus" measure is a
concentration index over the resulting saliency distribution. None of this
implies subjective awareness -- it is a mechanical filter that selects which
internal feature vectors propagate to later stages.
"""
from __future__ import annotations

from schemas.models import (
    EmotionState,
    GoalPressure,
    Percept,
    SalientItem,
    SimConfig,
)


class Attention:
    """Select the most salient percepts under a fixed capacity bottleneck.

    Default weights are exposed as instance attributes so the salience function
    can be tuned without touching :meth:`select`. Each attribute multiplies one
    contribution source in the additive salience model.
    """

    def __init__(self) -> None:
        # Default salience weights (one per contribution source). Tunable.
        self.w_danger: float = 1.0
        self.w_novelty: float = 0.8
        self.w_goal: float = 1.0
        self.w_pe: float = 0.6           # prediction-error driven attention
        self.w_util: float = 0.5
        self.dist_penalty: float = 0.4   # scales the (distance/grid) penalty

    def _goal_relevance(
        self, percept: Percept, goal_pressure_by_need: dict[str, float]
    ) -> float:
        """Map a percept's features onto active goal needs.

        Each percept feature is routed to the goal need it serves and weighted
        by that need's current pressure:

        - ``danger``       -> ``reduce_danger``
        - ``novelty``      -> ``explore_novelty``
        - ``energy_value`` -> ``preserve_energy``

        The result is the sum of feature * matching-need-pressure terms, so a
        percept only becomes goal-relevant when the agent is actually under
        pressure for the need that percept can address.
        """
        relevance = 0.0
        relevance += float(percept.danger) * goal_pressure_by_need.get(
            "reduce_danger", 0.0
        )
        relevance += float(percept.novelty) * goal_pressure_by_need.get(
            "explore_novelty", 0.0
        )
        # Normalize energy_value into ~0..1 (food energy is ~0..10) before
        # routing it to the energy-preservation need.
        norm_energy = min(1.0, float(percept.energy_value) / 10.0)
        relevance += norm_energy * goal_pressure_by_need.get(
            "preserve_energy", 0.0
        )
        return relevance

    def select(
        self,
        percepts: list[Percept],
        goals: list[GoalPressure],
        prediction_error: float,
        emotion: EmotionState,
        config: SimConfig,
    ) -> list[SalientItem]:
        """Score percepts and return the top ``config.attention_capacity`` items.

        Salience model (per percept)::

            saliency = w_danger  * danger      * (1 + fear)
                     + w_novelty * novelty      * curiosity * (1 + emotion.curiosity)
                     + w_goal    * goal_relevance
                     + w_pe      * prediction_error
                     + w_util    * utility
                     - dist_penalty * (distance / grid_size)

        Args:
            percepts: Encoded percepts for the current tick.
            goals: Active goal pressures (used to derive goal relevance).
            prediction_error: Global prediction error in ``0..1``; elevates
                attention uniformly (surprise broadens search).
            emotion: Current emotion state; fear amplifies danger salience and
                curiosity amplifies novelty salience.
            config: Simulation config supplying ``attention_capacity``,
                ``curiosity`` and ``grid_size``.

        Returns:
            A list of :class:`SalientItem` sorted by descending saliency and
            capped at ``config.attention_capacity``. Each item carries a
            ``reasons`` breakdown of per-source contributions for transparency.
        """
        # Aggregate goal pressures by need (max across duplicates, defensive).
        goal_pressure_by_need: dict[str, float] = {}
        for g in goals:
            prev = goal_pressure_by_need.get(g.need, 0.0)
            goal_pressure_by_need[g.need] = max(prev, float(g.pressure))

        fear = float(emotion.fear)
        curiosity_emotion = float(emotion.curiosity)
        pe = float(prediction_error)
        grid = float(max(1, config.grid_size))  # avoid divide-by-zero

        items: list[SalientItem] = []
        for p in percepts:
            danger_term = self.w_danger * float(p.danger) * (1.0 + fear)
            novelty_term = (
                self.w_novelty
                * float(p.novelty)
                * float(config.curiosity)
                * (1.0 + curiosity_emotion)
            )
            goal_term = self.w_goal * self._goal_relevance(
                p, goal_pressure_by_need
            )
            pe_term = self.w_pe * pe
            util_term = self.w_util * float(p.utility)
            dist_term = self.dist_penalty * (float(p.distance) / grid)

            saliency = (
                danger_term
                + novelty_term
                + goal_term
                + pe_term
                + util_term
                - dist_term
            )

            # Per-source contribution breakdown (distance stored as a negative
            # penalty so the components sum to the reported saliency).
            reasons: dict[str, float] = {
                "danger": float(danger_term),
                "novelty": float(novelty_term),
                "goal": float(goal_term),
                "prediction_error": float(pe_term),
                "utility": float(util_term),
                "distance_penalty": float(-dist_term),
            }

            items.append(
                SalientItem(
                    percept=p,
                    saliency=float(saliency),
                    reasons=reasons,
                )
            )

        # Sort by descending saliency and apply the capacity bottleneck.
        items.sort(key=lambda it: it.saliency, reverse=True)
        capacity = max(0, int(config.attention_capacity))
        return items[:capacity]

    def focus(self, salient: list[SalientItem]) -> float:
        """Return attentional concentration in ``[0, 1]``.

        Concentration is the share of total (clipped non-negative) saliency
        held by the single most salient item::

            focus = top_saliency / sum(saliencies)

        A value near 1 means attention is sharply pointed at one item; values
        near ``1/n`` mean it is spread evenly. Returns 0 when there is nothing
        to attend to or total saliency is non-positive.
        """
        if not salient:
            return 0.0
        # Clip to non-negative so penalty-dominated items cannot make the
        # denominator misleading or negative.
        values = [max(0.0, float(it.saliency)) for it in salient]
        total = sum(values)
        if total <= 0.0:
            return 0.0
        top = max(values)
        return float(min(1.0, max(0.0, top / total)))
