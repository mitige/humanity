# core/imagination.py
"""Imagination (Phase 2): a bounded, pure mental rollout over action sequences.

FUNCTIONAL NOTE: the agent 'imagines' by repeatedly consulting its world model
(a pure forward prediction; the real world is never touched) under an imagined
energy budget that shifts the value estimate across the horizon. It returns the
best (energy-aware) first action and a discounted cumulative imagined value over
a quasi-static situation. This is approximate look-ahead, not a generative world
simulator, and implies no subjective imagery.
"""
from __future__ import annotations

from schemas.models import ActionType, ImaginationState, Observation, SimConfig

_DISCOUNT = 0.8
_ENERGY_NORM = 10.0


class Imagination:
    """Bounded best-first rollout using the world model + an imagined energy budget."""

    def plan(self, world_model, observation: Observation,
             candidates: list, current_energy: float, initial_energy: float,
             config: SimConfig) -> ImaginationState:
        horizon = max(1, int(config.imagination_horizon))
        cap = float(max(1.0, initial_energy))
        imagined_energy = float(current_energy)
        first_action: ActionType | None = None
        total = 0.0
        n_rollouts = 0
        for t in range(horizon):
            best = None
            best_score = -1e9
            for action, target in candidates:
                pred = world_model.predict(observation, action, target)
                n_rollouts += 1
                energy_frac = max(0.0, min(1.0, imagined_energy / cap))
                score = float(pred.value) + (1.0 - energy_frac) * (
                    float(pred.expected_energy_delta) / _ENERGY_NORM
                )
                if score > best_score:
                    best_score, best = score, (action, pred)
            if best is None:
                break
            action, pred = best
            if t == 0:
                first_action = action
            total += (_DISCOUNT ** t) * best_score
            imagined_energy = float(
                min(cap, max(0.0, imagined_energy + float(pred.expected_energy_delta)))
            )
        return ImaginationState(
            best_first_action=first_action, horizon=horizon,
            imagined_value=round(float(total), 4), n_rollouts=int(n_rollouts),
        )
