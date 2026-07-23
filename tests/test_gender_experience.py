"""Phase-8 lifecycle, preset and factorised-engine invariants."""
from __future__ import annotations

import pytest

from core.gender_experience import GenderExperienceEngine, alignment
from core.gender_lifecycle import GenderLifecycle
from core.gender_scenarios import (
    PRESET_DESCRIPTIONS,
    derive_gender_seed,
    get_gender_scenario,
    list_gender_scenarios,
)
from schemas.models import (
    BodyDomainPreference,
    GenderAxes,
    GenderEventRequest,
    GenderEventType,
    GenderIntentRequest,
    GenderIntentType,
    GenderLifeStage,
    GenderProfile,
    GenderSelfUnderstanding,
    GenderSocialContext,
    LifeCoursePlan,
    LifeCourseStage,
    SimConfig,
    TransitionDimension,
    TransitionStatus,
)


def _config(**updates) -> SimConfig:
    return SimConfig(
        gender_experience_enabled=True,
        persist_memory=False,
        trace_logging=False,
        **updates,
    )


def _engine(
    preset_id: str = "euphoria_led",
    *,
    config: SimConfig | None = None,
    context: GenderSocialContext | None = None,
) -> GenderExperienceEngine:
    scenario = get_gender_scenario(preset_id, seed=91)
    agent = scenario.agents[0]
    return GenderExperienceEngine(
        config or _config(),
        agent_id=0,
        profile=agent.profile,
        life_course=agent.life_course,
        social_context=context or scenario.social_context,
        seed=scenario.seed,
    )


def test_all_approved_presets_are_complete_and_inspectable() -> None:
    expected = {
        "transfeminine_early",
        "transfeminine_late",
        "transmasculine_early",
        "transmasculine_late",
        "nonbinary",
        "genderfluid",
        "agender",
        "euphoria_led",
        "social_transition_only",
        "partial_medical_transition",
        "cis_control",
    }
    assert set(PRESET_DESCRIPTIONS) == expected
    listed = list_gender_scenarios(seed=7)
    assert [item["preset_id"] for item in listed] == list(PRESET_DESCRIPTIONS)
    for item in listed:
        manifest = item["manifest"]
        assert manifest["preset_id"] == item["preset_id"]
        assert manifest["seed"] == 7
        assert manifest["agents"]["0"]["profile"]["preferred_expression"]
        assert manifest["agents"]["0"]["life_course"]["stages"]


def test_per_agent_seed_is_stable_and_order_independent() -> None:
    first = {agent_id: derive_gender_seed(42, agent_id) for agent_id in [3, 1, 2]}
    second = {agent_id: derive_gender_seed(42, agent_id) for agent_id in [1, 2, 3]}
    assert first == second
    assert len(set(first.values())) == 3
    assert derive_gender_seed(43, 1) != derive_gender_seed(42, 1)


def test_lifecycle_can_start_in_adulthood_and_emits_neutral_changes() -> None:
    target = GenderAxes(androgynous=1.0)
    lifecycle = GenderLifecycle(
        LifeCoursePlan(
            stages=[
                LifeCourseStage(
                    stage=GenderLifeStage.ADULTHOOD,
                    duration_ticks=1,
                    body_targets={"voice": target},
                    body_change_rate=0.5,
                ),
                LifeCourseStage(
                    stage=GenderLifeStage.LATER_LIFE,
                    duration_ticks=2,
                ),
            ]
        ),
        initial_body={"voice": GenderAxes()},
    )
    first = lifecycle.advance()
    assert first.stage is GenderLifeStage.ADULTHOOD
    assert first.body["voice"].androgynous == pytest.approx(0.5)
    assert [event.type for event in first.events] == [GenderEventType.VOICE_CHANGE]
    second = lifecycle.advance()
    assert second.stage is GenderLifeStage.LATER_LIFE
    assert GenderEventType.LIFE_STAGE_CHANGE in {
        event.type for event in second.events
    }


def test_axis_alignment_is_independent_and_bounded() -> None:
    assert alignment(GenderAxes(), GenderAxes()) == 1.0
    score = alignment(
        GenderAxes(feminine=1.0, masculine=0.7),
        GenderAxes(feminine=0.0, masculine=0.7),
    )
    assert score == pytest.approx(2.0 / 3.0)


def test_empty_body_and_expression_domains_are_neutral() -> None:
    profile = GenderProfile(
        profile_id="empty-domains",
        assigned_category="open",
        felt_affinities={},
        gender_salience=0.0,
        initial_self_understanding=GenderSelfUnderstanding(),
    )
    plan = LifeCoursePlan(
        stages=[
            LifeCourseStage(
                stage=GenderLifeStage.ADULTHOOD,
                duration_ticks=10,
            )
        ]
    )
    engine = GenderExperienceEngine(
        _config(), profile=profile, life_course=plan
    )
    state = engine.update(1)
    assert state is not None
    assert state.congruence.body == 1.0
    assert state.congruence.expression == 1.0
    assert state.affect.dysphoria == 0.0


def test_euphoria_led_path_has_negligible_dysphoria_despite_mismatch() -> None:
    engine = _engine("euphoria_led")
    states = [engine.update(tick) for tick in range(1, 7)]
    assert all(state is not None for state in states)
    assert max(state.affect.dysphoria for state in states if state) == 0.0
    # Expression moves toward preference and can yield positive affect without
    # distress ever becoming identity evidence.
    assert max(state.affect.euphoria for state in states if state) > 0.0
    assert states[-1].self_understanding.labels == [
        "transfeminine",
        "nonbinary",
    ]


def test_affirmation_produces_euphoria_that_decays_while_fulfillment_persists() -> None:
    engine = _engine("euphoria_led")
    engine.update(1)
    engine.queue_event(
        GenderEventRequest(
            type=GenderEventType.AFFIRMATION,
            domain="general",
            intensity=1.0,
            context_code="trusted_friend",
        )
    )
    affirmed = engine.update(2)
    assert affirmed is not None
    assert affirmed.affect.euphoria > 0.0
    assert affirmed.affect.dysphoria == 0.0
    later = None
    for tick in range(3, 11):
        later = engine.update(tick)
    assert later is not None
    assert later.affect.euphoria < affirmed.affect.euphoria
    assert later.affect.fulfillment > 0.0


def test_external_and_internalized_transphobia_are_separate_and_recoverable() -> None:
    config = _config(
        gender_internalization_rate=0.4,
        gender_recovery_rate=0.4,
    )
    engine = _engine(
        "nonbinary",
        config=config,
        context=GenderSocialContext(
            norm_rigidity=0.9,
            institutional_hostility=0.0,
            community_visibility=0.1,
            positive_representation=0.1,
        ),
    )
    baseline_checksum = engine.profile_checksum
    engine.update(1)
    engine.queue_event(
        GenderEventRequest(
            type=GenderEventType.DISCRIMINATION,
            domain="public",
            intensity=1.0,
            context_code="institutional_interaction",
        )
    )
    exposed = engine.update(2)
    assert exposed is not None
    assert exposed.minority_stress.external_current == 1.0
    assert exposed.minority_stress.internalized_transphobia > 0.0
    internalized_peak = exposed.minority_stress.internalized_transphobia
    engine.queue_event(
        GenderEventRequest(
            type=GenderEventType.SUPPORT,
            domain="general",
            intensity=1.0,
            context_code="trusted_support",
        )
    )
    engine.queue_event(
        GenderEventRequest(
            type=GenderEventType.COMMUNITY_CONTACT,
            domain="general",
            intensity=1.0,
            context_code="community_connection",
        )
    )
    recovered = engine.update(3)
    assert recovered is not None
    assert recovered.minority_stress.external_current == 0.0
    assert (
        recovered.minority_stress.internalized_transphobia
        < internalized_peak
    )
    assert recovered.resilience.index > exposed.resilience.index
    assert engine.profile_checksum == baseline_checksum


def test_distress_and_expression_never_auto_assign_a_trans_label() -> None:
    profile = GenderProfile(
        profile_id="unlabeled-high-mismatch",
        assigned_category="male",
        felt_affinities={"unlabeled": 0.8},
        gender_salience=1.0,
        available_vocabulary=["questioning", "trans woman"],
        body_preferences={
            "voice": BodyDomainPreference(
                initial=GenderAxes(masculine=1.0),
                preferred=GenderAxes(feminine=1.0),
                salience=1.0,
                dysphoria_sensitivity=1.0,
                euphoria_sensitivity=0.0,
            )
        },
        initial_self_understanding=GenderSelfUnderstanding(
            labels=[],
            questioning=True,
            certainty=0.0,
            fit_by_label={"trans woman": 0.0},
            known_vocabulary=["questioning", "trans woman"],
        ),
    )
    plan = LifeCoursePlan(
        stages=[
            LifeCourseStage(
                stage=GenderLifeStage.ADULTHOOD,
                duration_ticks=100,
                norm_exposure=1.0,
            )
        ]
    )
    engine = GenderExperienceEngine(
        _config(), profile=profile, life_course=plan
    )
    for tick in range(1, 12):
        state = engine.update(tick)
    assert state is not None
    assert state.affect.dysphoria > 0.0
    assert state.self_understanding.labels == []
    assert state.self_understanding.questioning is True


def test_self_authored_label_revision_does_not_require_dysphoria() -> None:
    engine = _engine("euphoria_led")
    engine.update(1)
    engine.queue_event(
        GenderEventRequest(
            type=GenderEventType.LABEL_REVISION,
            domain="nonbinary",
            intensity=0.8,
            context_code="self_reflection",
            note="A self-authored revision after reversible exploration.",
        )
    )
    revised = engine.update(2)
    assert revised is not None
    assert revised.affect.dysphoria == 0.0
    assert revised.self_understanding.labels == ["nonbinary"]


def test_accentuation_is_personal_baseline_relative_and_names_compensation() -> None:
    engine = _engine("transfeminine_late")
    state = engine.update(1)
    assert state is not None
    presentation = state.expression["presentation"]
    assert presentation.accentuation > 0.0
    assert "assigned_compensation" in {
        driver.value for driver in presentation.drivers
    }


def test_transition_dimensions_progress_only_with_intent_and_access() -> None:
    engine = _engine("partial_medical_transition")
    before = engine.update(1)
    assert before is not None
    assert all(item.progress == 0.0 for item in before.transitions.values())
    original_labels = list(before.self_understanding.labels)
    engine.queue_intent(
        GenderIntentRequest(
            type=GenderIntentType.SEEK_VOICE_WORK,
            transition_dimension=TransitionDimension.VOICE,
            domain="voice",
            urgency=0.9,
        )
    )
    started = engine.update(2)
    assert started is not None
    voice_progress = started.transitions[TransitionDimension.VOICE].progress
    assert voice_progress > 0.0
    assert started.transitions[TransitionDimension.HORMONAL].progress == 0.0

    engine.queue_intent(
        GenderIntentRequest(
            type=GenderIntentType.PAUSE,
            transition_dimension=TransitionDimension.VOICE,
        )
    )
    paused = engine.update(3)
    assert paused is not None
    assert paused.transitions[TransitionDimension.VOICE].status is TransitionStatus.PAUSED
    assert paused.transitions[TransitionDimension.VOICE].progress == voice_progress

    engine.queue_intent(
        GenderIntentRequest(
            type=GenderIntentType.REVERSE,
            transition_dimension=TransitionDimension.VOICE,
        )
    )
    reversed_state = engine.update(4)
    assert reversed_state is not None
    assert reversed_state.transitions[TransitionDimension.VOICE].progress < voice_progress
    assert reversed_state.self_understanding.labels == original_labels

    engine.queue_intent(
        GenderIntentRequest(
            type=GenderIntentType.RESUME,
            transition_dimension=TransitionDimension.VOICE,
        )
    )
    resumed = engine.update(5)
    assert resumed is not None
    assert (
        resumed.transitions[TransitionDimension.VOICE].progress
        > reversed_state.transitions[TransitionDimension.VOICE].progress
    )
    assert resumed.self_understanding.labels == original_labels


def test_event_update_rolls_back_queue_and_ledger_on_failure(monkeypatch) -> None:
    engine = _engine("nonbinary")
    engine.update(1)
    queued = engine.queue_event(
        GenderEventRequest(
            type=GenderEventType.AFFIRMATION,
            domain="general",
            context_code="test",
        )
    )
    pending_before = engine.pending_events
    ledger_before = engine.event_ledger
    checksum_before = engine.profile_checksum

    def fail(_events):
        raise RuntimeError("synthetic update failure")

    monkeypatch.setattr(engine, "_update_expression", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        engine.update(2)
    assert [event.event_id for event in engine.pending_events] == [
        queued.event_id
    ]
    assert engine.pending_events == pending_before
    assert engine.event_ledger == ledger_before
    assert engine.profile_checksum == checksum_before


def test_same_seed_and_inputs_produce_identical_state_and_ledgers() -> None:
    left = _engine("genderfluid")
    right = _engine("genderfluid")
    for engine in (left, right):
        engine.queue_event(
            GenderEventRequest(
                type=GenderEventType.EXPLORATION,
                domain="genderfluid",
                context_code="reversible_private_exploration",
                note="Configured self-exploration.",
            )
        )
        engine.queue_intent(
            GenderIntentRequest(
                type=GenderIntentType.EXPLORE_IDENTITY,
                urgency=0.7,
            )
        )
    for tick in range(1, 12):
        left_state = left.update(tick)
        right_state = right.update(tick)
        assert left_state == right_state
    assert left.event_ledger == right.event_ledger
    assert left.profile_checksum == right.profile_checksum


def test_influence_is_strictly_capped() -> None:
    engine = _engine("nonbinary")
    engine.update(1)
    for event_type in (
        GenderEventType.THREAT,
        GenderEventType.DISCRIMINATION,
        GenderEventType.INVALIDATION,
    ):
        engine.queue_event(
            GenderEventRequest(
                type=event_type,
                domain="public",
                intensity=1.0,
                context_code="bounded_stress_test",
            )
        )
    engine.update(2)
    influence = engine.influence()
    assert -0.08 <= influence.mood_delta <= 0.08
    assert -0.05 <= influence.confidence_delta <= 0.05
    assert -0.03 <= influence.coherence_delta <= 0.03
    assert all(0.0 <= value <= 1.0 for value in influence.goal_pressures.values())


def test_engine_is_inert_without_flag_or_explicit_profile() -> None:
    unconfigured = GenderExperienceEngine(SimConfig())
    assert unconfigured.active is False
    assert unconfigured.update(1) is None

    scenario = get_gender_scenario("nonbinary")
    configured_but_off = GenderExperienceEngine(
        SimConfig(gender_experience_enabled=False),
        profile=scenario.agents[0].profile,
        life_course=scenario.agents[0].life_course,
    )
    assert configured_but_off.update(1) is None

