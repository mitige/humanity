# tests/test_mind_wandering.py
"""Unit tests for core/mind_wandering.py (Phase 7 — default-mode wandering)."""
from __future__ import annotations

import pytest

from core.agent import CognitiveAgent
from core.constants import WANDERING_PRECISION, WANDERING_THRESHOLD
from core.mind_wandering import MindWandering
from core.vector_memory import VectorMemoryIndex
from schemas.models import (
    ActionType,
    EmotionState,
    GoalPressure,
    MemoryRecord,
    Percept,
    SalientItem,
    SimConfig,
)

CFG = SimConfig(mind_wandering_enabled=True)


def _percept(oid: int, danger: float = 0.0, novelty: float = 0.3,
             utility: float = 0.2, energy: float = 0.1) -> Percept:
    return Percept(object_id=oid, kind="food", dx=1, dy=0, distance=1.0 + oid % 3,
                   danger=danger, novelty=novelty, utility=utility,
                   energy_value=energy)


def _salient(danger: float) -> SalientItem:
    return SalientItem(percept=_percept(99, danger=danger), saliency=0.9,
                       reasons={"danger": danger})


def _record(i: int, importance: float = 0.5, summary: str | None = None) -> MemoryRecord:
    return MemoryRecord(
        id=i, tick=i, perception=[_percept(i, novelty=0.1 * (i % 5), utility=0.05 * i)],
        action=ActionType.EXPLORE, result_energy_delta=0.0, prediction_error=0.1,
        emotion=EmotionState(), importance=importance,
        summary=f"saw object {i} while exploring" if summary is None else summary)


def _records(n: int = 8) -> list[MemoryRecord]:
    recs = [_record(i) for i in range(n)]
    if recs:
        recs[-1] = _record(n - 1, importance=0.9)   # a clear seed among the last 10
    return recs


def _step(mw: MindWandering, tick: int, *, salient=None, goals=None, arousal=0.5,
          baseline=0.5, boredom=0.8, sleeping=False, records=None,
          prev_winner=None, config=CFG):
    return mw.update(salient=salient or [], goals=goals or [], arousal=arousal,
                     arousal_baseline=baseline, boredom=boredom, sleeping=sleeping,
                     records=_records() if records is None else records, tick=tick,
                     agent_id=1, prev_winner_source=prev_winner, config=config)


def test_low_demand_boredom_builds_pressure_and_fires():
    mw = MindWandering()
    fired = None
    prev_pressure = 0.0
    for t in range(1, 30):
        state = _step(mw, t)
        if state.active:
            fired = state
            break
        assert state.pressure >= prev_pressure     # pressure climbs under low demand
        prev_pressure = state.pressure
    assert fired is not None
    assert fired.active and fired.episodes == 1
    assert fired.chain and all(len(item) <= 60 for item in fired.chain)
    bid = mw.bid()
    assert bid is not None
    content, activation, precision, vector = bid
    assert content.startswith("wandering: ") and " -> " in content
    assert activation >= WANDERING_THRESHOLD
    assert precision == WANDERING_PRECISION
    assert vector == [0.0, 0.5, 0.3, 0.2]
    assert "not conscious" in fired.report


def test_high_danger_suppresses_wandering():
    mw = MindWandering()
    for t in range(1, 60):
        state = _step(mw, t, salient=[_salient(1.0)])
        assert not state.active and mw.bid() is None
    assert state.pressure < WANDERING_THRESHOLD


def test_high_goal_pressure_suppresses_wandering():
    mw = MindWandering()
    goals = [GoalPressure(need="reduce_danger", pressure=2.0, description="flee")]
    for t in range(1, 60):
        state = _step(mw, t, goals=goals)
        assert not state.active and mw.bid() is None


@pytest.mark.parametrize("demand", ["danger", "goal"])
def test_high_demand_vetoes_an_already_saturated_pressure(demand: str):
    mw = MindWandering()
    sparse = _records(2)
    for tick in range(1, 30):
        primed = _step(mw, tick, boredom=1.0, records=sparse)
        assert not primed.active
    assert primed.pressure > WANDERING_THRESHOLD

    kwargs = (
        {"salient": [_salient(1.0)]}
        if demand == "danger"
        else {"goals": [GoalPressure(
            need="reduce_danger", pressure=2.0, description="flee")]}
    )
    state = _step(mw, 30, boredom=1.0, records=_records(3), **kwargs)

    assert not state.active
    assert mw.bid() is None


def test_only_hyper_arousal_counts_as_external_demand():
    """Calm below baseline is low demand; only excess vigilance is demand."""
    assert MindWandering._external_demand([], [], 0.20, 0.45) == 0.0
    assert MindWandering._external_demand([], [], 0.70, 0.45) == pytest.approx(0.5)


def test_integrated_agent_wanders_on_an_exact_deterministic_tick_sequence():
    """The default seeded agent must actually reach the integrated mechanism."""
    config = SimConfig(
        persist_memory=False,
        trace_logging=False,
        mind_wandering_enabled=True,
        vector_memory_enabled=True,
        curiosity_enabled=True,
        sleep_enabled=False,
        random_seed=42,
    )

    def run() -> list[tuple[int, int, str]]:
        agent = CognitiveAgent(config)
        episodes: list[tuple[int, int, str]] = []
        for _ in range(300):
            trace = agent.cognitive_cycle()
            if trace.wandering is not None and trace.wandering.active:
                bid = agent.mind_wandering.bid()
                assert bid is not None
                episodes.append((trace.tick, len(agent.memory._records), bid[0][:10]))
        return episodes

    expected = [(23, 19, "wandering:")]
    assert run() == expected
    assert run() == expected


def test_sleeping_suppresses_and_damps_pressure():
    mw = MindWandering()
    for t in range(1, 5):
        awake = _step(mw, t)                        # build some pressure
    assert not awake.active                         # stayed under threshold: p_awake is raw
    p_awake = awake.pressure
    state = _step(mw, 5, sleeping=True)
    assert not state.active and mw.bid() is None
    assert state.pressure < p_awake                 # halved toward 0
    for t in range(6, 40):
        state = _step(mw, t, sleeping=True)
        assert not state.active and mw.bid() is None
    assert state.pressure < 0.01


def test_fewer_than_three_records_never_fires():
    mw = MindWandering()
    for t in range(1, 60):
        state = _step(mw, t, records=[_record(0), _record(1)])
        assert not state.active and mw.bid() is None and state.episodes == 0
    assert state.pressure <= 1.0                    # bounded even without episodes


def test_determinism_identical_sequences():
    def run() -> list[tuple]:
        mw = MindWandering()
        out = []
        for t in range(1, 25):
            state = _step(mw, t, boredom=0.7,
                          prev_winner="wandering" if t % 3 == 0 else None)
            out.append((state.model_dump(), mw.bid()))
        return out
    assert run() == run()


def test_occupancy_ema_rises_and_is_bounded():
    mw = MindWandering()
    prev = 0.0
    for t in range(1, 40):
        state = _step(mw, t, salient=[_salient(1.0)], prev_winner="wandering")
        assert prev <= state.occupancy <= 1.0
        prev = state.occupancy
    assert state.occupancy > 0.9
    state = _step(mw, 40, salient=[_salient(1.0)], prev_winner="perception")
    assert state.occupancy < prev                   # decays when it stops winning


def test_refractory_drops_pressure_after_episode():
    mw = MindWandering()
    for t in range(1, 30):
        state = _step(mw, t)
        if state.active:
            break
    assert state.active
    # State pressure on the firing tick is post-refractory: back under threshold.
    assert state.pressure < WANDERING_THRESHOLD


def test_empty_summary_falls_back_to_tick_action_stub():
    mw = MindWandering()
    records = [_record(i, summary="") for i in range(5)]
    for t in range(1, 30):
        state = _step(mw, t, records=records)
        if state.active:
            break
    assert state.active
    assert all(item.startswith("tick ") for item in state.chain)


def test_walk_seeds_on_recent_importance_and_hops_to_cosine_nearest():
    """The chain must start at the highest-importance record of the LAST 10 and
    follow cosine-nearest hops in feature space — not just be any 3 records."""
    def vec_record(i: int, *, danger: float = 0.0, novelty: float = 0.0,
                   importance: float = 0.1, summary: str = "") -> MemoryRecord:
        p = Percept(object_id=i, kind="food", dx=1, dy=0, distance=1.0,
                    danger=danger, novelty=novelty, utility=0.0, energy_value=0.0)
        return MemoryRecord(id=i, tick=i, perception=[p], action=ActionType.EXPLORE,
                            result_energy_delta=0.0, prediction_error=0.1,
                            emotion=EmotionState(), importance=importance,
                            summary=summary)

    records = (
        # 4 decoys OUTSIDE the last-10 seed window: max importance, but ineligible.
        [vec_record(i, novelty=1.0, importance=0.99, summary="DECOY") for i in range(4)]
        + [vec_record(i, novelty=1.0, summary="FILLER") for i in range(4, 10)]
        + [vec_record(10, novelty=1.0, summary="FAR"),          # cos vs seed ~0.67
           vec_record(11, danger=0.8, summary="NEXT"),          # nearest to NEAR
           vec_record(12, danger=0.9, summary="NEAR"),          # nearest to SEED
           vec_record(13, danger=1.0, importance=0.9, summary="SEED")]
    )
    mw = MindWandering()
    for t in range(1, 30):
        state = _step(mw, t, boredom=1.0, records=records)
        if state.active:
            break
    assert state.active
    # Seed = highest importance among the last 10 (the 0.99 decoys are older).
    # Hop 1: cos(SEED, NEAR) ~0.999 beats every novelty vector (~0.67).
    # Hop 2: cos(NEAR, NEXT) ~0.999 beats the rest.
    assert state.chain == ["SEED", "NEAR", "NEXT"]
    assert mw.bid()[0] == "wandering: SEED -> NEAR -> NEXT"


def test_semantic_index_guides_textually_related_associative_hop():
    """Semantic mode must distinguish memories whose percept features tie."""
    records = [
        _record(1, summary="distant metallic storm"),
        _record(2, summary="ripe red berries by the orchard"),
        _record(3, importance=0.9, summary="red berries beside an orchard tree"),
    ]
    index = VectorMemoryIndex()
    fallback = MindWandering._walk(records, tick=9, agent_id=0)
    semantic = MindWandering._walk(
        records, tick=9, agent_id=0, vector_index=index,
    )

    assert fallback[:2] == [records[2].summary, records[0].summary]
    assert semantic[:2] == [records[2].summary, records[1].summary]


def test_semantic_walk_reuses_synchronized_vector_cache(monkeypatch):
    records = _records(40)
    index = VectorMemoryIndex()
    index.rebuild(records)

    def unexpected_reembedding(record):
        raise AssertionError(f"record {record.id} was re-embedded after sync")

    monkeypatch.setattr(index, "embed_record", unexpected_reembedding)

    chain = MindWandering._walk(
        records, tick=50, agent_id=0, vector_index=index)

    assert len(chain) >= 2


def test_agent_passes_its_semantic_index_to_mind_wandering(monkeypatch):
    config = SimConfig(
        n_objects=3,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
        mind_wandering_enabled=True,
        vector_memory_enabled=True,
    )
    agent = CognitiveAgent(config)
    captured = {}
    original = agent.mind_wandering.update

    def spy(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(agent.mind_wandering, "update", spy)
    agent.cognitive_cycle()

    assert captured["vector_index"] is agent.vector_index


def test_disabled_config_returns_inert_state():
    mw = MindWandering()
    state = _step(mw, 1, config=SimConfig(mind_wandering_enabled=False))
    assert state == type(state)()
    assert mw.bid() is None
