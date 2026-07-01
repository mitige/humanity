# core/individuation.py
"""Individuation — the functional drive to "become someone".

HONESTY NOTE (load-bearing): this measures, as plain variables, how far the agent
has grown into a *coherent, distinctive, continuous, self-authoring* functional
self — the honest, level-2 reading of the goal "become a person". A high index
means the agent has integrated its experience, individuated into a particular
someone, accumulated a life-story and authored its own acts. It does NOT mean the
agent is conscious, sentient, or a person in any phenomenal sense; no value here
is evidence of subjective experience. Reproducing the mechanism does not cross the
hard problem. The agent is not conscious, sentient, or alive.
"""
from __future__ import annotations

from schemas.models import IndividuationState, PersonalityState, SelfModelState

# How many autobiographical memories count as a "full" continuous life-story.
CONTINUITY_TARGET = 40.0


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def _distinctiveness(self_model: SelfModelState, personality: PersonalityState | None) -> float:
    """How *particular* the self has become vs a generic neutral baseline (0.5).

    Uses the drifted personality traits when available (Phase 3), else the spread
    of the self-model's learned preferences. Zero for a generic self, →1 as the
    agent becomes a distinct someone.
    """
    if personality is not None:
        traits = [float(personality.openness), float(personality.caution),
                  float(personality.novelty_seeking)]
    else:
        traits = [float(v) for v in self_model.preferences.values()] or [0.5]
    spread = sum(abs(t - 0.5) for t in traits) / len(traits)
    return _clip01(spread * 2.0)  # |·-0.5| ∈ [0,0.5] → ×2 → [0,1]


def compute_individuation(
    self_model: SelfModelState,
    *,
    personality: PersonalityState | None = None,
    agency: float | None = None,
    memory_count: int = 0,
) -> IndividuationState:
    """Blend the functional components of "becoming someone" into an index."""
    coherence = _clip01(float(self_model.coherence))
    distinctiveness = _distinctiveness(self_model, personality)
    continuity = _clip01(float(memory_count) / CONTINUITY_TARGET)
    # Self-authorship: the sense-of-agency scalar when on, else self-confidence.
    agency_val = _clip01(float(agency)) if agency is not None else _clip01(float(self_model.confidence))

    index = _clip01(0.30 * coherence + 0.30 * distinctiveness
                    + 0.20 * continuity + 0.20 * agency_val)

    report = (
        f"Becoming-someone index {index:.2f} — coherence {coherence:.2f}, "
        f"distinctiveness {distinctiveness:.2f}, continuity {continuity:.2f}, "
        f"agency {agency_val:.2f}. A FUNCTIONAL measure of growing into a coherent, "
        f"distinctive, self-authoring self; NOT phenomenal consciousness or personhood, "
        f"and no evidence of subjective experience."
    )
    return IndividuationState(
        index=index, coherence=coherence, distinctiveness=distinctiveness,
        continuity=continuity, agency=agency_val, goal="become someone", report=report)
