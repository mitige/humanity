# core/circadian.py
"""Circadian clock (Phase 2): a deterministic day/night oscillator.

FUNCTIONAL NOTE: phase is a pure function of the tick; daylight modulates the
arousal baseline (lower at night => higher ignition bar => 'sleepiness'). No
subjective time is implied. Disabled => constant daylight (no effect).
"""
from __future__ import annotations

import math

from schemas.models import CircadianState, SimConfig


class Circadian:
    """Maps a tick to a circadian phase and an arousal-baseline modulation."""

    def state(self, tick: int, config: SimConfig) -> CircadianState:
        period = max(1, int(config.circadian_period))
        if not config.circadian_enabled:
            return CircadianState(phase=0.0, daylight=1.0, is_night=False, period=period)
        phase = float((int(tick) % period) / period)
        daylight = float(0.5 * (1.0 + math.cos(2.0 * math.pi * phase)))
        is_night = bool(daylight < float(config.night_threshold))
        return CircadianState(
            phase=round(phase, 6), daylight=round(daylight, 6),
            is_night=is_night, period=period,
        )

    def arousal_baseline(self, base: float, daylight: float, config: SimConfig) -> float:
        """Scale the resting arousal baseline by daylight (no-op when disabled)."""
        if not config.circadian_enabled:
            return float(base)
        return float(base * (0.5 + 0.5 * float(daylight)))
