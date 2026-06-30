# core/meta_learning.py
"""Meta-learning (Phase 3): the agent adapts its own learning rate.

FUNCTIONAL NOTE: when recent prediction error is high and falling, learning is
productive, so the effective rate rises; when error is low and flat (already
learned), it falls. A bounded, deterministic function of the error history — no
subjective metacognition is implied.
"""
from __future__ import annotations

from schemas.models import SimConfig


class MetaLearner:
    """Computes a bounded effective learning rate from recent error dynamics."""

    def effective_lr(self, base_lr: float, recent_errors: list[float], config: SimConfig) -> float:
        if not config.meta_learning_enabled or len(recent_errors) < 3:
            return float(base_lr)
        errs = [float(e) for e in list(recent_errors)[-8:]]
        mean_err = sum(errs) / len(errs)
        half = max(1, len(errs) // 2)
        early = sum(errs[:half]) / half
        late = sum(errs[half:]) / max(1, len(errs) - half)
        trend = early - late  # > 0 => error is falling (improving)
        raise_term = max(0.0, trend) * mean_err          # productive learning
        lower_term = (1.0 - mean_err) * 0.3              # settled => ease off
        factor = 1.0 + 3.0 * raise_term - lower_term
        lr = float(base_lr) * factor
        return float(max(float(config.meta_lr_min), min(float(config.meta_lr_max), lr)))
