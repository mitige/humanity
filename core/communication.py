# core/communication.py
"""Grounded inter-agent communication for the society layer.

FUNCTIONAL NOTE: a VERBALIZE action emits a Message whose content is a grounded
summary of the sender's ConsciousMoment — nothing is invented. Messages are
posted to the SharedWorld and delivered (one tick later, within earshot) by
SharedWorld.observe. On receipt a message becomes a 'communication' coalition
that competes for global-workspace access like any other bid. No LLM, no free
text generation; the system is not conscious, sentient, or alive.
"""
from __future__ import annotations

import numpy as np

from schemas.models import Coalition, ConsciousMoment, Message, OtherMind


def build_message_content(sender_id: int, moment: ConsciousMoment | None) -> tuple[str, list[float]]:
    """Build a grounded (content, vector) pair from the sender's conscious moment."""
    if moment is None:
        return (f"agent {sender_id}: (no content)", [0.0, 0.0, 0.0, 0.0])
    content = f"agent {sender_id}: {moment.contents}"
    vector = [
        float(np.clip(moment.awareness_level, 0.0, 1.0)),
        float((np.clip(moment.valence, -1.0, 1.0) + 1.0) / 2.0),
        float(np.clip(moment.phi_proxy, 0.0, 1.0)),
        float(np.clip(moment.arousal, 0.0, 1.0)),
    ]
    return content, vector


def message_coalition(message: Message, other: OtherMind | None) -> Coalition:
    """Turn a received message into a 'communication' coalition bid.

    Activation = the message's salience (mean of its feature vector, a stand-in
    for how strongly it carries affect/awareness). Precision = trust in the
    sender (an untrusted source is weighted down, exactly like low-precision
    sensory evidence under precision-weighting).
    """
    vec = [float(v) for v in (message.vector or [])]
    activation = float(np.clip(np.mean(vec), 0.0, 1.0)) if vec else 0.3
    trust = float(other.trust) if other is not None else 0.5
    return Coalition(
        source="communication",
        content=f"communication: {message.content}",
        activation=float(np.clip(activation, 0.0, 1.0)),
        precision=float(np.clip(trust, 0.0, 1.0)),
        vector=(vec + [0.0, 0.0, 0.0, 0.0])[:4],
    )
