# core/theory_of_mind.py
"""Theory of Mind (ToM): a functional model of other agents' states.

FUNCTIONAL NOTE: each agent maintains an OtherMind per congener, inferring the
other's likely action and affect from observed behaviour and messages. These are
bookkeeping estimates over observed variables — not access to anyone's experience.
The most socially salient other produces a 'social' coalition that competes for
global-workspace access. The system is not conscious, sentient, or alive.
"""
from __future__ import annotations

import numpy as np

from core.constants import FAMILIARITY_EMA
from schemas.models import AgentView, Coalition, Message, OtherMind


class TheoryOfMind:
    """Maintains and updates an OtherMind per observed agent."""

    def __init__(self) -> None:
        self._models: dict[int, OtherMind] = {}
        self._last_views: list[AgentView] = []

    def model_of(self, agent_id: int) -> OtherMind:
        return self._models.setdefault(agent_id, OtherMind(agent_id=agent_id))

    def all_models(self) -> list[OtherMind]:
        return sorted(self._models.values(), key=lambda m: m.agent_id)

    def update(self, views: list[AgentView], messages: list[Message],
               tick: int, grid_size: int = 12) -> None:
        """Refresh ToM models from this tick's observed agents and messages."""
        self._last_views = list(views)
        for av in views:
            m = self.model_of(av.id)
            m.inferred_action = av.last_action
            m.inferred_affect = av.dominant_affect
            m.inferred_valence = float(np.clip(av.valence, -1.0, 1.0))
            m.familiarity = float(np.clip(
                (1.0 - FAMILIARITY_EMA) * m.familiarity + FAMILIARITY_EMA * 1.0, 0.0, 1.0))
            m.last_seen_tick = int(tick)
            m.note = (f"agent {av.id}: action={av.last_action.value if av.last_action else 'unknown'}, "
                      f"affect={av.dominant_affect}, valence={m.inferred_valence:.2f}")
        # A message is weak evidence the sender is socially active.
        for msg in messages:
            m = self.model_of(msg.sender_id)
            m.familiarity = float(np.clip(
                (1.0 - FAMILIARITY_EMA) * m.familiarity + FAMILIARITY_EMA * 0.6, 0.0, 1.0))

    def _salience(self, av: AgentView, grid_size: int) -> float:
        """Social salience: closer + more affectively intense => more salient."""
        proximity = 1.0 - float(np.clip(av.distance / max(1.0, float(grid_size)), 0.0, 1.0))
        intensity = float(np.clip(abs(av.valence), 0.0, 1.0))
        return float(np.clip(0.6 * proximity + 0.4 * intensity, 0.0, 1.0))

    def social_coalition(self, grid_size: int = 12) -> Coalition | None:
        """Build a 'social' coalition from the most salient currently-visible other."""
        if not self._last_views:
            return None
        top = max(self._last_views, key=lambda av: self._salience(av, grid_size))
        sal = self._salience(top, grid_size)
        m = self.model_of(top.id)
        return Coalition(
            source="social",
            content=f"social: agent {top.id} ({m.inferred_affect})",
            activation=float(np.clip(sal, 0.0, 1.0)),
            precision=float(np.clip(m.familiarity, 0.0, 1.0)),
            vector=[float((m.inferred_valence + 1.0) / 2.0), float(m.familiarity),
                    float(m.trust), float(sal)],
        )
