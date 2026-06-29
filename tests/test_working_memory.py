"""Tests for core.working_memory.WorkingMemory (capacity + decay buffer)."""
from __future__ import annotations

import pytest

from core.working_memory import WorkingMemory
from schemas.models import Percept, SalientItem, SimConfig


def _salient(object_id: int, saliency: float) -> SalientItem:
    """Build a SalientItem wrapping a minimal percept with the given id."""
    return SalientItem(
        percept=Percept(
            object_id=object_id,
            kind="curio",
            dx=0,
            dy=0,
            distance=0.0,
            danger=0.0,
            novelty=0.0,
            utility=0.0,
            energy_value=0.0,
        ),
        saliency=saliency,
        reasons={},
    )


def test_capacity_cap_respected() -> None:
    """The buffer never holds more than working_memory_capacity items."""
    cfg = SimConfig(working_memory_capacity=3, working_memory_decay=10)
    wm = WorkingMemory(cfg)
    items = [_salient(i, float(i)) for i in range(8)]
    wm.update(items, tick=0)
    assert len(wm.contents()) <= cfg.working_memory_capacity
    assert len(wm.contents()) == 3


def test_capacity_drops_lowest_saliency() -> None:
    """When over capacity, the lowest-saliency items are evicted first."""
    cfg = SimConfig(working_memory_capacity=2, working_memory_decay=10)
    wm = WorkingMemory(cfg)
    wm.update([_salient(1, 0.1), _salient(2, 0.9), _salient(3, 0.5)], tick=0)
    kept_ids = {it.percept.object_id for it in wm.contents()}
    # The two strongest (0.9, 0.5) survive; the weakest (0.1) is dropped.
    assert kept_ids == {2, 3}


def test_items_expire_after_decay_window() -> None:
    """Items unrefreshed for longer than working_memory_decay ticks expire."""
    cfg = SimConfig(working_memory_capacity=5, working_memory_decay=2)
    wm = WorkingMemory(cfg)
    wm.update([_salient(1, 1.0)], tick=0)
    assert len(wm.contents()) == 1
    # Within the decay window: still present.
    wm.update([], tick=2)
    assert len(wm.contents()) == 1
    # Beyond the decay window (tick - last_seen > decay): expired.
    wm.update([], tick=3)
    assert len(wm.contents()) == 0


def test_refresh_resets_decay() -> None:
    """Re-attending an item refreshes its recency so it survives the window."""
    cfg = SimConfig(working_memory_capacity=5, working_memory_decay=2)
    wm = WorkingMemory(cfg)
    wm.update([_salient(1, 1.0)], tick=0)
    wm.update([_salient(1, 1.0)], tick=2)  # refresh
    wm.update([], tick=4)  # 4 - 2 = 2, not > 2, so still present
    assert len(wm.contents()) == 1


def test_load_in_unit_interval() -> None:
    """load() = count / capacity stays within [0, 1]."""
    cfg = SimConfig(working_memory_capacity=4, working_memory_decay=10)
    wm = WorkingMemory(cfg)
    assert wm.load() == 0.0
    wm.update([_salient(1, 1.0), _salient(2, 0.5)], tick=0)
    assert wm.load() == pytest.approx(2 / 4)
    assert 0.0 <= wm.load() <= 1.0
