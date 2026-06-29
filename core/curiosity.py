# core/curiosity.py
"""Curiosity / boredom (Phase 2): intrinsic motivation from learning progress.

FUNCTIONAL NOTE: learning progress is the recent reduction in prediction error.
Positive progress yields an intrinsic reward (learning is engaging); a low, flat
error means the environment is 'solved', raising boredom, which downstream boosts
novelty seeking. These are bounded control scalars, not feelings.
"""
from __future__ import annotations

from schemas.models import CuriosityState, SimConfig


class Curiosity:
    """Computes learning progress, intrinsic reward and boredom from recent error."""

    def update(self, recent_errors: list[float], config: SimConfig) -> CuriosityState:
        if not config.curiosity_enabled or len(recent_errors) < 2:
            return CuriosityState()
        window = min(len(recent_errors), int(config.curiosity_window))
        errs = [float(e) for e in list(recent_errors)[-window:]]
        half = max(1, len(errs) // 2)
        early = sum(errs[:half]) / half
        late = sum(errs[half:]) / max(1, len(errs) - half)
        learning_progress = float(max(-1.0, min(1.0, early - late)))  # >0 => improving
        intrinsic_reward = float(max(0.0, learning_progress))
        mean_err = sum(errs) / len(errs)
        boredom = float(max(0.0, min(1.0, (1.0 - mean_err) * (1.0 - abs(learning_progress)))))
        return CuriosityState(
            learning_progress=round(learning_progress, 4),
            boredom=round(boredom, 4),
            intrinsic_reward=round(intrinsic_reward, 4),
        )
