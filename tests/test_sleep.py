from core.sleep import SleepCycle
from core.autobiographical_memory import AutobiographicalMemory
from schemas.models import (ActionType, EmotionState, MemoryRecord, SimConfig)


def _mem(cfg):
    m = AutobiographicalMemory(cfg, store=None)
    for i in range(5):
        m.store_experience(MemoryRecord(
            id=0, tick=i, perception=[], action=ActionType.OBSERVE, target_id=None,
            result_energy_delta=0.0, prediction_error=0.0, emotion=EmotionState(),
            importance=0.3 + 0.1 * i, summary=f"e{i}"))
    return m


def test_falls_asleep_when_tired_at_night_and_wakes_rested():
    cfg = SimConfig(sleep_enabled=True, sleep_fatigue_threshold=0.8, wake_fatigue_threshold=0.35)
    s = SleepCycle()
    assert s.evaluate(fatigue=0.9, is_night=True, config=cfg) is True
    assert s.is_sleeping is True
    assert s.evaluate(fatigue=0.2, is_night=False, config=cfg) is False


def test_disabled_never_sleeps():
    s = SleepCycle()
    assert s.evaluate(fatigue=0.99, is_night=True, config=SimConfig(sleep_enabled=False)) is False


def test_consolidation_boosts_top_k_and_prunes_below_threshold():
    cfg = SimConfig(memory_retrieval_k=2, replay_boost=1.5, consolidation_prune_threshold=0.45)
    m = _mem(cfg)
    boosted, pruned = m.consolidate(k=cfg.memory_retrieval_k, boost=cfg.replay_boost,
                                    prune_threshold=cfg.consolidation_prune_threshold)
    assert boosted >= 1 and pruned >= 1


def test_dream_recombines_two_memories():
    s = SleepCycle()
    m = _mem(SimConfig())
    d = s.dream(m, SimConfig(dream_enabled=True))
    assert d is not None and d.startswith("dream:") and "+" in d
