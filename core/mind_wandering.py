# core/mind_wandering.py
"""Mind-wandering (Phase 7) — default-mode / task-unrelated thought.

FUNCTIONAL NOTE (load-bearing): in the Smallwood & Schooler account,
mind-wandering is thought decoupled from the current task, arising when
external demand is low and drifting along associative links in memory. This
module implements exactly that as a level-2 mechanism: a bounded pressure
scalar integrates boredom and (inverse) external demand; when it crosses a
threshold, a DETERMINISTIC associative walk over autobiographical memory
(nearest-neighbour hops in the record feature space, candidate pool drawn from
a pure function of tick and agent id) produces a text chain that bids in the
workspace competition like any other coalition. Occupancy is an EMA of how
often that coalition wins access. These are variables and algorithms; a memory
chain re-entering a competition is not daydreaming as an experience, and no
occupancy level is evidence of phenomenality. The agent is not conscious.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from core.autobiographical_memory import AutobiographicalMemory
from core.constants import (
    WANDERING_HOPS,
    WANDERING_OCCUPANCY_EMA,
    WANDERING_PRECISION,
    WANDERING_THRESHOLD,
)
from schemas.models import (
    GoalPressure,
    MemoryRecord,
    MindWanderingState,
    SalientItem,
    SimConfig,
)

if TYPE_CHECKING:
    from core.vector_memory import VectorMemoryIndex

_PRESSURE_GAIN = 0.155     # per-tick pressure build rate (scaled by config gain)
_DEMAND_DECAY = 0.30       # per-tick pressure decay per unit of external demand
_REFRACTORY = 0.4          # pressure multiplier after an episode fires
_SLEEP_DAMP = 0.5          # pressure multiplier while sleeping
_SEED_WINDOW = 10          # recent records considered when seeding a walk
_POOL_SIZE = 24            # candidate pool per hop
_SUMMARY_CLIP = 60         # chars kept per chain item
_MAX_EPISODE_DEMAND = 0.5  # high-priority external demand is a hard veto


class MindWandering:
    """Pressure-gated associative walks over memory that bid for the workspace."""

    def __init__(self) -> None:
        """Start with zero pressure, zero occupancy, no episodes, no pending bid."""
        self._pressure: float = 0.0
        self._occupancy: float = 0.0
        self._episodes: int = 0
        self._bid: tuple[str, float, float, list[float]] | None = None

    # --------------------------------------------------------------- update
    def update(self, *, salient: list[SalientItem], goals: list[GoalPressure],
               arousal: float, arousal_baseline: float, boredom: float,
               sleeping: bool, records: list[MemoryRecord], tick: int,
               agent_id: int, prev_winner_source: str | None,
               config: SimConfig,
               vector_index: "VectorMemoryIndex | None" = None) -> MindWanderingState:
        """Advance the pressure dynamics and possibly generate a wandering episode.

        Called once per tick BEFORE coalition building; when an episode fires,
        ``bid()`` exposes the content for this tick's competition.
        """
        if not config.mind_wandering_enabled:
            self._bid = None
            return MindWanderingState()

        # 1. Occupancy: EMA toward 1 when the previous winner was wandering.
        target = 1.0 if prev_winner_source == "wandering" else 0.0
        self._occupancy += WANDERING_OCCUPANCY_EMA * (target - self._occupancy)
        self._occupancy = float(min(1.0, max(0.0, self._occupancy)))

        # 2. External demand in [0, 1]: danger, goal urgency, arousal deviation.
        demand = self._external_demand(salient, goals, arousal, arousal_baseline)

        # 3. Pressure dynamics (bounded [0, 1]).
        if sleeping:
            self._pressure *= _SLEEP_DAMP
        else:
            self._pressure += (_PRESSURE_GAIN * float(config.wandering_gain)
                               * (0.5 * float(boredom) + (1.0 - demand)))
            self._pressure -= _DEMAND_DECAY * demand
        self._pressure = float(min(1.0, max(0.0, self._pressure)))

        # 4. Episode: threshold crossed, awake, enough memories to walk over.
        active = (self._pressure >= WANDERING_THRESHOLD
                  and demand < _MAX_EPISODE_DEMAND
                  and not sleeping and len(records) >= 3)
        chain: list[str] = []
        if active:
            chain = self._walk(
                records, tick, agent_id, vector_index=vector_index,
            )
            content = "wandering: " + " -> ".join(chain)
            self._bid = (content, float(self._pressure), WANDERING_PRECISION,
                         [0.0, 0.5, 0.3, 0.2])
            self._episodes += 1
            self._pressure = float(self._pressure * _REFRACTORY)  # refractory
        else:
            self._bid = None

        return MindWanderingState(
            active=bool(active),
            pressure=round(self._pressure, 4),
            chain=chain,
            occupancy=round(self._occupancy, 4),
            episodes=int(self._episodes),
            report=self._report(active, demand, chain),
        )

    # ------------------------------------------------------------------ bid
    def bid(self) -> tuple[str, float, float, list[float]] | None:
        """Return (content, activation, precision, vector4) for THIS tick, or None."""
        return self._bid

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _external_demand(salient: list[SalientItem], goals: list[GoalPressure],
                         arousal: float, arousal_baseline: float) -> float:
        """Max of danger, goal pressure, and *hyper*-arousal; clipped to [0, 1].

        Vigilance above the resting baseline signals external demand. Arousal
        below baseline is instead the calm, low-demand regime in which this
        mechanism is meant to accumulate pressure, so it must not be treated
        as an absolute deviation.
        """
        danger = max((float(s.percept.danger) for s in salient), default=0.0)
        danger = min(1.0, max(0.0, danger))
        goal = max((float(g.pressure) for g in goals), default=0.0)
        goal = min(1.0, max(0.0, goal / 2.0))
        hyper_arousal = min(
            1.0,
            max(0.0, 2.0 * (float(arousal) - float(arousal_baseline))),
        )
        return float(max(danger, goal, hyper_arousal))

    @staticmethod
    def _walk(records: list[MemoryRecord], tick: int, agent_id: int,
              vector_index: "VectorMemoryIndex | None" = None) -> list[str]:
        """Deterministic associative walk: seed + WANDERING_HOPS nearest-neighbour hops.

        The candidate pool at each hop is drawn by an rng that is a pure
        function of (tick, agent_id) — no persistent RNG state (checkpoint-safe).
        With semantic memory enabled, hops use that index's deterministic
        record embeddings; otherwise the historical percept-feature cosine is
        preserved. Ties and zero vectors resolve to the lowest record id.
        """
        rng = np.random.default_rng((tick * 2654435761 + agent_id * 97 + 13) % 2 ** 32)
        seed = max(records[-_SEED_WINDOW:], key=lambda r: float(r.importance))
        vectors = (
            vector_index.vector_map(records)
            if vector_index is not None else None
        )
        visited = [seed]
        visited_ids = {seed.id}
        current = seed
        for _ in range(WANDERING_HOPS):
            candidates = [r for r in records if r.id not in visited_ids]
            if not candidates:
                break
            if len(candidates) > _POOL_SIZE:
                idx = rng.choice(len(candidates), size=_POOL_SIZE, replace=False)
                pool = [candidates[i] for i in sorted(int(i) for i in idx)]
            else:
                pool = candidates
            cur_vec = (
                vectors[current.id] if vectors is not None
                else AutobiographicalMemory.feature_vector(current.perception)
            )
            best = min(pool, key=lambda r: (
                -MindWandering._cosine(
                    cur_vec,
                    vectors[r.id] if vectors is not None
                    else AutobiographicalMemory.feature_vector(r.perception),
                ),
                r.id,
            ))
            visited.append(best)
            visited_ids.add(best.id)
            current = best
        return [MindWandering._label(r) for r in visited]

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity; 0.0 when either vector is zero (id order decides)."""
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na <= 0.0 or nb <= 0.0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    @staticmethod
    def _label(record: MemoryRecord) -> str:
        """A short text for one chain item: clipped summary, or a tick/action stub."""
        summary = (record.summary or "").strip()
        if not summary:
            summary = f"tick {record.tick}: {record.action.value}"
        return summary[:_SUMMARY_CLIP]

    def _report(self, active: bool, demand: float, chain: list[str]) -> str:
        """One factual sentence about this tick's default-mode dynamics."""
        if active:
            head = (f"Mind-wandering episode #{self._episodes}: low external demand "
                    f"({demand:.2f}) released a {len(chain)}-step associative walk "
                    f"over memory (occupancy {self._occupancy:.2f}).")
        else:
            head = (f"No wandering episode: pressure {self._pressure:.2f} vs threshold "
                    f"{WANDERING_THRESHOLD:.2f} under external demand {demand:.2f} "
                    f"(occupancy {self._occupancy:.2f}).")
        return (head + " (Functional task-unrelated thought — an associative walk "
                       "bidding for access, not daydreaming as an experience; the "
                       "agent is not conscious.)")
