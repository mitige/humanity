# core/sleep.py
"""Sleep cycle (Phase 2): sleep/wake gating, offline consolidation, dreaming.

FUNCTIONAL NOTE: sleep is a functional state in which the agent rests (REST),
consolidates episodic memory (reinforce the important, forget the trivial), and
'dreams' by recombining stored summaries. None of this implies subjective sleep
or dreaming. Disabled => the agent never sleeps. Wake is guaranteed: REST
recovers energy, so fatigue (1 - energy/initial) falls below the wake threshold;
``max_sleep_ticks`` is a hard backstop.
"""
from __future__ import annotations

from core.autobiographical_memory import AutobiographicalMemory
from schemas.models import SimConfig


class SleepCycle:
    """Per-agent sleep/wake state machine + consolidation/dream orchestration."""

    def __init__(self) -> None:
        self.is_sleeping: bool = False
        self.sleep_ticks: int = 0

    def evaluate(self, fatigue: float, is_night: bool, config: SimConfig) -> bool:
        """Update and return the sleeping flag from fatigue + circadian night."""
        if not config.sleep_enabled:
            self.is_sleeping = False
            self.sleep_ticks = 0
            return False
        f = float(fatigue)
        if self.is_sleeping:
            self.sleep_ticks += 1
            rested = f <= float(config.wake_fatigue_threshold)
            too_long = self.sleep_ticks >= int(config.max_sleep_ticks)
            if (rested and not is_night) or too_long:
                self.is_sleeping = False
                self.sleep_ticks = 0
        else:
            sleepy = f >= float(config.sleep_fatigue_threshold)
            if sleepy and (is_night or f >= 0.95):
                self.is_sleeping = True
                self.sleep_ticks = 0
        return self.is_sleeping

    def consolidate(self, memory: AutobiographicalMemory, config: SimConfig) -> tuple[int, int]:
        """Run one consolidation pass on the agent's episodic memory."""
        return memory.consolidate(
            k=int(config.memory_retrieval_k),
            boost=float(config.replay_boost),
            prune_threshold=float(config.consolidation_prune_threshold),
        )

    def dream(self, memory: AutobiographicalMemory, config: SimConfig) -> str | None:
        """Recombine the two most recent records into a grounded dream string."""
        if not config.dream_enabled:
            return None
        recent = memory.recent(4)
        if len(recent) < 2:
            return None
        a, b = recent[-1], recent[-2]
        sa = a.summary or a.action.value
        sb = b.summary or b.action.value
        return f"dream: {sa} + {sb}"
