"""Self-model: a functional, updatable model of the agent's own state.

FUNCTIONAL NOTE
---------------
This module maintains a structured :class:`SelfModelState` — energy, confidence,
mood, learned action preferences, capability beliefs, active goals and a short
narrative — plus rolling history buffers used to compute a narrative-coherence
score. Everything here is bookkeeping over internal variables: the "self" it
models is a data structure, not a subject. The agent is not conscious, sentient,
or alive, and the narrative text is generated from these variables.
"""
from __future__ import annotations

import numpy as np

from core.constants import CONFIDENCE_EMA, COHERENCE_WINDOW
from schemas.models import (
    ActionDecision,
    ActionType,
    EmotionState,
    GoalPressure,
    SelfModelState,
    SimConfig,
)

# Stable identity for the simulated agent.
_IDENTITY = "Aurora-fn-01"


def _clip01(value: float) -> float:
    """Clamp a scalar into ``[0, 1]``."""
    return float(min(1.0, max(0.0, value)))


def _clip_unit(value: float) -> float:
    """Clamp a scalar into ``[-1, 1]``."""
    return float(min(1.0, max(-1.0, value)))


class SelfModel:
    """Maintains and updates the agent's functional model of itself."""

    def __init__(self, config: SimConfig) -> None:
        """Initialize a neutral self-model and empty coherence history buffers."""
        self.config = config
        labels = [a.value for a in ActionType]
        self._state = SelfModelState(
            identity=_IDENTITY,
            age_ticks=0,
            energy=float(config.initial_energy),
            confidence=0.5,
            mood=0.0,
            preferences={label: 0.5 for label in labels},
            active_goals=[],
            capability_beliefs={label: 0.5 for label in labels},
            coherence=1.0,
            narrative=(
                "Self-model initialized. Neutral internal variables; "
                "no subjective experience is implied."
            ),
        )
        # Rolling history buffers used to estimate coherence.
        self._pref_history: list[dict[str, float]] = []
        self._mood_history: list[float] = []
        self._goal_history: list[frozenset[str]] = []
        # Rolling stream-of-consciousness: recent ConsciousMoment contents folded
        # into the narrative. Bounded to keep the narrative short.
        self._stream: list[str] = []
        self._stream_max: int = 4

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #
    def update(
        self,
        *,
        decision: ActionDecision,
        result,  # StepResult
        prediction_error: float,
        emotion: EmotionState,
        goals: list[GoalPressure],
        tick: int,
        conscious_contents: str | None = None,
    ) -> None:
        """Update self-state from the latest cycle outcome.

        Confidence and mood are EMA-smoothed; per-action preferences and
        capability beliefs are nudged by the reward sign and prediction accuracy;
        the narrative is refreshed and coherence recomputed over the recent
        history window.

        When ``conscious_contents`` is provided (the bound ConsciousMoment
        contents for this tick), it is folded into a short rolling
        stream-of-consciousness that is appended to the generated narrative. This
        is still text generated from internal variables, not lived experience.
        """
        s = self._state
        action_label = decision.action.value
        pe = _clip01(float(prediction_error))

        # Energy comes directly from the world step.
        s.energy = float(result.new_energy)

        # Confidence: blend decision confidence with prediction accuracy.
        accuracy = 1.0 - pe
        conf_target = 0.5 * float(decision.confidence) + 0.5 * accuracy
        s.confidence = _clip01(
            CONFIDENCE_EMA * conf_target + (1.0 - CONFIDENCE_EMA) * s.confidence
        )

        # Mood (valence): satisfaction minus fear, EMA-smoothed in [-1, 1].
        mood_target = _clip_unit(float(emotion.satisfaction) - float(emotion.fear))
        s.mood = _clip_unit(
            CONFIDENCE_EMA * mood_target + (1.0 - CONFIDENCE_EMA) * s.mood
        )

        # Reward signal for preference learning: energy change + goal progress.
        goal_progress = float(result.actual.get("goal_progress", 0.0))
        reward = float(result.energy_delta) + goal_progress
        lr = float(self.config.learning_rate)
        pref = s.preferences.get(action_label, 0.5)
        # Nudge preference toward 1 on positive reward, toward 0 on negative.
        reward_sign = 1.0 if reward > 0 else (-1.0 if reward < 0 else 0.0)
        s.preferences[action_label] = _clip01(pref + lr * 0.5 * reward_sign)

        # Capability belief: nudged toward predictive accuracy for this action.
        cap = s.capability_beliefs.get(action_label, 0.5)
        s.capability_beliefs[action_label] = _clip01(cap + lr * (accuracy - cap))

        s.age_ticks = int(tick)

        # Record history (snapshots) BEFORE computing coherence so the window
        # includes the current tick.
        self._pref_history.append(dict(s.preferences))
        self._mood_history.append(float(s.mood))
        self._goal_history.append(frozenset(s.active_goals))
        self._trim_history()

        # Fold the bound conscious contents into the rolling stream.
        if conscious_contents:
            text = str(conscious_contents).strip()
            if text:
                self._stream.append(text)
                if len(self._stream) > self._stream_max:
                    self._stream = self._stream[-self._stream_max:]

        s.coherence = self.coherence()
        s.narrative = self._build_narrative(goals)

    def _trim_history(self) -> None:
        """Keep only the last ``COHERENCE_WINDOW`` history snapshots."""
        if len(self._pref_history) > COHERENCE_WINDOW:
            self._pref_history = self._pref_history[-COHERENCE_WINDOW:]
        if len(self._mood_history) > COHERENCE_WINDOW:
            self._mood_history = self._mood_history[-COHERENCE_WINDOW:]
        if len(self._goal_history) > COHERENCE_WINDOW:
            self._goal_history = self._goal_history[-COHERENCE_WINDOW:]

    # ------------------------------------------------------------------ #
    # Coherence
    # ------------------------------------------------------------------ #
    def coherence(self) -> float:
        """Narrative/self stability in ``[0, 1]`` over the recent history window.

        Coherence = 1 - clip((pref_drift + mood_volatility + goal_churn) / 3).
        High when preferences, mood and goals are stable; low when they churn.
        """
        # Preference drift: mean absolute consecutive change across actions.
        pref_drift = 0.0
        if len(self._pref_history) >= 2:
            diffs: list[float] = []
            for prev, cur in zip(self._pref_history, self._pref_history[1:]):
                keys = set(prev) | set(cur)
                step = np.mean(
                    [abs(cur.get(k, 0.5) - prev.get(k, 0.5)) for k in keys]
                )
                diffs.append(float(step))
            pref_drift = float(np.mean(diffs)) if diffs else 0.0

        # Mood volatility: std-dev of recent mood, normalized (mood spans 2).
        mood_volatility = 0.0
        if len(self._mood_history) >= 2:
            mood_volatility = float(np.std(self._mood_history)) / 2.0

        # Goal churn: fraction of consecutive windows where the goal set changed.
        goal_churn = 0.0
        if len(self._goal_history) >= 2:
            changes = sum(
                1
                for prev, cur in zip(self._goal_history, self._goal_history[1:])
                if prev != cur
            )
            goal_churn = changes / (len(self._goal_history) - 1)

        instability = _clip01((pref_drift + mood_volatility + goal_churn) / 3.0)
        return _clip01(1.0 - instability)

    # ------------------------------------------------------------------ #
    # Narrative
    # ------------------------------------------------------------------ #
    def _build_narrative(self, goals: list[GoalPressure]) -> str:
        """Generate a short French narrative summary from current variables."""
        s = self._state
        dominant_goal = ""
        if goals:
            top = max(goals, key=lambda g: g.pressure)
            if top.pressure > 0.0:
                dominant_goal = top.need
        goal_txt = (
            f" Dominant pressure: {dominant_goal}." if dominant_goal else ""
        )
        objectives = (
            f" Active goals: {', '.join(s.active_goals)}."
            if s.active_goals
            else ""
        )
        stream_txt = (
            f" Recent stream: {' | '.join(self._stream)}." if self._stream else ""
        )
        return (
            f"State generated from internal variables ({s.identity}, "
            f"tick {s.age_ticks}): energy={s.energy:.1f}, "
            f"confidence={s.confidence:.2f}, mood={s.mood:.2f}, "
            f"coherence={s.coherence:.2f}.{goal_txt}{objectives}{stream_txt} "
            "No subjective experience is implied."
        )

    # ------------------------------------------------------------------ #
    # Goals / accessors
    # ------------------------------------------------------------------ #
    def set_goal(self, goal: str) -> None:
        """Append a unique active goal to the self-model."""
        goal = goal.strip()
        if goal and goal not in self._state.active_goals:
            self._state.active_goals.append(goal)

    def _apply_agency(self, agency: float) -> None:
        """Nudge confidence toward a high sense of agency (Phase 2, gentle EMA)."""
        a = _clip01(float(agency))
        self._state.confidence = _clip01(0.9 * self._state.confidence + 0.1 * a)

    def snapshot(self) -> SelfModelState:
        """Return a deep copy of the current self-model state."""
        return self._state.model_copy(deep=True)
