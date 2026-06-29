"""Motivation system: derives functional goal pressures from internal state.

FUNCTIONAL NOTE
---------------
"Goal pressures" are bounded, non-negative functional scalars computed from the
self-model, functional emotions and current percepts. They are intermediate
control variables that bias the agent's policy; they are NOT drives, desires or
felt needs and do not imply any subjective experience.
"""
from __future__ import annotations

from schemas.models import (
    EmotionState,
    GoalPressure,
    Percept,
    SelfModelState,
    SimConfig,
)


class MotivationSystem:
    """Computes a list of named goal pressures used to weight action choice."""

    def __init__(self, config: SimConfig) -> None:
        # Store the reference energy level so the low-energy curve has a baseline
        # even when the self-model's energy is read directly.
        self._initial_energy = float(config.initial_energy) if config.initial_energy > 0 else 1.0

    def evaluate(
        self,
        self_model: SelfModelState,
        emotion: EmotionState,
        percepts: list[Percept],
        prediction_error: float,
        uncertainty: float,
        config: SimConfig,
        n_visible_agents: int = 0,
    ) -> list[GoalPressure]:
        """Return the current functional goal pressures (each >= 0).

        Needs covered: preserve_energy, reduce_danger, explore_novelty,
        improve_prediction, maintain_coherence, achieve_goals, affiliate.
        """
        # Keep the baseline in sync with the live config (config can be patched).
        initial_energy = float(config.initial_energy) if config.initial_energy > 0 else self._initial_energy

        max_danger = max((p.danger for p in percepts), default=0.0)
        max_novelty = max((p.novelty for p in percepts), default=0.0)

        # preserve_energy: low-energy curve — pressure grows as energy fraction
        # drops. Squaring the deficit makes the pressure ramp up sharply when low.
        energy_fraction = max(0.0, min(1.0, self_model.energy / initial_energy))
        energy_deficit = 1.0 - energy_fraction
        preserve_energy = max(0.0, config.energy_drive * (energy_deficit ** 2))

        # reduce_danger: scaled by the caution drive, driven by the most dangerous
        # visible object and reinforced by functional fear.
        reduce_danger = max(
            0.0, config.caution * max(max_danger, emotion.fear)
        )

        # explore_novelty: scaled by the curiosity drive and the most novel object.
        explore_novelty = max(0.0, config.curiosity * max_novelty)

        # improve_prediction: pressure to act so the world model improves, driven
        # by current uncertainty and recent prediction error.
        improve_prediction = max(
            0.0, 0.5 * (max(0.0, uncertainty) + max(0.0, prediction_error))
        )

        # maintain_coherence: scaled by the coherence drive, grows as self-model
        # coherence falls.
        maintain_coherence = max(
            0.0, config.coherence_drive * (1.0 - max(0.0, min(1.0, self_model.coherence)))
        )

        # achieve_goals: active only when explicit goals exist — a constant base
        # plus a small term that grows with the number of active goals.
        if self_model.active_goals:
            achieve_goals = 0.5 + 0.1 * len(self_model.active_goals)
        else:
            achieve_goals = 0.0

        # affiliate: pressure to be near others; high when isolated, relieved by
        # company. Scaled by the affiliation drive. Zero drive => zero pressure.
        isolation = 1.0 / (1.0 + float(max(0, n_visible_agents)))
        affiliate = max(0.0, float(config.affiliation_drive) * isolation)

        return [
            GoalPressure(
                need="preserve_energy",
                pressure=float(preserve_energy),
                description=f"Maintain energy (remaining fraction {energy_fraction:.2f}).",
            ),
            GoalPressure(
                need="reduce_danger",
                pressure=float(reduce_danger),
                description=f"Reduce exposure to danger (max perceived danger {max_danger:.2f}).",
            ),
            GoalPressure(
                need="explore_novelty",
                pressure=float(explore_novelty),
                description=f"Explore novelty (max perceived novelty {max_novelty:.2f}).",
            ),
            GoalPressure(
                need="improve_prediction",
                pressure=float(improve_prediction),
                description=(
                    f"Improve prediction (uncertainty {uncertainty:.2f}, "
                    f"error {prediction_error:.2f})."
                ),
            ),
            GoalPressure(
                need="maintain_coherence",
                pressure=float(maintain_coherence),
                description=f"Maintain self-model coherence (coherence {self_model.coherence:.2f}).",
            ),
            GoalPressure(
                need="achieve_goals",
                pressure=float(achieve_goals),
                description=(
                    f"Pursue {len(self_model.active_goals)} active goal(s)."
                    if self_model.active_goals
                    else "No explicit active goal."
                ),
            ),
            GoalPressure(
                need="affiliate",
                pressure=float(affiliate),
                description=(f"Seek social contact ({n_visible_agents} agent(s) visible)."),
            ),
        ]

    def total_pressure(self, goals: list[GoalPressure]) -> float:
        """Return the summed pressure across all goal pressures (>= 0)."""
        return float(sum(max(0.0, g.pressure) for g in goals))
