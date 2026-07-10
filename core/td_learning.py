# core/td_learning.py
"""Contextual TD(λ) credit assignment (Phase 7): SARSA(λ) with eligibility traces.

FUNCTIONAL NOTE: this is a level-2 functional mechanism — a transparent, tabular
Q[(context, action)] table updated by the classic SARSA(λ) temporal-difference
rule with replacing eligibility traces, extending the Phase-3 EMA learner with
context sensitivity and multi-step credit assignment. 'Context' is a 4-bit
summary of the observation (danger / low energy / novelty / others visible),
and 'credit assignment' is plain arithmetic on table entries: a reward arriving
several ticks after an action still nudges that action's entry through a
decaying trace. Variables and algorithms only; nothing here implies subjective
valuation or experience, and the agent is not conscious.
"""
from __future__ import annotations

from schemas.models import SimConfig

_REWARD_NORM = 10.0        # same reward normalization as the Phase-3 EMA learner
_TRACE_PRUNE = 1e-4        # eligibility traces below this are dropped


class TDLearner:
    """Per-agent contextual SARSA(λ) learner with replacing eligibility traces.

    Updates are one-tick delayed: at tick t the learner finally knows the
    successor (state, action) of tick t-1, so the transition stored at t-1 is
    scored now and its TD error is propagated backwards along the traces.
    """

    def __init__(self) -> None:
        """Start with an empty Q-table, no traces and no pending transition."""
        self.q: dict[tuple[str, str], float] = {}
        self.traces: dict[tuple[str, str], float] = {}
        self._pending: tuple[str, str, float] | None = None
        self._last_td_error: float = 0.0
        self._last_context: str | None = None
        self._last_reward: float = 0.0

    @staticmethod
    def context_key(danger_visible: bool, low_energy: bool, novelty_visible: bool,
                    others_visible: bool) -> str:
        """Encode the 4-bit observation summary as ``d{0|1}e{0|1}n{0|1}s{0|1}``."""
        return (
            f"d{1 if danger_visible else 0}"
            f"e{1 if low_energy else 0}"
            f"n{1 if novelty_visible else 0}"
            f"s{1 if others_visible else 0}"
        )

    def step(self, ctx: str, action_label: str, reward: float,
             config: SimConfig) -> float:
        """One SARSA(λ) step; returns the latest TD error (0.0 on the first call).

        The reward passed here is the one EARNED by (ctx, action_label) now; it
        is normalized (÷10, clipped to [-1, 1]) and stored. The actual update
        scores the PREVIOUS pending transition against the current pair as its
        successor, then decays and prunes the eligibility traces.
        """
        self._last_reward = float(reward)
        r = float(max(-1.0, min(1.0, self._last_reward / _REWARD_NORM)))
        if self._pending is not None:
            ctx_p, a_p, r_p = self._pending
            q_succ = float(self.q.get((ctx, action_label), 0.0))
            q_prev = float(self.q.get((ctx_p, a_p), 0.0))
            delta = r_p + float(config.td_discount) * q_succ - q_prev
            self.traces[(ctx_p, a_p)] = 1.0  # replacing traces
            lr = float(config.value_learning_rate)
            decay = float(config.td_discount) * float(config.td_lambda)
            surviving: dict[tuple[str, str], float] = {}
            for pair, trace in self.traces.items():
                updated = float(self.q.get(pair, 0.0)) + lr * delta * trace
                self.q[pair] = float(max(-1.0, min(1.0, updated)))
                decayed = trace * decay
                if decayed >= _TRACE_PRUNE:
                    surviving[pair] = float(decayed)
            self.traces = surviving
            self._last_td_error = float(delta)
        self._pending = (ctx, action_label, r)
        self._last_context = ctx
        return float(self._last_td_error)

    def values_for(self, ctx: str) -> dict[str, float]:
        """Return the {action_label: Q} view for one context ({} if unseen)."""
        return {a: float(v) for (c, a), v in self.q.items() if c == ctx}

    def n_contexts(self) -> int:
        """Number of distinct contexts with at least one Q entry."""
        return len({c for (c, _a) in self.q})

    @property
    def last_td_error(self) -> float:
        """The TD error of the most recent completed update (0.0 before any)."""
        return float(self._last_td_error)

    @property
    def last_context(self) -> str | None:
        """The context key of the most recent step() call (None before any)."""
        return self._last_context

    @property
    def last_reward(self) -> float:
        """Raw shaped reward supplied by the most recent step() call."""
        return float(self._last_reward)
