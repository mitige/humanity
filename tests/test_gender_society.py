"""Phase-8 privacy, recognition and one-tick-deferred society tests."""
from __future__ import annotations

from core.gender_scenarios import get_gender_scenario
from core.gender_society import (
    GenderSociety,
    _stable_unit,
    build_public_gender_projection,
)
from core.society import SocietyManager
from schemas.models import (
    GenderEventType,
    GenderObserverDisposition,
    GenderRecognitionState,
    GenderScenario,
    GenderScenarioAgent,
    GenderSocialContext,
    SimConfig,
)


def _profile_agent(preset: str, profile_id: str, *, public: bool):
    source = get_gender_scenario(preset, seed=19).agents[0]
    understanding = source.profile.initial_self_understanding.model_copy(
        deep=True
    )
    private_labels = list(understanding.labels)
    if "private-only-label" not in private_labels:
        private_labels.append("private-only-label")
    known = list(understanding.known_vocabulary)
    if "private-only-label" not in known:
        known.append("private-only-label")
    fit = dict(understanding.fit_by_label)
    fit["private-only-label"] = 0.9
    disclosures = dict(understanding.disclosure_scopes)
    disclosures["public"] = (
        [understanding.labels[0]] if public and understanding.labels else []
    )
    disclosures["public:pronouns"] = ["they/them"] if public else []
    disclosures["public:name"] = ["PublicName"] if public else []
    understanding = understanding.model_copy(
        update={
            "labels": private_labels,
            "known_vocabulary": known,
            "fit_by_label": fit,
            "disclosure_scopes": disclosures,
        },
        deep=True,
    )
    profile = source.profile.model_copy(
        update={
            "profile_id": profile_id,
            "felt_affinities": {
                **source.profile.felt_affinities,
                "private-only-label": 0.9,
            },
            "available_vocabulary": [
                *source.profile.available_vocabulary,
                "private-only-label",
            ],
            "initial_self_understanding": understanding,
        },
        deep=True,
    )
    return GenderScenarioAgent(
        profile=profile,
        life_course=source.life_course,
    )


def _scenario(
    *,
    context: GenderSocialContext,
    observer_one: GenderObserverDisposition,
    only_agent_one: bool = False,
) -> GenderScenario:
    agents = {
        1: _profile_agent("transfeminine_early", "profile-one", public=True)
    }
    if not only_agent_one:
        agents[0] = _profile_agent("nonbinary", "profile-zero", public=True)
    agents[1] = agents[1].model_copy(
        update={"observer_disposition": observer_one},
        deep=True,
    )
    return GenderScenario(
        scenario_id="two-agent-gender-society",
        seed=19,
        agents=agents,
        social_context=context,
    )


def _manager(scenario: GenderScenario) -> SocietyManager:
    manager = SocietyManager(
        SimConfig(
            grid_size=6,
            n_agents=1,
            n_objects=0,
            world_noise=0.0,
            persist_memory=False,
            trace_logging=False,
        )
    )
    manager.install_gender_scenario(scenario)
    if len(manager.agents) > 1:
        manager.world.agents[0].x = manager.world.agents[1].x = 3
        manager.world.agents[0].y = manager.world.agents[1].y = 3
        manager.agents[1].theory_of_mind.model_of(0).trust = 1.0
        manager.agents[0].theory_of_mind.model_of(1).trust = 1.0
    return manager


def test_public_projection_contains_only_disclosed_state() -> None:
    scenario = _scenario(
        context=GenderSocialContext(hostility_enabled=False),
        observer_one=GenderObserverDisposition(),
    )
    manager = _manager(scenario)
    manager.tick()
    private_state = manager.agents[0].gender_state()
    assert private_state is not None
    assert "private-only-label" in private_state.self_understanding.labels
    projection = build_public_gender_projection(private_state)
    dumped = projection.model_dump(mode="json")
    assert projection.labels == [
        private_state.self_understanding.disclosure_scopes["public"][0]
    ]
    assert projection.pronouns == ["they/them"]
    assert projection.name == "PublicName"
    serialized = str(dumped)
    assert "private-only-label" not in serialized
    assert "body" not in serialized
    assert "internalized" not in serialized
    assert "transition" not in serialized


def test_affirmation_is_generated_after_tick_and_consumed_next_tick() -> None:
    scenario = _scenario(
        context=GenderSocialContext(
            hostility_enabled=False,
            community_visibility=0.0,
        ),
        observer_one=GenderObserverDisposition(
            respect_propensity=1.0,
            learned_bias=0.0,
            affirmation_tendency=1.0,
        ),
    )
    manager = _manager(scenario)
    first = manager.tick()
    assert not first[0].gender_experience.affect.last_affirming_event_ids
    pending_for_zero = [
        event for event in manager.gender_society.pending_events
        if event.target_id == 0 and event.actor_id == 1
    ]
    assert pending_for_zero
    assert all(event.type not in {
        GenderEventType.INVALIDATION,
        GenderEventType.MISGENDERING,
        GenderEventType.REJECTION,
    } for event in pending_for_zero)

    second = manager.tick()
    assert second[0].gender_experience.affect.last_affirming_event_ids
    assert any(
        event.provenance.value == "society"
        for event in manager.agents[0].gender_experience.event_ledger
    )


def test_supportive_only_context_suppresses_all_hostile_outputs() -> None:
    scenario = _scenario(
        context=GenderSocialContext(
            norm_rigidity=1.0,
            institutional_hostility=1.0,
            hostility_enabled=False,
        ),
        observer_one=GenderObserverDisposition(
            respect_propensity=0.0,
            learned_bias=1.0,
            affirmation_tendency=0.0,
        ),
    )
    manager = _manager(scenario)
    for _ in range(6):
        manager.tick()
    hostile = {
        GenderEventType.MISGENDERING,
        GenderEventType.INVALIDATION,
        GenderEventType.REJECTION,
        GenderEventType.DISCRIMINATION,
        GenderEventType.THREAT,
    }
    assert all(
        event.type not in hostile
        for event in manager.gender_society.pending_events
    )
    assert not hostile & {
        GenderEventType(name)
        for name in manager.gender_society.event_counts
    }


def test_configured_externalized_transphobia_changes_stress_not_profile() -> None:
    scenario = _scenario(
        context=GenderSocialContext(
            norm_rigidity=1.0,
            institutional_hostility=1.0,
            hostility_enabled=True,
        ),
        observer_one=GenderObserverDisposition(
            respect_propensity=0.0,
            learned_bias=1.0,
            affirmation_tendency=0.0,
        ),
    )
    manager = _manager(scenario)
    checksum = manager.agents[0].gender_experience.profile_checksum
    manager.tick()
    pending = [
        event for event in manager.gender_society.pending_events
        if event.target_id == 0 and event.actor_id == 1
    ]
    assert pending
    assert pending[0].type is GenderEventType.INVALIDATION
    assert pending[0].note is None
    manager.tick()
    state = manager.agents[0].gender_state()
    assert state.minority_stress.external_current > 0.0
    assert manager.agents[0].gender_experience.profile_checksum == checksum


def test_accidental_misgendering_requires_a_recognition_knowledge_gap() -> None:
    projection_scenario = _scenario(
        context=GenderSocialContext(),
        observer_one=GenderObserverDisposition(),
    )
    manager = _manager(projection_scenario)
    manager.tick()
    projection = manager.gender_society.projections[0]
    disposition = GenderObserverDisposition(
        respect_propensity=0.6,
        learned_bias=0.0,
        affirmation_tendency=0.0,
    )
    context = GenderSocialContext(
        norm_rigidity=1.0,
        institutional_hostility=0.0,
        hostility_enabled=True,
    )
    # Pick the first fully deterministic seed whose hostility draw falls below
    # this observer/context probability.
    probability = 0.25 * (1.0 - 0.6) + 0.20
    seed = next(
        value for value in range(1000)
        if _stable_unit(value, 1, 1, 0, "hostility") < probability
    )
    society = GenderSociety(
        manager.config,
        context=context,
        seed=seed,
        dispositions={1: disposition},
    )
    first = society._events_for_pair(
        tick=1,
        observer_id=1,
        target_id=0,
        projection=projection,
        prior=None,
        disposition=disposition,
        relationship_trust=0.5,
    )
    assert first[0].type is GenderEventType.MISGENDERING
    assert first[0].deliberate is False

    known = GenderRecognitionState(
        observer_id=1,
        target_id=0,
        known_labels=projection.labels,
        known_pronouns=projection.pronouns,
        respect_propensity=0.6,
        relationship_trust=0.5,
        knowledge_confidence=1.0,
    )
    second = society._events_for_pair(
        tick=1,
        observer_id=1,
        target_id=0,
        projection=projection,
        prior=known,
        disposition=disposition,
        relationship_trust=0.5,
    )
    assert second[0].type is GenderEventType.REJECTION


def test_unspecified_agents_receive_no_silent_profile() -> None:
    scenario = _scenario(
        context=GenderSocialContext(hostility_enabled=False),
        observer_one=GenderObserverDisposition(),
        only_agent_one=True,
    )
    manager = _manager(scenario)
    traces = manager.tick()
    assert len(traces) == 2
    assert manager.agents[0].gender_state() is None
    assert manager.agents[1].gender_state() is not None
    assert set(manager.gender_society.projections) == {1}


def test_reversing_agent_dictionary_order_keeps_social_results_identical() -> None:
    scenario = _scenario(
        context=GenderSocialContext(
            norm_rigidity=0.7,
            institutional_hostility=0.3,
        ),
        observer_one=GenderObserverDisposition(
            respect_propensity=0.55,
            learned_bias=0.35,
            affirmation_tendency=0.65,
        ),
    )
    left = _manager(scenario)
    right = _manager(scenario)
    right.agents = dict(reversed(list(right.agents.items())))
    for _ in range(8):
        left_traces = left.tick()
        right_traces = right.tick()
        assert left_traces == right_traces
        assert left.gender_society.state() == right.gender_society.state()
        for agent_id in sorted(left.agents):
            assert (
                left.agents[agent_id].gender_experience.event_ledger
                == right.agents[agent_id].gender_experience.event_ledger
            )


def test_public_society_state_never_serializes_private_inputs() -> None:
    scenario = _scenario(
        context=GenderSocialContext(),
        observer_one=GenderObserverDisposition(),
    )
    manager = _manager(scenario)
    manager.tick()
    serialized = str(manager.gender_society_state().model_dump(mode="json"))
    assert "private-only-label" not in serialized
    assert "assigned_category" not in serialized
    assert "body_preferences" not in serialized
    assert "internalized_transphobia" not in serialized
