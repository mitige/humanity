"""Fast/headless training mode + memory feature-vector cache (performance)."""
from core.agent import CognitiveAgent
from core.autobiographical_memory import AutobiographicalMemory
from schemas.models import (ActionType, EmotionState, MemoryRecord, Percept, SimConfig)


def _percepts(danger: float) -> list[Percept]:
    return [Percept(object_id=1, kind="x", dx=0, dy=0, distance=1.0, danger=danger,
                    novelty=0.5, utility=0.5, energy_value=1.0)]


def test_persist_memory_false_uses_no_store():
    a = CognitiveAgent(SimConfig(persist_memory=False, world_noise=0.0))
    assert a.memory_store is None and a.memory._store is None
    a.cognitive_cycle()  # runs fine, memory stays in RAM


def test_persist_memory_true_is_the_default():
    a = CognitiveAgent(SimConfig(world_noise=0.0))
    assert a.memory_store is not None


def test_trace_logging_false_skips_the_write():
    a = CognitiveAgent(SimConfig(trace_logging=False, world_noise=0.0))
    logged = []
    a.trace_logger.log = lambda tr: logged.append(tr)
    a.cognitive_cycle()
    assert logged == []


def test_trace_logging_true_logs_by_default():
    a = CognitiveAgent(SimConfig(world_noise=0.0))
    logged = []
    a.trace_logger.log = lambda tr: logged.append(tr)
    a.cognitive_cycle()
    assert len(logged) == 1


def test_feature_vector_cache_aligned_and_retrieval_works():
    m = AutobiographicalMemory(SimConfig(), store=None)
    for i in range(5):
        m.store_experience(MemoryRecord(
            id=0, tick=i, perception=_percepts(0.2 * i), action=ActionType.OBSERVE,
            target_id=None, result_energy_delta=0.0, prediction_error=0.0,
            emotion=EmotionState(), importance=0.3 + 0.1 * i, summary=f"e{i}"))
    assert len(m._records) == len(m._vectors) == 5
    # Pruning consolidation keeps the cache in lock-step with the records.
    m.consolidate(k=2, boost=1.5, prune_threshold=0.45)
    assert len(m._records) == len(m._vectors)
    assert m.retrieve_similar(_percepts(0.8), 3)  # still returns matches


def test_society_train_advances_ticks():
    from core.society import SocietyManager
    soc = SocietyManager(SimConfig(n_agents=2, world_noise=0.0,
                                   persist_memory=False, trace_logging=False))
    out = soc.train(10)
    assert out["ticks_run"] == 10 and soc.world.tick == 10 and out["n_agents"] == 2


def test_train_endpoint_runs_fast_ticks():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    client.post("/society/config", json={"n_agents": 1, "world_noise": 0.0,
                                         "persist_memory": False, "trace_logging": False})
    r = client.post("/train", json={"ticks": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["ticks_run"] == 5 and "disclaimer" in body
