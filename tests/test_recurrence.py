import math

from core.recurrence import RecurrentPerception
from schemas.models import Percept, SimConfig, WorkingMemoryItem


def _percept(oid=1, danger=0.8, novelty=0.5, utility=0.3):
    return Percept(object_id=oid, kind="hazard", dx=1, dy=0, distance=1.0,
                   danger=danger, novelty=novelty, utility=utility, energy_value=0.0)


def _wm_item(percept, tick=1):
    return WorkingMemoryItem(percept=percept, saliency=0.7,
                             created_tick=tick, last_seen_tick=tick)


def test_refine_moves_readings_toward_prior_and_converges():
    cfg = SimConfig(recurrence_enabled=True, recurrence_passes=4, recurrence_gain=0.5)
    noisy = _percept(danger=0.9)
    prior = _percept(danger=0.5)
    refined, state = RecurrentPerception().refine([noisy], [_wm_item(prior)], cfg)
    assert 0.5 < refined[0].danger < 0.9         # pulled toward the prior
    assert state.n_refined == 1 and state.passes == 4
    assert state.mean_delta >= 0.0 and state.report


def test_refine_denoises_toward_truth():
    # Truth 0.5; a noisy reading 0.85 and a WM prior from an earlier (also noisy
    # but closer) sighting 0.55: the refined reading must beat the raw one.
    cfg = SimConfig(recurrence_enabled=True, recurrence_passes=3, recurrence_gain=0.5)
    truth = 0.5
    noisy = _percept(danger=0.85)
    prior = _percept(danger=0.55)
    refined, _ = RecurrentPerception().refine([noisy], [_wm_item(prior)], cfg)
    assert abs(refined[0].danger - truth) < abs(noisy.danger - truth)


def test_refine_without_prior_is_identity():
    cfg = SimConfig(recurrence_enabled=True)
    p = _percept(oid=7)
    refined, state = RecurrentPerception().refine([p], [], cfg)
    assert refined[0] == p
    assert state.n_refined == 0 and state.stabilized


def test_refine_is_pure():
    cfg = SimConfig(recurrence_enabled=True)
    noisy = _percept(danger=0.9)
    RecurrentPerception().refine([noisy], [_wm_item(_percept(danger=0.1))], cfg)
    assert noisy.danger == 0.9                   # input not mutated


def test_damped_passes_converge_monotonically():
    cfg = SimConfig(recurrence_enabled=True, recurrence_passes=8, recurrence_gain=1.0)
    refined, state = RecurrentPerception().refine(
        [_percept(danger=1.0)], [_wm_item(_percept(danger=0.0))], cfg)
    # With gain 1 the first pass jumps to the prior; later damped passes stay put.
    assert math.isclose(refined[0].danger, 0.0, abs_tol=1e-6)
    assert state.stabilized


def test_agent_trace_gating():
    from core.agent import CognitiveAgent
    # Seed 42 keeps objects inside the perception radius, so working memory
    # holds priors for currently visible percepts.
    base = dict(world_noise=0.1, random_seed=42, persist_memory=False, trace_logging=False)
    off = CognitiveAgent(SimConfig(**base))
    for _ in range(6):
        assert off.cognitive_cycle().recurrence is None
    on = CognitiveAgent(SimConfig(**base, recurrence_enabled=True))
    states = [on.cognitive_cycle().recurrence for _ in range(10)]
    assert all(s is not None for s in states)
    assert any(s.n_refined > 0 for s in states)   # WM priors kick in after tick 1
