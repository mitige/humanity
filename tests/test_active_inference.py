"""Tests for the active-inference upgrade of the world model and policy.

These exercise ``core.world_model.WorldModel.predict`` (expected free energy and
``value == -expected_free_energy``; lower EFE => higher value) and
``core.policy.Policy.choose_action`` (still returns a valid action with a
non-empty ``candidate_scores`` map).
"""
from __future__ import annotations

import pytest

from core.policy import Policy
from core.world_model import WorldModel
from schemas.models import (
    ActionType,
    EmotionState,
    Observation,
    SelfModelState,
    SimConfig,
)


def _cfg() -> SimConfig:
    """Deterministic config for the active-inference tests."""
    return SimConfig(random_seed=42, world_noise=0.0)


def _empty_observation() -> Observation:
    """An observation with no visible objects (target-free actions only)."""
    return Observation(
        tick=0, agent_x=0, agent_y=0, agent_energy=100.0, radius=3, visible=[]
    )


def _self_model() -> SelfModelState:
    """A neutral self-model snapshot."""
    labels = [a.value for a in ActionType]
    return SelfModelState(
        identity="Aurora-fn-01",
        age_ticks=0,
        energy=100.0,
        confidence=0.5,
        mood=0.0,
        preferences={label: 0.5 for label in labels},
        active_goals=[],
        capability_beliefs={label: 0.5 for label in labels},
        coherence=1.0,
        narrative="n",
    )


def test_predict_sets_efe_and_value_is_negative_efe() -> None:
    """predict() sets expected_free_energy and value == -expected_free_energy."""
    cfg = _cfg()
    wm = WorldModel(cfg)
    obs = _empty_observation()
    for action in ActionType:
        pred = wm.predict(obs, action, None)
        # The active-inference decomposition is the precision-weighted sum of the
        # pragmatic and epistemic values (rounded, hence approx).
        assert pred.expected_free_energy == pytest.approx(
            -(
                cfg.pragmatic_weight * pred.pragmatic_value
                + cfg.epistemic_weight * pred.epistemic_value
            ),
            abs=1e-3,
        )
        # The policy-facing scalar value is exactly the negative EFE.
        assert pred.value == pytest.approx(-pred.expected_free_energy, abs=1e-9)


def test_lower_expected_free_energy_yields_higher_value() -> None:
    """The action with lower EFE has the higher (more desirable) value."""
    cfg = _cfg()
    wm = WorldModel(cfg)
    obs = _empty_observation()

    rest = wm.predict(obs, ActionType.REST, None)
    verbalize = wm.predict(obs, ActionType.VERBALIZE, None)

    # REST is the most desirable target-free action (lowest EFE) in the priors.
    assert rest.expected_free_energy < verbalize.expected_free_energy
    assert rest.value > verbalize.value


def test_value_monotonic_in_negative_efe_across_actions() -> None:
    """Sorting predictions by value matches sorting by -EFE (argmax stays valid)."""
    cfg = _cfg()
    wm = WorldModel(cfg)
    obs = _empty_observation()
    preds = [wm.predict(obs, a, None) for a in ActionType]

    by_value = sorted(preds, key=lambda p: p.value, reverse=True)
    by_neg_efe = sorted(preds, key=lambda p: -p.expected_free_energy, reverse=True)
    assert [p.action for p in by_value] == [p.action for p in by_neg_efe]


def test_choose_action_returns_valid_action_with_scores() -> None:
    """choose_action returns a valid ActionType and a non-empty score map."""
    cfg = _cfg()
    wm = WorldModel(cfg)
    pol = Policy()
    obs = _empty_observation()

    candidates = [
        (ActionType.OBSERVE, None),
        (ActionType.REST, None),
        (ActionType.EXPLORE, None),
        (ActionType.ANALYZE, None),
        (ActionType.VERBALIZE, None),
    ]
    preds = wm.predict_all(obs, candidates)
    decision = pol.choose_action(
        preds, [], _self_model(), [], EmotionState(), [], cfg
    )

    assert isinstance(decision.action, ActionType)
    assert decision.candidate_scores
    assert 0.0 <= decision.confidence <= 1.0
    # The rationale references active-inference free-energy minimization.
    assert "free energy" in decision.rationale.lower()


def test_choose_action_with_no_candidates_still_valid() -> None:
    """With no predictions, choose_action defaults to a valid OBSERVE action."""
    pol = Policy()
    decision = pol.choose_action(
        [], [], _self_model(), [], EmotionState(), [], _cfg()
    )
    assert isinstance(decision.action, ActionType)
    assert decision.action == ActionType.OBSERVE
