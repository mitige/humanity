"""Phase-8 cognitive integration and default-off regression guarantees."""
from __future__ import annotations

from core.agent import CognitiveAgent
from core.gender_experience import GenderInfluence
from core.gender_scenarios import get_gender_scenario
from core.self_model import SelfModel
from schemas.models import (
    ActionDecision,
    ActionType,
    EmotionState,
    GenderEventRequest,
    GenderEventType,
    SimConfig,
    StepResult,
)


def _fast_config(**updates) -> SimConfig:
    return SimConfig(
        random_seed=71,
        world_noise=0.0,
        persist_memory=False,
        trace_logging=False,
        **updates,
    )


def _trace_projection(trace) -> dict:
    data = trace.model_dump(mode="json")
    data.pop("gender_experience", None)
    return data


def test_phase8_default_off_leaves_trace_goals_and_sources_clean() -> None:
    default = CognitiveAgent(_fast_config())
    explicit_off = CognitiveAgent(
        _fast_config(gender_experience_enabled=False)
    )
    for _ in range(8):
        left = default.cognitive_cycle()
        right = explicit_off.cognitive_cycle()
        assert left.gender_experience is None
        assert right.gender_experience is None
        assert _trace_projection(left) == _trace_projection(right)
        assert all(
            coalition.source != "gender_experience"
            for coalition in left.workspace.competition
        )
        assert not {
            "seek_safety",
            "explore_gender",
            "seek_affirmation",
            "pursue_transition_intent",
        } & {goal.need for goal in left.goals}


def test_enabled_flag_without_profile_is_still_inert() -> None:
    agent = CognitiveAgent(
        _fast_config(gender_experience_enabled=True)
    )
    trace = agent.cognitive_cycle()
    assert trace.gender_experience is None
    assert agent.gender_state() is None
    assert all(
        coalition.source != "gender_experience"
        for coalition in trace.workspace.competition
    )


def test_installed_profile_populates_trace_workspace_goals_and_background_state() -> None:
    scenario = get_gender_scenario("euphoria_led", seed=71)
    configured = scenario.agents[0]
    agent = CognitiveAgent(
        _fast_config(gender_experience_enabled=True)
    )
    agent.install_gender_experience(
        configured.profile,
        configured.life_course,
        social_context=scenario.social_context,
        seed=scenario.seed,
    )
    agent.queue_gender_event(
        GenderEventRequest(
            type=GenderEventType.AFFIRMATION,
            domain="general",
            intensity=1.0,
            context_code="configured_affirmation",
        )
    )
    trace = agent.cognitive_cycle()
    assert trace.gender_experience is not None
    assert trace.gender_experience.affect.dysphoria == 0.0
    assert {
        "seek_safety",
        "explore_gender",
        "seek_affirmation",
        "pursue_transition_intent",
    } <= {goal.need for goal in trace.goals}
    assert any(
        coalition.source == "gender_experience"
        for coalition in trace.workspace.competition
    )
    background = agent.consciousness_state()
    assert background["gender_experience"] == (
        trace.gender_experience.model_dump()
    )
    serialized = trace.model_dump(mode="json")
    assert "assigned_category" not in str(serialized)
    assert "body_preferences" not in str(serialized)


def test_agent_gender_event_is_consumed_on_next_tick() -> None:
    scenario = get_gender_scenario("nonbinary", seed=71)
    configured = scenario.agents[0]
    agent = CognitiveAgent(
        _fast_config(gender_experience_enabled=True)
    )
    agent.install_gender_experience(
        configured.profile,
        configured.life_course,
        social_context=scenario.social_context,
        seed=scenario.seed,
    )
    first = agent.cognitive_cycle()
    queued = agent.queue_gender_event(
        GenderEventRequest(
            type=GenderEventType.AFFIRMATION,
            domain="general",
            intensity=1.0,
            context_code="trusted_support",
        )
    )
    assert queued.event_id not in first.gender_experience.recent_event_ids
    second = agent.cognitive_cycle()
    assert queued.event_id in second.gender_experience.recent_event_ids


def test_active_phase8_agent_is_deterministic() -> None:
    scenario = get_gender_scenario("genderfluid", seed=71)
    agents = []
    for _ in range(2):
        agent = CognitiveAgent(
            _fast_config(gender_experience_enabled=True)
        )
        configured = scenario.agents[0]
        agent.install_gender_experience(
            configured.profile,
            configured.life_course,
            social_context=scenario.social_context,
            seed=scenario.seed,
        )
        agents.append(agent)
    for _ in range(12):
        assert agents[0].cognitive_cycle() == agents[1].cognitive_cycle()


def test_self_model_applies_gender_caps_after_ordinary_update() -> None:
    config = _fast_config(gender_experience_enabled=True)
    model = SelfModel(config)
    decision = ActionDecision(
        action=ActionType.OBSERVE,
        confidence=0.5,
        rationale="test",
        candidate_scores={"observe": 1.0},
    )
    result = StepResult(
        tick=1,
        action=ActionType.OBSERVE,
        energy_delta=0.0,
        new_energy=100.0,
        events=[],
        actual={
            "danger": 0.0,
            "novelty": 0.0,
            "goal_progress": 0.0,
            "energy_value": 0.0,
            "utility": 0.0,
        },
    )
    model.update(
        decision=decision,
        result=result,
        prediction_error=0.0,
        emotion=EmotionState(),
        goals=[],
        tick=1,
        gender_influence=GenderInfluence(
            mood_delta=-1.0,
            confidence_delta=-1.0,
            coherence_delta=-1.0,
        ),
    )
    state = model.snapshot()
    # The engine cannot push more than the three approved caps even if a caller
    # constructs an out-of-range influence object.
    assert state.mood == -0.08
    assert 0.0 <= state.confidence
    assert state.coherence == 0.97
    assert state.identity == "Aurora-fn-01"
