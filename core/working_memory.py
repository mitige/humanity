"""Working memory: a small, capacity-limited, decaying buffer of salient items.

FUNCTIONAL NOTE
---------------
This is a functional model of a working-memory-like buffer. It holds a bounded
set of recently-attended items keyed by object id, refreshes them when they are
re-attended, expires stale entries, and evicts the least salient item when over
capacity. It is a data structure that simulates an observable correlate of
working memory; it does not entail any subjective experience.
"""
from __future__ import annotations

from schemas.models import SalientItem, SimConfig, WorkingMemoryItem


class WorkingMemory:
    """Capacity-limited, time-decaying buffer of salient percepts.

    Items are keyed by ``percept.object_id``. Each update refreshes already-known
    items (bumping ``last_seen_tick`` and ``saliency``), inserts new ones,
    expires items unseen for longer than ``working_memory_decay`` ticks, and
    drops the lowest-saliency items once capacity is exceeded.
    """

    def __init__(self, config: SimConfig) -> None:
        self._config = config
        # Keyed by object_id for O(1) refresh; preserves one entry per object.
        self._items: dict[int, WorkingMemoryItem] = {}

    def update(self, salient: list[SalientItem], tick: int) -> None:
        """Insert/refresh salient items, expire stale ones, enforce capacity.

        Order of operations:
          1. Insert or refresh each incoming salient item (by object_id).
          2. Expire items whose ``last_seen_tick`` is older than the decay window.
          3. If still over capacity, drop the lowest-saliency items.
        """
        # 1) Insert or refresh.
        for item in salient:
            oid = item.percept.object_id
            existing = self._items.get(oid)
            if existing is not None:
                # Refresh: keep original creation tick, update recency + saliency.
                existing.percept = item.percept
                existing.saliency = float(item.saliency)
                existing.last_seen_tick = int(tick)
            else:
                self._items[oid] = WorkingMemoryItem(
                    percept=item.percept,
                    saliency=float(item.saliency),
                    created_tick=int(tick),
                    last_seen_tick=int(tick),
                )

        # 2) Expire items not refreshed within the decay window.
        decay = self._config.working_memory_decay
        expired = [
            oid
            for oid, it in self._items.items()
            if tick - it.last_seen_tick > decay
        ]
        for oid in expired:
            del self._items[oid]

        # 3) Enforce capacity by evicting lowest-saliency items.
        capacity = max(0, self._config.working_memory_capacity)
        if len(self._items) > capacity:
            # Sort by saliency ascending; the weakest items are dropped first.
            ordered = sorted(
                self._items.items(), key=lambda kv: kv[1].saliency
            )
            n_to_drop = len(self._items) - capacity
            for oid, _ in ordered[:n_to_drop]:
                del self._items[oid]

    def contents(self) -> list[WorkingMemoryItem]:
        """Return current items, sorted by saliency descending (strongest first)."""
        return sorted(
            self._items.values(), key=lambda it: it.saliency, reverse=True
        )

    def load(self) -> float:
        """Return buffer load in ``[0, 1]`` = current count / capacity."""
        capacity = self._config.working_memory_capacity
        if capacity <= 0:
            return 0.0
        return float(min(1.0, len(self._items) / capacity))
