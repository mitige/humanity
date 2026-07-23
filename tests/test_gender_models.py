"""Phase 8 public contracts: bounded, open-label and non-diagnostic."""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from schemas.models import (
    BodyDomainPreference,
    ConfigPatch,
    ExpressionChannelProfile,
    GenderAxes,
    GenderEventRequest,
    GenderEventType,
    GenderLifeStage,
    GenderProfile,
    GenderProfileSegment,
    GenderScenario,
    GenderScenarioAgent,
    GenderSelfUnderstanding,
    GenderSocialContext,
    LifeCoursePlan,
    LifeCourseStage,
    SimConfig,
    TransitionDimension,
)


def _understanding() -> GenderSelfUnderstanding:
    return GenderSelfUnderstanding(
        labels=["questioning"],
        questioning=True,
        certainty=0.2,
        fit_by_label={"questioning": 0.5},
        known_vocabulary=["questioning", "woman", "nonbinary"],
    )


def _profile(**updates) -> GenderProfile:
    values = {
        "profile_id": "open-profile",
        "assigned_category": "custom assigned category",
        "felt_affinities": {"woman": 0.8, "nonbinary": 0.6},
        "fluidity": 0.3,
        "gender_salience": 0.8,
        "available_vocabulary": ["questioning", "woman", "nonbinary"],
        "preferred_expression": {
            "presentation": ExpressionChannelProfile(
                desired=GenderAxes(feminine=0.8, androgynous=0.5)
            )
        },
        "body_preferences": {
            "voice": BodyDomainPreference(
                preferred=GenderAxes(feminine=0.8),
                salience=0.9,
                dysphoria_sensitivity=0.0,
                euphoria_sensitivity=0.8,
            )
        },
        "transition_priorities": {
            TransitionDimension.SOCIAL: 0.9,
            TransitionDimension.VOICE: 0.7,
        },
        "initial_self_understanding": _understanding(),
    }
    values.update(updates)
    return GenderProfile(**values)


def _life_course() -> LifeCoursePlan:
    return LifeCoursePlan(
        stages=[
            LifeCourseStage(
                stage=GenderLifeStage.ADULTHOOD,
                duration_ticks=100,
                autonomy=1.0,
                resource_access=0.7,
                norm_exposure=0.5,
            )
        ]
    )


def test_phase8_config_defaults_off_and_patch_fields_exist() -> None:
    cfg = SimConfig()
    assert cfg.gender_experience_enabled is False
    assert cfg.gender_affect_weight == pytest.approx(0.20)
    assert cfg.gender_motivation_weight == pytest.approx(1.0)
    assert cfg.gender_internalization_rate == pytest.approx(0.05)
    assert cfg.gender_recovery_rate == pytest.approx(0.03)
    assert cfg.gender_event_memory_max == 256
    expected = {
        "gender_experience_enabled",
        "gender_affect_weight",
        "gender_motivation_weight",
        "gender_internalization_rate",
        "gender_recovery_rate",
        "gender_event_memory_max",
    }
    assert expected <= set(ConfigPatch.model_fields)


def test_gender_axes_are_independent_and_allow_custom_open_axes() -> None:
    axes = GenderAxes(
        feminine=0.9,
        masculine=0.8,
        androgynous=0.7,
        custom={"two-spirit-context": 0.6},
    )
    assert axes.feminine == 0.9
    assert axes.masculine == 0.8
    assert axes.custom["two-spirit-context"] == 0.6


@pytest.mark.parametrize("bad", [-0.01, 1.01, math.inf, math.nan])
def test_gender_axes_reject_out_of_bounds_and_nonfinite_custom_values(bad: float) -> None:
    with pytest.raises(ValidationError):
        GenderAxes(custom={"custom": bad})


def test_profile_supports_multiple_labels_and_zero_dysphoria_sensitivity() -> None:
    profile = _profile()
    assert profile.felt_affinities == {"woman": 0.8, "nonbinary": 0.6}
    assert profile.body_preferences["voice"].dysphoria_sensitivity == 0.0
    assert profile.initial_self_understanding.labels == ["questioning"]


def test_profile_rejects_overlapping_timeline_segments() -> None:
    with pytest.raises(ValidationError, match="overlap"):
        _profile(
            felt_timeline=[
                GenderProfileSegment(
                    start_tick=0,
                    end_tick=20,
                    affinities={"nonbinary": 0.8},
                ),
                GenderProfileSegment(
                    start_tick=10,
                    end_tick=30,
                    affinities={"woman": 0.8},
                ),
            ]
        )


def test_life_course_accepts_adult_start_and_rejects_reverse_order() -> None:
    adult = _life_course()
    assert adult.stages[0].stage is GenderLifeStage.ADULTHOOD
    with pytest.raises(ValidationError, match="monotonic"):
        LifeCoursePlan(
            stages=[
                LifeCourseStage(
                    stage=GenderLifeStage.ADULTHOOD, duration_ticks=10
                ),
                LifeCourseStage(
                    stage=GenderLifeStage.ADOLESCENCE, duration_ticks=10
                ),
            ]
        )


def test_hostile_event_cannot_carry_custom_dialogue() -> None:
    with pytest.raises(ValidationError, match="free-text"):
        GenderEventRequest(
            type=GenderEventType.MISGENDERING,
            domain="social",
            context_code="public_interaction",
            note="custom hostile dialogue",
        )


def test_affirming_event_may_carry_a_bounded_note() -> None:
    event = GenderEventRequest(
        type=GenderEventType.AFFIRMATION,
        domain="pronouns",
        context_code="trusted_friend",
        note="The declared pronouns were respected.",
    )
    assert event.note is not None


def test_scenario_is_explicit_and_unspecified_agents_are_not_invented() -> None:
    scenario = GenderScenario(
        scenario_id="custom-one-agent",
        seed=123,
        agents={
            0: GenderScenarioAgent(
                profile=_profile(),
                life_course=_life_course(),
            )
        },
        social_context=GenderSocialContext(),
    )
    assert scenario.enable is True
    assert set(scenario.agents) == {0}


def test_scenario_rejects_negative_agent_id() -> None:
    with pytest.raises(ValidationError, match="agent IDs"):
        GenderScenario(
            scenario_id="bad-agent",
            agents={
                -1: GenderScenarioAgent(
                    profile=_profile(),
                    life_course=_life_course(),
                )
            },
        )
