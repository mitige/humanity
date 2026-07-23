"""Factorised, non-diagnostic model of situated gender experience.

The engine deliberately keeps five things separate:

* the configured private felt profile;
* the simulated agent's evolving self-understanding;
* body/expression/social congruence;
* dysphoria, euphoria and sustained fulfilment;
* external/internalised minority stress and resilience.

No update infers identity from distress, expression, embodiment, an observer, or
a transition choice.  The implementation is a qualitative research instrument,
not a diagnostic, clinical, predictive, or phenomenological model.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from statistics import fmean

import numpy as np

from core.gender_lifecycle import (
    GenderLifecycle,
    axes_from_values,
    axes_values,
    mean_axis_distance,
    move_axes,
)
from core.gender_scenarios import derive_gender_seed
from schemas.models import (
    BodyDomainState,
    ExpressionChannelState,
    ExpressionDriver,
    GenderAffectState,
    GenderAxes,
    GenderCongruenceState,
    GenderDebugState,
    GenderEvent,
    GenderEventProvenance,
    GenderEventRequest,
    GenderEventType,
    GenderExperienceState,
    GenderIntent,
    GenderIntentRequest,
    GenderIntentStatus,
    GenderIntentType,
    GenderMinorityStressState,
    GenderProfile,
    GenderResilienceState,
    GenderSelfUnderstanding,
    GenderSocialContext,
    LifeCoursePlan,
    SimConfig,
    TransitionDimension,
    TransitionDimensionState,
    TransitionReversibility,
    TransitionStatus,
)


_AFFIRMING_EVENTS = {
    GenderEventType.AFFIRMATION,
    GenderEventType.CORRECT_NAME_PRONOUN,
    GenderEventType.SUPPORT,
    GenderEventType.COMMUNITY_CONTACT,
    GenderEventType.POSITIVE_REPRESENTATION,
    GenderEventType.LEGAL_RECOGNITION,
    GenderEventType.ACCESS_GRANTED,
}

_HOSTILE_EVENTS = {
    GenderEventType.MISGENDERING,
    GenderEventType.INVALIDATION,
    GenderEventType.REJECTION,
    GenderEventType.DISCRIMINATION,
    GenderEventType.THREAT,
    GenderEventType.CARE_BARRIER,
    GenderEventType.ACCESS_DENIED,
}

_SELF_AUTHORED_EVIDENCE_EVENTS = {
    GenderEventType.REFLECTION,
    GenderEventType.EXPLORATION,
    GenderEventType.VOCABULARY_DISCOVERY,
    GenderEventType.LABEL_REVISION,
}

_INTENT_DIMENSIONS = {
    GenderIntentType.SEEK_ADMINISTRATIVE_RECOGNITION:
        TransitionDimension.ADMINISTRATIVE,
    GenderIntentType.SEEK_VOICE_WORK: TransitionDimension.VOICE,
    GenderIntentType.SEEK_HORMONAL_CARE: TransitionDimension.HORMONAL,
    GenderIntentType.SEEK_SURGICAL_CARE: TransitionDimension.SURGICAL,
    GenderIntentType.ASSERT_NAME_PRONOUNS: TransitionDimension.SOCIAL,
}

_TRANSITION_RATES = {
    TransitionDimension.SOCIAL: 0.10,
    TransitionDimension.ADMINISTRATIVE: 0.06,
    TransitionDimension.VOICE: 0.055,
    TransitionDimension.HORMONAL: 0.025,
    TransitionDimension.SURGICAL: 0.12,
}


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _clip(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))


def _mean(values, default: float = 0.0) -> float:
    materialized = [float(value) for value in values]
    return float(fmean(materialized)) if materialized else float(default)


def _ema(previous: float, target: float, rate: float) -> float:
    return _clip01(float(previous) + float(rate) * (float(target) - float(previous)))


def _blend_axes(left: GenderAxes, right: GenderAxes, right_weight: float) -> GenderAxes:
    left_values = axes_values(left)
    right_values = axes_values(right)
    names = left_values.keys() | right_values.keys()
    weight = _clip01(right_weight)
    return axes_from_values(
        {
            name: (1.0 - weight) * left_values.get(name, 0.0)
            + weight * right_values.get(name, 0.0)
            for name in names
        }
    )


def alignment(current: GenderAxes, preferred: GenderAxes) -> float:
    """Independent-axis alignment used by every embodiment/expression domain."""
    return _clip01(1.0 - mean_axis_distance(current, preferred))


@dataclass(slots=True)
class GenderInfluence:
    """Strictly capped contribution to the ordinary cognitive architecture."""

    mood_delta: float = 0.0
    confidence_delta: float = 0.0
    coherence_delta: float = 0.0
    goal_pressures: dict[str, float] = field(default_factory=dict)
    activation: float = 0.0
    content: str = ""


class GenderExperienceEngine:
    """Own one agent's private profile, event ledger and factorised state."""

    def __init__(
        self,
        config: SimConfig,
        *,
        agent_id: int = 0,
        profile: GenderProfile | None = None,
        life_course: LifeCoursePlan | None = None,
        social_context: GenderSocialContext | None = None,
        seed: int | None = None,
        initial_events: list[GenderEvent] | None = None,
    ) -> None:
        self.config = config
        self.agent_id = int(agent_id)
        self._profile: GenderProfile | None = None
        self._life_course_plan: LifeCoursePlan | None = None
        self._social_context = (
            social_context or GenderSocialContext()
        ).model_copy(deep=True)
        self._seed = int(config.random_seed if seed is None else seed)
        self._rng = np.random.default_rng(
            derive_gender_seed(self._seed, self.agent_id)
        )
        self._lifecycle: GenderLifecycle | None = None
        self._profile_checksum = ""
        self._last_tick = 0
        self._last_state: GenderExperienceState | None = None
        self._next_event_id = 0
        self._next_intent_id = 0
        self._pending_events: list[GenderEvent] = []
        self._event_ledger: list[GenderEvent] = []
        self._pending_intents: list[GenderIntent] = []
        self._current_intent: GenderIntent | None = None
        self._active_transitions: dict[TransitionDimension, int] = {}
        self._understanding = GenderSelfUnderstanding()
        self._expression_axes: dict[str, dict[str, GenderAxes]] = {}
        self._rolling_expression_baseline: dict[str, GenderAxes] = {}
        self._body_axes: dict[str, GenderAxes] = {}
        self._previous_alignment: dict[str, float] = {}
        self._dysphoria_by_domain: dict[str, float] = {}
        self._euphoria_by_domain: dict[str, float] = {}
        self._fulfillment = 0.0
        self._stress = GenderMinorityStressState()
        self._resilience = GenderResilienceState()
        self._transitions: dict[
            TransitionDimension, TransitionDimensionState
        ] = {}
        self._social_congruence = 1.0
        self._administrative_congruence = 1.0
        if profile is not None or life_course is not None:
            if profile is None or life_course is None:
                raise ValueError("profile and life_course must be installed together")
            self.install(
                profile,
                life_course,
                social_context=social_context,
                seed=seed,
                initial_events=initial_events,
            )

    @property
    def active(self) -> bool:
        return bool(
            self.config.gender_experience_enabled
            and self._profile is not None
            and self._lifecycle is not None
        )

    @property
    def profile_checksum(self) -> str:
        return self._profile_checksum

    @property
    def event_ledger(self) -> list[GenderEvent]:
        return [event.model_copy(deep=True) for event in self._event_ledger]

    @property
    def pending_events(self) -> list[GenderEvent]:
        return [event.model_copy(deep=True) for event in self._pending_events]

    @property
    def current_state(self) -> GenderExperienceState | None:
        return (
            self._last_state.model_copy(deep=True)
            if self._last_state is not None
            else None
        )

    def install(
        self,
        profile: GenderProfile,
        life_course: LifeCoursePlan,
        *,
        social_context: GenderSocialContext | None = None,
        seed: int | None = None,
        initial_events: list[GenderEvent] | None = None,
    ) -> None:
        """Reset this module around one explicit, validated private profile."""
        self._profile = profile.model_copy(deep=True)
        self._life_course_plan = life_course.model_copy(deep=True)
        if social_context is not None:
            self._social_context = social_context.model_copy(deep=True)
        if seed is not None:
            self._seed = int(seed)
        self._rng = np.random.default_rng(
            derive_gender_seed(self._seed, self.agent_id)
        )
        self._profile_checksum = self._checksum(self._profile)
        self._last_tick = 0
        self._last_state = None
        self._next_event_id = 0
        self._next_intent_id = 0
        self._pending_events = []
        self._event_ledger = []
        self._pending_intents = []
        self._current_intent = None
        self._active_transitions = {}
        self._understanding = self._profile.initial_self_understanding.model_copy(
            deep=True
        )
        # The profile-level vocabulary is available to scenario designers, while
        # known_vocabulary records what the agent can currently use.
        self._expression_axes = {}
        self._rolling_expression_baseline = {}
        for channel, channel_profile in self._profile.preferred_expression.items():
            self._expression_axes[channel] = {
                "private": channel_profile.private_baseline.model_copy(deep=True),
                "trusted": channel_profile.trusted_baseline.model_copy(deep=True),
                "public": channel_profile.public_baseline.model_copy(deep=True),
            }
            self._rolling_expression_baseline[channel] = (
                channel_profile.private_baseline.model_copy(deep=True)
            )
        self._body_axes = {
            name: preference.initial.model_copy(deep=True)
            for name, preference in self._profile.body_preferences.items()
        }
        self._lifecycle = GenderLifecycle(
            self._life_course_plan,
            initial_body=self._body_axes,
        )
        self._previous_alignment = {}
        self._dysphoria_by_domain = {}
        self._euphoria_by_domain = {}
        self._fulfillment = 0.0
        self._stress = GenderMinorityStressState()
        initial_certainty = self._understanding.certainty
        self._resilience = GenderResilienceState(
            community=0.15 * self._social_context.community_visibility,
            positive_representation=0.25
            * self._social_context.positive_representation,
            pride=0.15 * initial_certainty,
            self_acceptance=0.35 * initial_certainty,
        )
        self._resilience = self._with_resilience_index(self._resilience)
        public_labels = self._understanding.disclosure_scopes.get("public", [])
        self._social_congruence = 0.82 if public_labels else 0.55
        self._administrative_congruence = (
            1.0
            if self._profile.transition_priorities.get(
                TransitionDimension.ADMINISTRATIVE, 0.0
            ) == 0.0
            else 0.5
        )
        self._transitions = self._initial_transition_states()
        for event in initial_events or []:
            installed = event.model_copy(
                update={"processed": False},
                deep=True,
            )
            self._pending_events.append(installed)
            self._next_event_id = max(
                self._next_event_id, int(installed.event_id) + 1
            )

    def set_social_context(self, context: GenderSocialContext) -> None:
        self._social_context = context.model_copy(deep=True)

    def queue_event(
        self,
        request: GenderEventRequest,
        *,
        provenance: GenderEventProvenance = GenderEventProvenance.USER_PROBE,
    ) -> GenderEvent:
        """Queue a validated event for the next update tick."""
        if self._profile is None:
            raise RuntimeError("no gender profile is installed")
        if request.target_id != self.agent_id:
            raise ValueError("gender event target does not match this engine")
        event = GenderEvent(
            **request.model_dump(),
            event_id=self._next_event_id,
            tick=self._last_tick + 1,
            provenance=provenance,
            processed=False,
        )
        self._next_event_id += 1
        self._pending_events.append(event)
        return event.model_copy(deep=True)

    def queue_intent(
        self,
        request: GenderIntentRequest,
        *,
        provenance: GenderEventProvenance = GenderEventProvenance.USER_PROBE,
    ) -> GenderIntent:
        """Queue a self-authored intent for the next update tick."""
        if self._profile is None:
            raise RuntimeError("no gender profile is installed")
        intent = GenderIntent(
            **request.model_dump(),
            intent_id=self._next_intent_id,
            tick=self._last_tick + 1,
            status=GenderIntentStatus.PENDING,
            provenance=provenance,
        )
        self._next_intent_id += 1
        self._pending_intents.append(intent)
        return intent.model_copy(deep=True)

    def update(
        self,
        tick: int,
        *,
        social_context: GenderSocialContext | None = None,
    ) -> GenderExperienceState | None:
        """Advance one tick transactionally; return ``None`` while feature-off."""
        if not self.active:
            return None
        if int(tick) <= self._last_tick:
            raise ValueError("gender experience ticks must increase monotonically")
        snapshot = copy.deepcopy(self.__dict__)
        try:
            if social_context is not None:
                self._social_context = social_context.model_copy(deep=True)
            result = self._update(int(tick))
            if self._checksum(self._profile) != self._profile_checksum:
                raise RuntimeError("private gender profile was mutated during update")
            return result.model_copy(deep=True)
        except Exception:
            self.__dict__.clear()
            self.__dict__.update(snapshot)
            raise

    def _update(self, tick: int) -> GenderExperienceState:
        assert self._profile is not None
        assert self._lifecycle is not None
        lifecycle = self._lifecycle.advance(target_id=self.agent_id)
        self._body_axes = {
            name: axes.model_copy(deep=True)
            for name, axes in lifecycle.body.items()
        }
        events: list[GenderEvent] = [
            self._record_request(
                request,
                tick=tick,
                provenance=GenderEventProvenance.LIFECYCLE,
            )
            for request in lifecycle.events
        ]
        due_events = [
            event for event in self._pending_events if event.tick <= tick
        ]
        self._pending_events = [
            event for event in self._pending_events if event.tick > tick
        ]
        for pending in due_events:
            processed = pending.model_copy(
                update={"tick": tick, "processed": True},
                deep=True,
            )
            self._append_ledger(processed)
            events.append(processed)

        due_intents = [
            intent for intent in self._pending_intents if intent.tick <= tick
        ]
        self._pending_intents = [
            intent for intent in self._pending_intents if intent.tick > tick
        ]

        affirmations = self._apply_events(events, tick)
        for intent in due_intents:
            self._current_intent = self._apply_intent(intent, tick)

        transition_events = self._progress_transitions(tick)
        events.extend(transition_events)
        affirmations.update(
            self._affirmation_by_domain(transition_events)
        )

        expression = self._update_expression(events)
        body, congruence = self._compute_congruence(expression)
        self._resilience = self._update_resilience(events)
        self._stress = self._update_stress(events, lifecycle.stage_index)
        affect = self._update_affect(congruence, affirmations)
        self._understanding = self._update_self_understanding(
            tick, events, affect
        )

        recent_ids = [event.event_id for event in events][-64:]
        labels = ", ".join(self._understanding.labels) or "no settled label"
        report = (
            f"Functional gender-life state at tick {tick}: {labels}; "
            f"congruence {congruence.total:.2f}, dysphoria {affect.dysphoria:.2f}, "
            f"euphoria {affect.euphoria:.2f}, fulfillment {affect.fulfillment:.2f}, "
            f"external stress {self._stress.external_current:.2f}, "
            f"internalized social pressure "
            f"{self._stress.internalized_transphobia:.2f}. "
            "Identity is not inferred from these values."
        )
        state = GenderExperienceState(
            agent_id=self.agent_id,
            profile_id=self._profile.profile_id,
            tick=tick,
            life_stage=lifecycle.stage,
            tick_in_stage=lifecycle.tick_in_stage,
            self_understanding=self._understanding.model_copy(deep=True),
            expression=expression,
            body=body,
            congruence=congruence,
            affect=affect,
            minority_stress=self._stress.model_copy(deep=True),
            resilience=self._resilience.model_copy(deep=True),
            transitions={
                dimension: transition.model_copy(deep=True)
                for dimension, transition in self._transitions.items()
            },
            current_intent=(
                self._current_intent.model_copy(deep=True)
                if self._current_intent is not None
                else None
            ),
            recent_event_ids=recent_ids,
            report=report,
        )
        self._last_tick = tick
        self._last_state = state
        return state

    def _record_request(
        self,
        request: GenderEventRequest,
        *,
        tick: int,
        provenance: GenderEventProvenance,
    ) -> GenderEvent:
        event = GenderEvent(
            **request.model_dump(),
            event_id=self._next_event_id,
            tick=tick,
            provenance=provenance,
            processed=True,
        )
        self._next_event_id += 1
        self._append_ledger(event)
        return event

    def _append_ledger(self, event: GenderEvent) -> None:
        self._event_ledger.append(event.model_copy(deep=True))
        memory_max = int(self.config.gender_event_memory_max)
        if len(self._event_ledger) > memory_max:
            self._event_ledger = self._event_ledger[-memory_max:]

    def _apply_events(
        self,
        events: list[GenderEvent],
        tick: int,
    ) -> dict[str, float]:
        affirmations = self._affirmation_by_domain(events)
        for event in events:
            intensity = float(event.intensity)
            if event.type in {
                GenderEventType.AFFIRMATION,
                GenderEventType.CORRECT_NAME_PRONOUN,
                GenderEventType.SUPPORT,
                GenderEventType.COMMUNITY_CONTACT,
            }:
                self._social_congruence = _clip01(
                    self._social_congruence + 0.16 * intensity
                )
            elif event.type is GenderEventType.LEGAL_RECOGNITION:
                self._administrative_congruence = _clip01(
                    self._administrative_congruence + 0.2 * intensity
                )
            elif event.type in _HOSTILE_EVENTS:
                self._social_congruence = _clip01(
                    self._social_congruence - 0.12 * intensity
                )

            dimension = self._dimension_from_domain(event.domain)
            if dimension is not None:
                current = self._transitions[dimension]
                if event.type is GenderEventType.ACCESS_GRANTED:
                    self._transitions[dimension] = current.model_copy(
                        update={"access": max(current.access, intensity)}
                    )
                elif event.type in {
                    GenderEventType.ACCESS_DENIED,
                    GenderEventType.CARE_BARRIER,
                }:
                    self._transitions[dimension] = current.model_copy(
                        update={
                            "access": min(current.access, 1.0 - intensity),
                            "status": TransitionStatus.BLOCKED,
                            "last_reason": event.context_code,
                            "last_change_tick": tick,
                        }
                    )
                    self._active_transitions.pop(dimension, None)
                elif event.type is GenderEventType.TRANSITION_PAUSED:
                    self._transitions[dimension] = current.model_copy(
                        update={
                            "status": TransitionStatus.PAUSED,
                            "last_reason": event.context_code,
                            "last_change_tick": tick,
                        }
                    )
                    self._active_transitions.pop(dimension, None)
                elif event.type is GenderEventType.TRANSITION_REVISED:
                    self._transitions[dimension] = current.model_copy(
                        update={
                            "status": TransitionStatus.REVISING,
                            "last_reason": event.context_code,
                            "last_change_tick": tick,
                        }
                    )
        return affirmations

    @staticmethod
    def _affirmation_by_domain(
        events: list[GenderEvent],
    ) -> dict[str, float]:
        affirmations: dict[str, float] = {}
        for event in events:
            if event.type in _AFFIRMING_EVENTS or event.type in {
                GenderEventType.TRANSITION_PROGRESS,
                GenderEventType.TRANSITION_COMPLETED,
            }:
                affirmations[event.domain] = max(
                    affirmations.get(event.domain, 0.0),
                    float(event.intensity),
                )
        return affirmations

    def _update_resilience(
        self, events: list[GenderEvent]
    ) -> GenderResilienceState:
        values = self._resilience.model_dump()
        for event in events:
            amount = 0.18 * float(event.intensity)
            if event.type is GenderEventType.SUPPORT:
                values["support"] = _clip01(values["support"] + amount)
            elif event.type is GenderEventType.COMMUNITY_CONTACT:
                values["community"] = _clip01(values["community"] + amount)
            elif event.type is GenderEventType.POSITIVE_REPRESENTATION:
                values["positive_representation"] = _clip01(
                    values["positive_representation"] + amount
                )
            elif event.type in {
                GenderEventType.AFFIRMATION,
                GenderEventType.CORRECT_NAME_PRONOUN,
                GenderEventType.LEGAL_RECOGNITION,
            }:
                values["self_acceptance"] = _clip01(
                    values["self_acceptance"] + 0.1 * float(event.intensity)
                )
                values["pride"] = _clip01(
                    values["pride"] + 0.06 * float(event.intensity)
                )
            elif event.type is GenderEventType.RECOVERY:
                values["self_acceptance"] = _clip01(
                    values["self_acceptance"] + amount
                )
        # Context makes resources available but does not force a person to use
        # them; therefore its contribution is a deliberately slow approach.
        values["community"] = _ema(
            values["community"],
            self._social_context.community_visibility,
            0.015,
        )
        values["positive_representation"] = _ema(
            values["positive_representation"],
            self._social_context.positive_representation,
            0.015,
        )
        return self._with_resilience_index(
            GenderResilienceState(**{
                key: value for key, value in values.items() if key != "index"
            })
        )

    @staticmethod
    def _with_resilience_index(
        resilience: GenderResilienceState,
    ) -> GenderResilienceState:
        index = _mean(
            [
                resilience.support,
                resilience.community,
                resilience.positive_representation,
                resilience.pride,
                resilience.self_acceptance,
            ]
        )
        return resilience.model_copy(update={"index": index})

    def _update_stress(
        self,
        events: list[GenderEvent],
        stage_index: int,
    ) -> GenderMinorityStressState:
        assert self._lifecycle is not None
        hostile = [
            float(event.intensity)
            for event in events
            if event.type in _HOSTILE_EVENTS
        ]
        stage = self._lifecycle.plan.stages[stage_index]
        institutional = (
            self._social_context.institutional_hostility
            * stage.norm_exposure
        )
        event_exposure = max(hostile, default=0.0)
        external_current = _clip01(
            event_exposure + 0.35 * institutional
        )
        external_chronic = _ema(
            self._stress.external_chronic,
            external_current,
            0.1,
        )
        cumulative = _clip01(
            0.995 * self._stress.cumulative_exposure
            + 0.05 * external_current
        )
        resilience_index = self._resilience.index
        gain = (
            self.config.gender_internalization_rate
            * external_current
            * (0.5 + 0.5 * self._social_context.norm_rigidity)
            * (1.0 - resilience_index)
        )
        recovery_input = _mean(
            [
                self._resilience.support,
                self._resilience.community,
                self._resilience.pride,
                self._resilience.self_acceptance,
            ]
        )
        recovery = self.config.gender_recovery_rate * recovery_input
        internalized = _clip01(
            self._stress.internalized_transphobia + gain - recovery
        )
        rejection = _ema(
            self._stress.rejection_expectation,
            max(external_current, external_chronic),
            0.12,
        )
        vigilance = _clip01(
            0.5 * external_current
            + 0.3 * external_chronic
            + 0.2 * rejection
        )
        concealment = _clip01(
            0.35 * external_current
            + 0.25 * external_chronic
            + 0.4 * internalized
        )
        return GenderMinorityStressState(
            external_current=external_current,
            external_chronic=external_chronic,
            rejection_expectation=rejection,
            concealment_pressure=concealment,
            vigilance=vigilance,
            internalized_transphobia=internalized,
            incident_count=self._stress.incident_count + len(hostile),
            cumulative_exposure=cumulative,
        )

    def _update_expression(
        self,
        events: list[GenderEvent],
    ) -> dict[str, ExpressionChannelState]:
        assert self._profile is not None
        affirming = any(event.type in _AFFIRMING_EVENTS for event in events)
        exploring = (
            self._current_intent is not None
            and self._current_intent.status is GenderIntentStatus.ACCEPTED
            and self._current_intent.type in {
                GenderIntentType.EXPLORE_IDENTITY,
                GenderIntentType.ADJUST_EXPRESSION,
            }
        )
        concealing = (
            self._current_intent is not None
            and self._current_intent.status is GenderIntentStatus.ACCEPTED
            and self._current_intent.type is GenderIntentType.CONCEAL
        )
        disclosing = (
            self._current_intent is not None
            and self._current_intent.status is GenderIntentStatus.ACCEPTED
            and self._current_intent.type is GenderIntentType.DISCLOSE
        )
        result: dict[str, ExpressionChannelState] = {}
        for channel, profile in self._profile.preferred_expression.items():
            contexts = self._expression_axes[channel]
            contexts["private"] = move_axes(
                contexts["private"], profile.desired, 0.22
            )
            trusted_access = _clip01(
                0.45 + 0.5 * self._social_context.baseline_safety
                - 0.25 * self._stress.concealment_pressure
            )
            trusted_target = _blend_axes(
                profile.trusted_baseline, profile.desired, trusted_access
            )
            contexts["trusted"] = move_axes(
                contexts["trusted"], trusted_target, 0.16
            )
            public_access = _clip01(
                self._social_context.baseline_safety
                * (1.0 - 0.65 * self._stress.external_current)
                * (1.0 - 0.45 * self._stress.internalized_transphobia)
            )
            if concealing:
                public_access = 0.0
            elif disclosing:
                public_access = max(public_access, 0.9)
            public_target = _blend_axes(
                profile.public_baseline, profile.desired, public_access
            )
            contexts["public"] = move_axes(
                contexts["public"], public_target, 0.14
            )

            baseline = self._rolling_expression_baseline[channel]
            accentuation = max(
                self._accentuation(context_axes, baseline)
                for context_axes in contexts.values()
            )
            drivers: list[ExpressionDriver] = []
            if accentuation > 0.0:
                if exploring:
                    drivers.append(ExpressionDriver.EXPLORATION)
                if affirming or self._last_euphoria() > 0.15:
                    drivers.append(ExpressionDriver.EUPHORIA)
                if disclosing or any(
                    event.type is GenderEventType.CORRECT_NAME_PRONOUN
                    for event in events
                ):
                    drivers.append(ExpressionDriver.RECOGNITION)
                if self._is_assigned_compensation(
                    contexts["public"], profile.desired
                ):
                    drivers.append(ExpressionDriver.ASSIGNED_COMPENSATION)
                if (
                    self._stress.internalized_transphobia > 0.2
                    or self._social_context.norm_rigidity > 0.72
                ):
                    drivers.append(ExpressionDriver.PROVING_PRESSURE)
                if public_access < 0.45 or concealing:
                    drivers.append(ExpressionDriver.SAFETY)
                if mean_axis_distance(profile.desired, baseline) > 0.18:
                    drivers.append(ExpressionDriver.AESTHETIC)

            # The rolling personal baseline changes slowly toward preference; it
            # is never a population norm and is not trained from observers.
            self._rolling_expression_baseline[channel] = move_axes(
                baseline, profile.desired, 0.01
            )
            result[channel] = ExpressionChannelState(
                channel=channel,
                desired=profile.desired.model_copy(deep=True),
                private=contexts["private"].model_copy(deep=True),
                trusted=contexts["trusted"].model_copy(deep=True),
                public=contexts["public"].model_copy(deep=True),
                visibility=public_access,
                safety_cost=1.0 - public_access,
                accentuation=accentuation,
                drivers=list(dict.fromkeys(drivers)),
            )
        return result

    @staticmethod
    def _accentuation(current: GenderAxes, baseline: GenderAxes) -> float:
        current_values = axes_values(current)
        baseline_values = axes_values(baseline)
        names = current_values.keys() | baseline_values.keys()
        if not names:
            return 0.0
        return _clip01(
            max(
                max(
                    0.0,
                    current_values.get(name, 0.0)
                    - baseline_values.get(name, 0.0)
                    - 0.1,
                )
                for name in names
            )
        )

    def _is_assigned_compensation(
        self,
        public: GenderAxes,
        desired: GenderAxes,
    ) -> bool:
        assert self._profile is not None
        assigned = self._profile.assigned_category.casefold()
        if any(token in assigned for token in ("female", "woman", "girl", "fem")):
            return (
                public.feminine > desired.feminine + 0.15
                and public.feminine > public.masculine
            )
        if any(token in assigned for token in ("male", "man", "boy", "masc")):
            return (
                public.masculine > desired.masculine + 0.15
                and public.masculine > public.feminine
            )
        return False

    def _compute_congruence(
        self,
        expression: dict[str, ExpressionChannelState],
    ) -> tuple[dict[str, BodyDomainState], GenderCongruenceState]:
        assert self._profile is not None
        body: dict[str, BodyDomainState] = {}
        by_domain: dict[str, float] = {}
        body_weights: list[tuple[float, float]] = []
        for name, preference in self._profile.body_preferences.items():
            current = self._body_axes.get(name, preference.initial)
            score = alignment(current, preference.preferred)
            body[name] = BodyDomainState(
                name=name,
                current=current.model_copy(deep=True),
                preferred=preference.preferred.model_copy(deep=True),
                salience=preference.salience,
                public_visibility=preference.public_visibility,
                alignment=score,
                change_rate=self._body_change_rate(name),
            )
            by_domain[f"body:{name}"] = score
            body_weights.append((score, preference.salience))
        body_score = self._weighted(body_weights, default=1.0)

        expression_weights: list[tuple[float, float]] = []
        for channel, state in expression.items():
            contextual = _mean(
                [
                    alignment(state.private, state.desired),
                    alignment(state.trusted, state.desired),
                    alignment(state.public, state.desired),
                ],
                default=1.0,
            )
            by_domain[f"expression:{channel}"] = contextual
            expression_weights.append(
                (
                    contextual,
                    self._profile.preferred_expression[channel].salience,
                )
            )
        expression_score = self._weighted(expression_weights, default=1.0)
        by_domain["social"] = self._social_congruence
        by_domain["administrative"] = self._administrative_congruence
        total = self._weighted(
            [
                (body_score, _mean(
                    preference.salience
                    for preference in self._profile.body_preferences.values()
                )),
                (expression_score, _mean(
                    channel.salience
                    for channel in self._profile.preferred_expression.values()
                )),
                (self._social_congruence, self._profile.gender_salience),
                (
                    self._administrative_congruence,
                    self._profile.transition_priorities.get(
                        TransitionDimension.ADMINISTRATIVE, 0.0
                    ),
                ),
            ],
            default=1.0,
        )
        return body, GenderCongruenceState(
            by_domain=by_domain,
            body=body_score,
            expression=expression_score,
            social=self._social_congruence,
            administrative=self._administrative_congruence,
            total=total,
        )

    @staticmethod
    def _weighted(
        values: list[tuple[float, float]],
        *,
        default: float,
    ) -> float:
        denominator = sum(max(0.0, float(weight)) for _, weight in values)
        if denominator <= 0.0:
            return float(default)
        return _clip01(
            sum(float(value) * max(0.0, float(weight))
                for value, weight in values)
            / denominator
        )

    def _body_change_rate(self, name: str) -> float:
        if self._last_state is None or name not in self._last_state.body:
            return 0.0
        previous = self._last_state.body[name].alignment
        current = alignment(
            self._body_axes[name],
            self._profile.body_preferences[name].preferred,  # type: ignore[union-attr]
        )
        return _clip(current - previous, -1.0, 1.0)

    def _update_affect(
        self,
        congruence: GenderCongruenceState,
        affirmations: dict[str, float],
    ) -> GenderAffectState:
        assert self._profile is not None
        contextual_pressure = max(
            self._stress.external_current,
            self._stress.external_chronic,
        )
        body_sensitivities = [
            preference.dysphoria_sensitivity
            for preference in self._profile.body_preferences.values()
        ]
        general_dysphoria_sensitivity = _mean(
            body_sensitivities, default=0.5
        )
        body_euphoria_sensitivities = [
            preference.euphoria_sensitivity
            for preference in self._profile.body_preferences.values()
        ]
        general_euphoria_sensitivity = _mean(
            body_euphoria_sensitivities, default=0.5
        )
        dysphoria: dict[str, float] = {}
        euphoria: dict[str, float] = {}
        weights: dict[str, float] = {}
        for domain, score in congruence.by_domain.items():
            sensitivity, euphoric_sensitivity, salience = (
                self._domain_sensitivities(
                    domain,
                    general_dysphoria_sensitivity,
                    general_euphoria_sensitivity,
                )
            )
            target_dysphoria = (
                sensitivity
                * salience
                * (1.0 - score)
                * (0.75 + 0.25 * contextual_pressure)
            )
            previous_dysphoria = self._dysphoria_by_domain.get(domain, 0.0)
            dysphoria[domain] = _ema(
                previous_dysphoria, target_dysphoria, 0.35
            )

            previous_alignment = self._previous_alignment.get(domain, score)
            positive_delta = max(0.0, score - previous_alignment)
            affirmation = max(
                affirmations.get(domain, 0.0),
                affirmations.get(domain.split(":", 1)[-1], 0.0),
                affirmations.get("general", 0.0),
            )
            target_euphoria = euphoric_sensitivity * _clip01(
                positive_delta + affirmation
            )
            previous_euphoria = self._euphoria_by_domain.get(domain, 0.0)
            euphoria[domain] = _clip01(
                0.45 * previous_euphoria + 0.55 * target_euphoria
            )
            weights[domain] = salience
            self._previous_alignment[domain] = score
        self._dysphoria_by_domain = dysphoria
        self._euphoria_by_domain = euphoria
        dysphoria_total = self._weighted(
            [(value, weights[name]) for name, value in dysphoria.items()],
            default=0.0,
        )
        euphoria_total = self._weighted(
            [(value, weights[name]) for name, value in euphoria.items()],
            default=0.0,
        )
        affirmation_level = max(affirmations.values(), default=0.0)
        fulfillment_target = _clip01(
            0.8 * congruence.total + 0.2 * affirmation_level
        )
        self._fulfillment = _ema(
            self._fulfillment, fulfillment_target, 0.08
        )
        affirming_ids = [
            event.event_id
            for event in self._event_ledger[-32:]
            if event.type in _AFFIRMING_EVENTS
        ][-32:]
        distressing_ids = [
            event.event_id
            for event in self._event_ledger[-32:]
            if event.type in _HOSTILE_EVENTS
        ][-32:]
        return GenderAffectState(
            dysphoria_by_domain=dysphoria,
            dysphoria=dysphoria_total,
            euphoria_by_domain=euphoria,
            euphoria=euphoria_total,
            fulfillment=self._fulfillment,
            last_affirming_event_ids=affirming_ids,
            last_distressing_event_ids=distressing_ids,
        )

    def _domain_sensitivities(
        self,
        domain: str,
        general_dysphoria: float,
        general_euphoria: float,
    ) -> tuple[float, float, float]:
        assert self._profile is not None
        if domain.startswith("body:"):
            preference = self._profile.body_preferences[domain.split(":", 1)[1]]
            return (
                preference.dysphoria_sensitivity,
                preference.euphoria_sensitivity,
                preference.salience,
            )
        if domain.startswith("expression:"):
            channel = domain.split(":", 1)[1]
            salience = self._profile.preferred_expression[channel].salience
            return general_dysphoria, general_euphoria, salience
        if domain == "social":
            return (
                general_dysphoria,
                general_euphoria,
                self._profile.gender_salience,
            )
        priority = self._profile.transition_priorities.get(
            TransitionDimension.ADMINISTRATIVE, 0.0
        )
        return general_dysphoria, general_euphoria, priority

    def _update_self_understanding(
        self,
        tick: int,
        events: list[GenderEvent],
        affect: GenderAffectState,
    ) -> GenderSelfUnderstanding:
        assert self._profile is not None
        state = self._understanding.model_copy(deep=True)
        known = list(state.known_vocabulary)
        for event in events:
            if event.type is GenderEventType.VOCABULARY_DISCOVERY:
                term = event.domain
                if (
                    term in self._profile.available_vocabulary
                    and term not in known
                ):
                    known.append(term)
        fit = dict(state.fit_by_label)
        affinities = self._active_affinities(tick)
        self_authored = [
            event for event in events
            if event.type in _SELF_AUTHORED_EVIDENCE_EVENTS
        ]
        exploring = (
            self._current_intent is not None
            and self._current_intent.status is GenderIntentStatus.ACCEPTED
            and self._current_intent.type
            in {GenderIntentType.EXPLORE_IDENTITY, GenderIntentType.ADJUST_EXPRESSION}
        )
        # Slow private self-observation supplies a small evidence rate.  It reads
        # the configured felt affinity and fulfilment only—never dysphoria,
        # expression, transition progress, or an observer's appraisal.
        evidence_rate = 0.015 * self._profile.gender_salience
        if self_authored or exploring:
            evidence_rate += 0.16
        for label in known:
            if label in affinities:
                target = _clip01(
                    0.8 * affinities[label] + 0.2 * affect.fulfillment
                )
                fit[label] = _ema(fit.get(label, 0.0), target, evidence_rate)
        labels = list(state.labels)
        explicit_revision = next(
            (
                event for event in reversed(events)
                if event.type is GenderEventType.LABEL_REVISION
            ),
            None,
        )
        if explicit_revision is not None and explicit_revision.domain in known:
            labels = [explicit_revision.domain]
        else:
            supported = [
                label for label in known
                if label in affinities
                and affinities[label] >= 0.6
                and fit.get(label, 0.0) >= 0.72
            ]
            if supported and (self_authored or exploring or not state.questioning):
                labels = supported[:4]
        fit_values = [fit[label] for label in labels if label in fit]
        certainty_target = _mean(fit_values, default=state.certainty)
        certainty = _ema(
            state.certainty,
            certainty_target,
            0.12 if (self_authored or exploring) else 0.025,
        )
        questioning = not labels or certainty < 0.52
        disclosure = copy.deepcopy(state.disclosure_scopes)
        if (
            self._current_intent is not None
            and self._current_intent.status is GenderIntentStatus.ACCEPTED
        ):
            scope = self._current_intent.disclosure_scope
            if self._current_intent.type is GenderIntentType.DISCLOSE and scope:
                disclosure[scope] = list(labels)
            elif self._current_intent.type is GenderIntentType.CONCEAL and scope:
                disclosure[scope] = []
        revised = labels != state.labels
        return GenderSelfUnderstanding(
            labels=labels,
            certainty=certainty,
            questioning=questioning,
            fit_by_label=fit,
            known_vocabulary=known,
            disclosure_scopes=disclosure,
            last_revision_tick=tick if revised else state.last_revision_tick,
        )

    def _active_affinities(self, tick: int) -> dict[str, float]:
        assert self._profile is not None
        for segment in self._profile.felt_timeline:
            if segment.start_tick <= tick < segment.end_tick:
                return dict(segment.affinities)
        return dict(self._profile.felt_affinities)

    def _apply_intent(self, intent: GenderIntent, tick: int) -> GenderIntent:
        assert self._profile is not None
        request_type = intent.type
        dimension = intent.transition_dimension or _INTENT_DIMENSIONS.get(
            request_type
        )
        if request_type in {
            GenderIntentType.PAUSE,
            GenderIntentType.REVISE_GOALS,
            GenderIntentType.REVERSE,
            GenderIntentType.RESUME,
        } and dimension is None:
            return intent.model_copy(
                update={
                    "status": GenderIntentStatus.REJECTED,
                    "reason": "a transition dimension is required",
                    "tick": tick,
                }
            )

        if dimension is not None:
            current = self._transitions[dimension]
            if request_type is GenderIntentType.PAUSE:
                self._active_transitions.pop(dimension, None)
                self._transitions[dimension] = current.model_copy(
                    update={
                        "status": TransitionStatus.PAUSED,
                        "last_reason": "self-authored pause",
                        "last_change_tick": tick,
                    }
                )
            elif request_type is GenderIntentType.REVISE_GOALS:
                self._active_transitions.pop(dimension, None)
                self._transitions[dimension] = current.model_copy(
                    update={
                        "status": TransitionStatus.REVISING,
                        "last_reason": "self-authored goal revision",
                        "last_change_tick": tick,
                    }
                )
            elif request_type is GenderIntentType.REVERSE:
                if current.progress <= 0.0:
                    return intent.model_copy(
                        update={
                            "status": GenderIntentStatus.REJECTED,
                            "reason": "there is no modeled progress to reverse",
                            "tick": tick,
                        }
                    )
                self._active_transitions[dimension] = -1
                self._transitions[dimension] = current.model_copy(
                    update={
                        "status": TransitionStatus.REVISING,
                        "last_reason": "self-authored reversal",
                        "last_change_tick": tick,
                    }
                )
            elif request_type is GenderIntentType.RESUME:
                self._active_transitions[dimension] = 1
                status = (
                    TransitionStatus.UNDERWAY
                    if current.access > 0.0
                    else TransitionStatus.BLOCKED
                )
                self._transitions[dimension] = current.model_copy(
                    update={
                        "status": status,
                        "last_reason": "self-authored resumption",
                        "last_change_tick": tick,
                    }
                )
            else:
                desire = max(current.desire, intent.urgency)
                access = self._dimension_access(dimension)
                status = (
                    TransitionStatus.UNDERWAY
                    if access > 0.0
                    else TransitionStatus.BLOCKED
                )
                self._transitions[dimension] = current.model_copy(
                    update={
                        "desire": desire,
                        "access": access,
                        "status": status,
                        "last_reason": (
                            "explicit self-authored intent"
                            if access > 0.0
                            else "configured access unavailable"
                        ),
                        "last_change_tick": tick,
                    }
                )
                if access > 0.0:
                    self._active_transitions[dimension] = 1
        return intent.model_copy(
            update={
                "status": GenderIntentStatus.ACCEPTED,
                "reason": "processed as an explicit self-authored intent",
                "tick": tick,
            }
        )

    def _progress_transitions(self, tick: int) -> list[GenderEvent]:
        assert self._profile is not None
        generated: list[GenderEvent] = []
        for dimension in list(self._active_transitions):
            direction = self._active_transitions[dimension]
            current = self._transitions[dimension]
            access = self._dimension_access(dimension)
            if access <= 0.0:
                self._transitions[dimension] = current.model_copy(
                    update={
                        "access": 0.0,
                        "status": TransitionStatus.BLOCKED,
                        "last_reason": "configured access unavailable",
                        "last_change_tick": tick,
                    }
                )
                self._active_transitions.pop(dimension, None)
                continue
            delta = _TRANSITION_RATES[dimension] * access * direction
            new_progress = _clip01(current.progress + delta)
            actual_delta = new_progress - current.progress
            before_alignment = self._transition_alignment(dimension)
            self._apply_transition_body_effect(dimension, actual_delta)
            after_alignment = self._transition_alignment(dimension)
            satisfaction = _clip(
                current.satisfaction + 2.0 * (after_alignment - before_alignment),
                -1.0,
                1.0,
            )
            status = (
                TransitionStatus.REVISING
                if direction < 0
                else TransitionStatus.UNDERWAY
            )
            completed_type = GenderEventType.TRANSITION_PROGRESS
            if direction > 0 and new_progress >= 1.0:
                status = TransitionStatus.COMPLETED
                completed_type = GenderEventType.TRANSITION_COMPLETED
                self._active_transitions.pop(dimension, None)
            elif direction < 0 and new_progress <= 0.0:
                status = TransitionStatus.PAUSED
                self._active_transitions.pop(dimension, None)
            self._transitions[dimension] = current.model_copy(
                update={
                    "access": access,
                    "progress": new_progress,
                    "satisfaction": satisfaction,
                    "status": status,
                    "last_reason": (
                        "modeled reversal progress"
                        if direction < 0
                        else "modeled intent progress"
                    ),
                    "last_change_tick": tick,
                }
            )
            if abs(actual_delta) > 0.0:
                generated.append(
                    self._record_request(
                        GenderEventRequest(
                            target_id=self.agent_id,
                            type=completed_type,
                            domain=dimension.value,
                            intensity=_clip01(abs(actual_delta) * 5.0),
                            context_code=(
                                "self_authored_reversal"
                                if direction < 0
                                else "self_authored_transition"
                            ),
                        ),
                        tick=tick,
                        provenance=GenderEventProvenance.SYSTEM,
                    )
                )
        return generated

    def _apply_transition_body_effect(
        self,
        dimension: TransitionDimension,
        progress_delta: float,
    ) -> None:
        assert self._profile is not None
        assert self._lifecycle is not None
        if dimension in {
            TransitionDimension.SOCIAL,
            TransitionDimension.ADMINISTRATIVE,
        }:
            if dimension is TransitionDimension.SOCIAL:
                self._social_congruence = _clip01(
                    self._social_congruence + progress_delta
                )
            else:
                self._administrative_congruence = _clip01(
                    self._administrative_congruence + progress_delta
                )
            return
        if dimension is TransitionDimension.VOICE:
            domains = ["voice"]
        elif dimension is TransitionDimension.HORMONAL:
            domains = [
                name for name in self._profile.body_preferences
                if name in {
                    "voice", "face_hair", "body_shape", "general_embodiment"
                }
            ]
        else:
            domains = [
                name for name in self._profile.body_preferences
                if name in {"chest", "primary_reproductive", "general_embodiment"}
            ]
        for name in domains:
            preference = self._profile.body_preferences[name]
            current = self._body_axes.get(name, preference.initial)
            if progress_delta >= 0.0:
                updated = move_axes(
                    current,
                    preference.preferred,
                    _clip01(abs(progress_delta) * 2.0),
                )
            else:
                updated = move_axes(
                    current,
                    preference.initial,
                    _clip01(abs(progress_delta) * 2.0),
                )
            self._body_axes[name] = updated
            self._lifecycle.replace_body(name, updated)

    def _transition_alignment(self, dimension: TransitionDimension) -> float:
        assert self._profile is not None
        if dimension is TransitionDimension.SOCIAL:
            return self._social_congruence
        if dimension is TransitionDimension.ADMINISTRATIVE:
            return self._administrative_congruence
        if dimension is TransitionDimension.VOICE:
            domains = ["voice"]
        elif dimension is TransitionDimension.HORMONAL:
            domains = ["face_hair", "body_shape", "general_embodiment"]
        else:
            domains = ["chest", "primary_reproductive", "general_embodiment"]
        scores = [
            alignment(
                self._body_axes.get(name, preference.initial),
                preference.preferred,
            )
            for name, preference in self._profile.body_preferences.items()
            if name in domains
        ]
        return _mean(scores, default=1.0)

    def _initial_transition_states(
        self,
    ) -> dict[TransitionDimension, TransitionDimensionState]:
        assert self._profile is not None
        states: dict[TransitionDimension, TransitionDimensionState] = {}
        for dimension in TransitionDimension:
            desire = self._profile.transition_priorities.get(dimension, 0.0)
            if desire <= 0.0:
                status = TransitionStatus.NOT_DESIRED
            elif desire < 0.6:
                status = TransitionStatus.CONSIDERING
            else:
                status = TransitionStatus.DESIRED
            if dimension in {
                TransitionDimension.SOCIAL,
                TransitionDimension.ADMINISTRATIVE,
            }:
                reversibility = TransitionReversibility.FULLY
            elif dimension in {
                TransitionDimension.VOICE,
                TransitionDimension.HORMONAL,
            }:
                reversibility = TransitionReversibility.PARTLY
            else:
                reversibility = TransitionReversibility.NOT_MODELED
            states[dimension] = TransitionDimensionState(
                dimension=dimension,
                desire=desire,
                status=status,
                access=self._dimension_access(dimension),
                progress=0.0,
                reversibility=reversibility,
                target_domains=self._target_domains(dimension),
            )
        return states

    def _dimension_access(self, dimension: TransitionDimension) -> float:
        if self._lifecycle is None:
            return 0.0
        stage = self._lifecycle.stage
        if dimension is TransitionDimension.SOCIAL:
            return _clip01(
                stage.autonomy * self._social_context.baseline_safety
            )
        if dimension is TransitionDimension.ADMINISTRATIVE:
            return _clip01(stage.autonomy * stage.resource_access)
        return _clip01(
            stage.autonomy
            * stage.resource_access
            * self._social_context.care_access
            * (1.0 - self._social_context.institutional_hostility)
        )

    def _target_domains(
        self,
        dimension: TransitionDimension,
    ) -> list[str]:
        assert self._profile is not None
        if dimension is TransitionDimension.SOCIAL:
            return list(self._profile.preferred_expression)
        if dimension is TransitionDimension.ADMINISTRATIVE:
            return ["name", "administrative_marker"]
        if dimension is TransitionDimension.VOICE:
            return ["voice"] if "voice" in self._profile.body_preferences else []
        if dimension is TransitionDimension.HORMONAL:
            allowed = {"voice", "face_hair", "body_shape", "general_embodiment"}
        else:
            allowed = {"chest", "primary_reproductive", "general_embodiment"}
        return [
            name for name in self._profile.body_preferences if name in allowed
        ]

    @staticmethod
    def _dimension_from_domain(
        domain: str,
    ) -> TransitionDimension | None:
        try:
            return TransitionDimension(domain)
        except ValueError:
            return None

    def influence(self) -> GenderInfluence:
        """Return bounded cognitive deltas without changing identity or action."""
        if not self.active or self._last_state is None:
            return GenderInfluence()
        state = self._last_state
        weight = float(self.config.gender_affect_weight)
        mood_signal = (
            state.affect.euphoria
            + 0.5 * state.affect.fulfillment
            - state.affect.dysphoria
            - 0.7 * state.minority_stress.external_current
            - 0.4 * state.minority_stress.internalized_transphobia
        )
        confidence_signal = (
            0.5 * state.resilience.support
            + 0.5 * state.resilience.self_acceptance
            - state.minority_stress.rejection_expectation
            - state.minority_stress.internalized_transphobia
        )
        coherence_signal = (
            state.affect.fulfillment
            + state.resilience.self_acceptance
            - state.minority_stress.internalized_transphobia
        )
        intent_urgency = (
            state.current_intent.urgency
            if state.current_intent is not None
            and state.current_intent.status is GenderIntentStatus.ACCEPTED
            else 0.0
        )
        activation = _clip01(
            max(
                state.affect.dysphoria,
                state.affect.euphoria,
                state.minority_stress.external_current,
                intent_urgency,
            )
            * self._profile.gender_salience  # type: ignore[union-attr]
        )
        goals = {
            "seek_safety": _clip01(
                state.minority_stress.vigilance
                * self.config.gender_motivation_weight
            ),
            "explore_gender": _clip01(
                (1.0 - state.self_understanding.certainty)
                * self._profile.gender_salience  # type: ignore[union-attr]
                * self.config.gender_motivation_weight
            ),
            "seek_affirmation": _clip01(
                (1.0 - state.congruence.social)
                * self.config.gender_motivation_weight
            ),
            "pursue_transition_intent": _clip01(
                intent_urgency * self.config.gender_motivation_weight
            ),
        }
        content = (
            f"gender experience: dysphoria={state.affect.dysphoria:.2f}, "
            f"euphoria={state.affect.euphoria:.2f}, "
            f"stress={state.minority_stress.external_current:.2f}, "
            f"intent={intent_urgency:.2f}"
        )
        return GenderInfluence(
            mood_delta=_clip(weight * mood_signal, -0.08, 0.08),
            confidence_delta=_clip(weight * confidence_signal, -0.05, 0.05),
            coherence_delta=_clip(weight * coherence_signal, -0.03, 0.03),
            goal_pressures=goals,
            activation=activation,
            content=content,
        )

    def debug_state(self) -> GenderDebugState:
        if self._profile is None or self._life_course_plan is None:
            raise RuntimeError("no gender profile is installed")
        if self._last_state is None:
            raise RuntimeError("gender experience has not advanced yet")
        return GenderDebugState(
            profile=self._profile.model_copy(deep=True),
            life_course=self._life_course_plan.model_copy(deep=True),
            state=self._last_state.model_copy(deep=True),
            pending_events=self.pending_events,
            event_ledger_size=len(self._event_ledger),
            profile_checksum=self._profile_checksum,
        )

    def _last_euphoria(self) -> float:
        return (
            self._last_state.affect.euphoria
            if self._last_state is not None
            else 0.0
        )

    @staticmethod
    def _checksum(profile: GenderProfile | None) -> str:
        if profile is None:
            return ""
        canonical = json.dumps(
            profile.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(canonical).hexdigest()

