# core/personality.py
"""Emergent personality (Phase 3): a stable profile that diverges with experience.

FUNCTIONAL NOTE: three bounded traits drift (EMA) with what the agent lives —
novelty_seeking toward experienced novelty, caution toward experienced danger,
openness derived from their balance. A label names the dominant trait, and a
bounded affect bias is applied so agents with different histories behave
differently. Aggregate bookkeeping over the agent's own variables; no character
or subjectivity is implied.
"""
from __future__ import annotations


def _clip01(v: float) -> float:
    return float(min(1.0, max(0.0, v)))


class PersonalityModel:
    """Per-agent emergent personality profile + affect modulation."""

    def __init__(self) -> None:
        self.novelty_seeking: float = 0.5
        self.caution: float = 0.5
        self.openness: float = 0.5

    def update(self, novelty_experienced: float, danger_experienced: float, drift: float):
        from schemas.models import PersonalityState
        a = _clip01(float(drift))
        self.novelty_seeking = _clip01((1.0 - a) * self.novelty_seeking + a * _clip01(novelty_experienced))
        self.caution = _clip01((1.0 - a) * self.caution + a * _clip01(danger_experienced))
        self.openness = _clip01(0.5 + 0.5 * (self.novelty_seeking - self.caution))
        return PersonalityState(
            label=self._label(), openness=round(self.openness, 4),
            caution=round(self.caution, 4), novelty_seeking=round(self.novelty_seeking, 4),
            vector=[round(self.openness, 4), round(self.caution, 4), round(self.novelty_seeking, 4)],
        )

    def _label(self) -> str:
        if self.caution > 0.6 and self.novelty_seeking > 0.6:
            return "prudent curieux"
        if self.caution > 0.6:
            return "prudent"
        if self.novelty_seeking > 0.6 or self.openness > 0.6:
            return "explorateur audacieux"
        return "équilibré"

    def modulate(self, emotion):
        """Apply a small, bounded personality bias to baseline affect."""
        return emotion.model_copy(update={
            "curiosity": _clip01(emotion.curiosity + 0.2 * (self.openness - 0.5)),
            "fear": _clip01(emotion.fear + 0.2 * (self.caution - 0.5)),
        })
