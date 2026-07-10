# tests/test_td_learning.py
"""Unit tests for core/td_learning.py — contextual SARSA(λ) with traces."""
from __future__ import annotations

import pytest

from core.td_learning import TDLearner
from core.agent import CognitiveAgent
from schemas.models import SimConfig


def _cfg(**overrides) -> SimConfig:
    """A deterministic config with TD learning parameters set explicitly."""
    params = dict(td_learning_enabled=True, td_lambda=0.8, td_discount=0.9,
                  value_learning_rate=0.2, world_noise=0.0, random_seed=42)
    params.update(overrides)
    return SimConfig(**params)


CTX_A = TDLearner.context_key(False, False, False, False)
CTX_B = TDLearner.context_key(True, False, False, False)


def test_first_call_returns_zero_and_no_table_entry() -> None:
    learner = TDLearner()
    cfg = _cfg()
    assert learner.step(CTX_A, "eat", 5.0, cfg) == 0.0
    assert learner.last_td_error == 0.0
    assert learner.values_for(CTX_A) == {}
    assert learner.n_contexts() == 0
    assert learner.last_context == CTX_A
    assert learner.last_reward == 5.0


def test_td_only_trace_reports_its_actual_reward() -> None:
    """TD learning must not expose the disabled legacy learner's stale zero."""
    agent = CognitiveAgent(_cfg(
        learning_enabled=False,
        meta_learning_enabled=False,
        n_objects=0,
        persist_memory=False,
        trace_logging=False,
    ))

    trace = agent.cognitive_cycle()

    assert trace.learning is not None
    assert trace.learning.last_reward == pytest.approx(
        agent.td_learner.last_reward)
    assert trace.learning.last_reward != agent.policy_learner.last_reward


def test_repeated_positive_reward_drives_q_up() -> None:
    learner = TDLearner()
    cfg = _cfg()
    for _ in range(10):
        learner.step(CTX_A, "eat", 8.0, cfg)
    assert learner.values_for(CTX_A)["eat"] > 0.3


def test_repeated_negative_reward_drives_q_down() -> None:
    learner = TDLearner()
    cfg = _cfg()
    for _ in range(10):
        learner.step(CTX_A, "touch_danger", -8.0, cfg)
    assert learner.values_for(CTX_A)["touch_danger"] < -0.3


def test_eligibility_traces_credit_earlier_action() -> None:
    """A reward landing two steps after 'move' still credits 'move' via traces."""
    learner = TDLearner()
    cfg = _cfg()
    learner.step(CTX_A, "move", 0.0, cfg)     # earlier action, no reward
    learner.step(CTX_A, "rest", 0.0, cfg)
    learner.step(CTX_A, "eat", 10.0, cfg)     # reward earned here...
    learner.step(CTX_A, "idle", 0.0, cfg)     # ...processed on the next tick
    assert learner.values_for(CTX_A)["move"] > 0.0
    assert learner.values_for(CTX_A)["eat"] > learner.values_for(CTX_A)["move"]


def test_lambda_zero_gives_no_multi_step_credit() -> None:
    """With λ=0 the same sequence leaves the earlier action's Q untouched."""
    learner = TDLearner()
    cfg = _cfg(td_lambda=0.0)
    learner.step(CTX_A, "move", 0.0, cfg)
    learner.step(CTX_A, "rest", 0.0, cfg)
    learner.step(CTX_A, "eat", 10.0, cfg)
    learner.step(CTX_A, "idle", 0.0, cfg)
    assert learner.values_for(CTX_A).get("move", 0.0) == 0.0
    assert learner.values_for(CTX_A)["eat"] > 0.0


def test_context_separation_same_action_opposite_values() -> None:
    learner = TDLearner()
    cfg = _cfg()
    for _ in range(10):
        learner.step(CTX_A, "approach", 8.0, cfg)
    for _ in range(10):
        learner.step(CTX_B, "approach", -8.0, cfg)
    learner.step(CTX_B, "idle", 0.0, cfg)  # flush the last pending transition
    assert learner.values_for(CTX_A)["approach"] > 0.0
    assert learner.values_for(CTX_B)["approach"] < 0.0


def test_determinism_identical_runs() -> None:
    cfg = _cfg()
    seq = [(CTX_A, "eat", 6.0), (CTX_A, "move", -2.0), (CTX_B, "flee", 4.0),
           (CTX_B, "eat", -7.0), (CTX_A, "rest", 1.0), (CTX_A, "eat", 9.0)]
    l1, l2 = TDLearner(), TDLearner()
    errs1 = [l1.step(c, a, r, cfg) for c, a, r in seq * 5]
    errs2 = [l2.step(c, a, r, cfg) for c, a, r in seq * 5]
    assert errs1 == errs2
    assert l1.q == l2.q
    assert l1.traces == l2.traces
    assert l1.last_context == l2.last_context


def test_hand_computed_updates_pin_the_sarsa_lambda_formula() -> None:
    """Exact-value regression: pins delta = r_p + gamma*Q[succ] - Q[prev] and the
    replacing-trace propagation. Catches formula transpositions (e.g. swapped
    Q[succ]/Q[prev]) that sign-only tests cannot see while Q starts at 0.

    lr=0.2, gamma=0.9, lambda=0.8 => trace decay 0.72 per step.
    """
    learner = TDLearner()
    cfg = _cfg()
    approx = lambda x: pytest.approx(x, rel=1e-9, abs=1e-12)  # noqa: E731

    # t1: pending=(A,eat,r=0.5); no update yet.
    assert learner.step(CTX_A, "eat", 5.0, cfg) == 0.0

    # t2: score (A,eat,0.5) against succ (A,move): delta = 0.5 + 0.9*0 - 0 = 0.5
    #     Q[eat] = 0.2*0.5 = 0.1 ; traces: eat -> 0.72
    assert learner.step(CTX_A, "move", -3.0, cfg) == approx(0.5)
    assert learner.values_for(CTX_A)["eat"] == approx(0.1)

    # t3: score (A,move,-0.3) against succ (A,idle): delta = -0.3 + 0.9*0 - 0
    #     Q[move] = 0.2*(-0.3) = -0.06 ; Q[eat] = 0.1 + 0.2*(-0.3)*0.72 = 0.0568
    assert learner.step(CTX_A, "idle", 0.0, cfg) == approx(-0.3)
    assert learner.values_for(CTX_A)["move"] == approx(-0.06)
    assert learner.values_for(CTX_A)["eat"] == approx(0.0568)

    # t4: score (A,idle,0.0) against succ (A,eat), where Q[eat]=0.0568 now:
    #     delta = 0.0 + 0.9*0.0568 - Q[idle](0) = 0.05112   (a swapped formula
    #     would give -0.0568 here — different sign, so the pin is meaningful)
    #     Q[idle] = 0.2*0.05112 = 0.010224
    #     Q[eat]  = 0.0568 + 0.2*0.05112*0.5184 = 0.0621001216
    #     Q[move] = -0.06 + 0.2*0.05112*0.72   = -0.05263872
    assert learner.step(CTX_A, "eat", 0.0, cfg) == approx(0.05112)
    assert learner.last_td_error == approx(0.05112)
    assert learner.values_for(CTX_A)["idle"] == approx(0.010224)
    assert learner.values_for(CTX_A)["eat"] == approx(0.0621001216)
    assert learner.values_for(CTX_A)["move"] == approx(-0.05263872)


def test_q_bounded_under_extreme_rewards() -> None:
    learner = TDLearner()
    cfg = _cfg(value_learning_rate=1.0)
    for _ in range(50):
        learner.step(CTX_A, "eat", 1e6, cfg)
        learner.step(CTX_A, "touch_danger", -1e6, cfg)
    for value in learner.values_for(CTX_A).values():
        assert -1.0 <= value <= 1.0


def test_context_key_formatting() -> None:
    assert TDLearner.context_key(False, False, False, False) == "d0e0n0s0"
    assert TDLearner.context_key(True, True, True, True) == "d1e1n1s1"
    assert TDLearner.context_key(True, False, True, False) == "d1e0n1s0"
    assert TDLearner.context_key(False, True, False, True) == "d0e1n0s1"


def test_n_contexts_counts_distinct_contexts() -> None:
    learner = TDLearner()
    cfg = _cfg()
    assert learner.n_contexts() == 0
    for _ in range(3):
        learner.step(CTX_A, "eat", 5.0, cfg)
    assert learner.n_contexts() == 1
    for _ in range(3):
        learner.step(CTX_B, "flee", 5.0, cfg)
    assert learner.n_contexts() == 2
    assert learner.values_for("d1e1n1s1") == {}
