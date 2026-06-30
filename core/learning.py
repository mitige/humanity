# core/learning.py
"""Learned action values (Phase 3): an interpretable per-action value table.

FUNCTIONAL NOTE: each action accumulates an EMA of the (normalized) reward it
yielded — a transparent Q[action] table, not a neural network. The policy adds a
small bonus for high-value actions. Bookkeeping over internal variables; no
subjective preference is implied.
"""
from __future__ import annotations

_REWARD_NORM = 10.0


class PolicyLearner:
    """Per-agent table of EMA action values updated from realized reward."""

    def __init__(self) -> None:
        self.q: dict[str, float] = {}
        self.last_reward: float = 0.0

    def update(self, action_label: str, reward: float, lr: float) -> None:
        """EMA-update Q[action] toward the normalized reward (clipped to [-1,1])."""
        self.last_reward = float(reward)
        r = float(max(-1.0, min(1.0, float(reward) / _REWARD_NORM)))
        a = float(max(0.0, min(1.0, float(lr))))
        prev = float(self.q.get(action_label, 0.0))
        self.q[action_label] = float(max(-1.0, min(1.0, prev + a * (r - prev))))

    def bonus(self, action_label: str) -> float:
        """Return the learned value of an action (0.0 if never updated)."""
        return float(self.q.get(action_label, 0.0))

    def values(self) -> dict[str, float]:
        """Return a copy of the full action-value table."""
        return {k: float(v) for k, v in self.q.items()}
