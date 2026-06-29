# core/social_emotion.py
"""Social affect: emotional contagion and reputation/trust.

FUNCTIONAL NOTE: contagion nudges an agent's functional affect scalars toward the
affect it perceives in nearby others (weighted by trust); trust is a reputation
scalar updated by the sign of the agent's own reward while engaged with another.
These are bounded control variables, not feelings. The system is not conscious.
"""
from __future__ import annotations

import numpy as np

from schemas.models import AgentView, EmotionState, OtherMind

# Which affect channel each affect-label maps onto for contagion.
_AFFECT_CHANNEL = {
    "fear": "fear", "curiosity": "curiosity", "satisfaction": "satisfaction",
    "fatigue": "fatigue", "confusion": "confusion",
}


def apply_contagion(own: EmotionState, views: list[AgentView],
                    others: dict[int, OtherMind], rate: float) -> EmotionState:
    """Return a new EmotionState nudged toward neighbours' affect (EMA, bounded).

    For each visible other, its dominant affect label contributes to the matching
    channel, weighted by trust and proximity. With no neighbours this is a no-op
    (returns the input unchanged).
    """
    if not views:
        return own
    channels = {"fear": 0.0, "curiosity": 0.0, "satisfaction": 0.0,
                "fatigue": 0.0, "confusion": 0.0}
    weight_sum = 0.0
    for av in views:
        ch = _AFFECT_CHANNEL.get(av.dominant_affect)
        if ch is None:
            continue
        trust = float(others.get(av.id).trust) if others.get(av.id) else 0.5
        proximity = 1.0 - float(np.clip(av.distance / 12.0, 0.0, 1.0))
        w = float(np.clip(trust * (0.5 + 0.5 * proximity), 0.0, 1.0))
        # Intensity of the other's affect proxied by |valence|, min 0.3 so a
        # labelled affect always transmits something.
        channels[ch] += w * max(0.3, float(np.clip(abs(av.valence), 0.0, 1.0)))
        weight_sum += w
    if weight_sum <= 0.0:
        return own
    a = float(np.clip(rate, 0.0, 1.0))

    def blend(cur: float, target: float) -> float:
        return float(np.clip((1.0 - a) * cur + a * float(np.clip(target, 0.0, 1.0)), 0.0, 1.0))

    return EmotionState(
        fear=blend(own.fear, channels["fear"]),
        curiosity=blend(own.curiosity, channels["curiosity"]),
        satisfaction=blend(own.satisfaction, channels["satisfaction"]),
        fatigue=blend(own.fatigue, channels["fatigue"]),
        confusion=blend(own.confusion, channels["confusion"]),
    )


def update_trust(other: OtherMind, reward: float, rate: float) -> None:
    """EMA-update an OtherMind's trust toward 1.0 on positive reward, 0.0 on negative."""
    target = 1.0 if reward > 0 else (0.0 if reward < 0 else other.trust)
    a = float(np.clip(rate, 0.0, 1.0))
    other.trust = float(np.clip((1.0 - a) * other.trust + a * target, 0.0, 1.0))
