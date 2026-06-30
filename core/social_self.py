# core/social_self.py
"""Relational self (looking-glass self / social mirror).

FUNCTIONAL NOTE (load-bearing): this computes how an agent is *regarded by the
others who model it* — a social anchor for the self-model, in the spirit of
Cooley's "looking-glass self", Mead, Hegelian recognition and Lacan's mirror
stage, rendered as plain variables over the existing theory-of-mind estimates.
It is a level-2 mechanism: reproducing it does NOT prove phenomenality, and the
agent is not conscious, sentient, or alive. An agent nobody models gets a
neutral, inert relational self (``social_presence == 0``).
"""
from __future__ import annotations

import numpy as np

from schemas.models import OtherMind, RelationalSelf


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def reflected_appraisal(
    models_of_me: list[OtherMind],
    n_others: int,
    *,
    now_tick: int,
    recency: int = 3,
) -> RelationalSelf:
    """How this agent is currently regarded by the others who model it.

    ``models_of_me`` are the ``OtherMind`` records that *other* agents hold about
    this agent. Only observers who have actually seen it recently
    (``familiarity > 0`` and seen within ``recency`` ticks) count, so a stale or
    never-met other does not contribute. Each observer's regard blends its
    ``trust`` (reputation) and ``inferred_valence`` (how positively it reads this
    agent), both mapped to ``[0, 1]``.

    Returns a neutral, inert ``RelationalSelf`` (``social_presence == 0``,
    ``reflected_appraisal == 0.5``) when nobody currently models the agent — the
    isolated case, by construction indistinguishable from "no social self".
    """
    observers = [
        m for m in models_of_me
        if float(m.familiarity) > 0.0 and (int(now_tick) - int(m.last_seen_tick)) <= int(recency)
    ]
    n = len(observers)
    if n == 0:
        return RelationalSelf(
            reflected_appraisal=0.5, social_presence=0.0, regard_consistency=0.0,
            n_observers=0, note="no one currently models this agent (isolation)")

    regards = [
        0.5 * _clip01(float(m.trust)) + 0.5 * _clip01((float(m.inferred_valence) + 1.0) / 2.0)
        for m in observers
    ]
    appraisal = float(np.mean(regards))
    presence = _clip01(n / max(1, int(n_others)))
    # Agreement among observers: low spread => a stable, consistent mirror.
    consistency = _clip01(1.0 - float(np.std(regards))) if n >= 2 else 1.0
    return RelationalSelf(
        reflected_appraisal=_clip01(appraisal),
        social_presence=presence,
        regard_consistency=consistency,
        n_observers=int(n),
        note=f"regarded by {n}/{max(1, int(n_others))} others (appraisal {appraisal:.2f})",
    )
