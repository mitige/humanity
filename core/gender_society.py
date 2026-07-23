"""Privacy-preserving, one-tick-deferred Phase-8 social dynamics."""
from __future__ import annotations

from hashlib import blake2b

from schemas.models import (
    GenderEventProvenance,
    GenderEventRequest,
    GenderEventType,
    GenderExperienceState,
    GenderObserverDisposition,
    GenderRecognitionState,
    GenderSocialContext,
    GenderSocietyState,
    PublicGenderProjection,
    SimConfig,
)


_HOSTILE_OUTPUTS = {
    GenderEventType.MISGENDERING,
    GenderEventType.INVALIDATION,
    GenderEventType.REJECTION,
    GenderEventType.DISCRIMINATION,
    GenderEventType.THREAT,
    GenderEventType.CARE_BARRIER,
    GenderEventType.ACCESS_DENIED,
}


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _stable_unit(seed: int, tick: int, observer_id: int, target_id: int,
                 channel: str) -> float:
    payload = (
        f"{int(seed)}:{int(tick)}:{int(observer_id)}:{int(target_id)}:{channel}"
    ).encode("utf-8")
    digest = blake2b(payload, digest_size=8, person=b"humanity").digest()
    return int.from_bytes(digest, "big") / float(2**64 - 1)


def build_public_gender_projection(
    state: GenderExperienceState,
) -> PublicGenderProjection:
    """Project only deliberately disclosed fields and public expression.

    The function has no profile argument by design, making latent-affinity and
    body-goal leakage structurally impossible at this boundary.
    """
    disclosure = state.self_understanding.disclosure_scopes
    labels = list(disclosure.get("public", []))
    pronouns = list(disclosure.get("public:pronouns", []))
    names = disclosure.get("public:name", [])
    return PublicGenderProjection(
        agent_id=state.agent_id,
        labels=labels,
        pronouns=pronouns,
        name=names[0] if names else None,
        expression={
            channel: channel_state.public.model_copy(deep=True)
            for channel, channel_state in state.expression.items()
        },
        disclosure_scope="public",
        updated_tick=state.tick,
    )


class GenderSociety:
    """Observer-local recognition and deferred, template-only social events."""

    def __init__(
        self,
        config: SimConfig,
        *,
        context: GenderSocialContext | None = None,
        seed: int | None = None,
        dispositions: dict[int, GenderObserverDisposition] | None = None,
    ) -> None:
        self.config = config
        self.context = (
            context or GenderSocialContext()
        ).model_copy(deep=True)
        self.seed = int(config.random_seed if seed is None else seed)
        self.dispositions = {
            int(agent_id): disposition.model_copy(deep=True)
            for agent_id, disposition in (dispositions or {}).items()
        }
        self.projections: dict[int, PublicGenderProjection] = {}
        self.recognition: dict[
            tuple[int, int], GenderRecognitionState
        ] = {}
        self._pending: list[GenderEventRequest] = []
        self.event_counts: dict[str, int] = {}

    @property
    def pending_events(self) -> list[GenderEventRequest]:
        return [event.model_copy(deep=True) for event in self._pending]

    def clear_pending(self) -> None:
        self._pending = []

    def deliver_pending(self, agents: dict[int, object]) -> int:
        """Queue last tick's social outcomes on their target engines."""
        pending, self._pending = self._pending, []
        delivered = 0
        for request in pending:
            target = agents.get(request.target_id)
            if target is None:
                continue
            # CognitiveAgent is intentionally duck-typed here to avoid a circular
            # import through core.agent -> this module.
            if getattr(target, "gender_experience").active:
                target.queue_gender_event(
                    request,
                    provenance=GenderEventProvenance.SOCIETY,
                )
                delivered += 1
        return delivered

    def after_tick(
        self,
        agents: dict[int, object],
        *,
        tick: int,
    ) -> list[GenderEventRequest]:
        """Snapshot public state, update observers, and stage next-tick events."""
        projections: dict[int, PublicGenderProjection] = {}
        for target_id, agent in sorted(agents.items()):
            state = agent.gender_state()
            if state is not None:
                projections[target_id] = build_public_gender_projection(state)
        self.projections = projections

        visible_pairs: list[tuple[int, int]] = []
        for observer_id, observer in sorted(agents.items()):
            visible_ids = sorted({
                int(view.id) for view in observer._last_visible_agents
            })
            for target_id in visible_ids:
                if (
                    observer_id != target_id
                    and target_id in projections
                ):
                    visible_pairs.append((observer_id, target_id))

        generated: list[GenderEventRequest] = []
        for observer_id, target_id in sorted(set(visible_pairs)):
            projection = projections[target_id]
            prior = self.recognition.get((observer_id, target_id))
            disposition = self.dispositions.get(
                observer_id, GenderObserverDisposition()
            )
            relationship_trust = self._relationship_trust(
                agents[observer_id], target_id
            )
            generated.extend(
                self._events_for_pair(
                    tick=tick,
                    observer_id=observer_id,
                    target_id=target_id,
                    projection=projection,
                    prior=prior,
                    disposition=disposition,
                    relationship_trust=relationship_trust,
                )
            )
            self.recognition[(observer_id, target_id)] = (
                self._updated_recognition(
                    tick=tick,
                    observer_id=observer_id,
                    target_id=target_id,
                    projection=projection,
                    prior=prior,
                    disposition=disposition,
                    relationship_trust=relationship_trust,
                )
            )

        if not self.context.hostility_enabled:
            generated = [
                event for event in generated
                if event.type not in _HOSTILE_OUTPUTS
            ]
        self._pending.extend(
            event.model_copy(deep=True) for event in generated
        )
        for event in generated:
            key = event.type.value
            self.event_counts[key] = self.event_counts.get(key, 0) + 1
        return [event.model_copy(deep=True) for event in generated]

    @staticmethod
    def _relationship_trust(observer, target_id: int) -> float:
        model = observer.theory_of_mind.model_of(target_id)
        return _clip01(float(model.trust))

    def _events_for_pair(
        self,
        *,
        tick: int,
        observer_id: int,
        target_id: int,
        projection: PublicGenderProjection,
        prior: GenderRecognitionState | None,
        disposition: GenderObserverDisposition,
        relationship_trust: float,
    ) -> list[GenderEventRequest]:
        outputs: list[GenderEventRequest] = []
        has_disclosure = bool(
            projection.labels or projection.pronouns or projection.name
        )
        has_public_expression = bool(projection.expression)
        if not has_disclosure and not has_public_expression:
            return outputs

        previously_known_pronouns = set(
            prior.known_pronouns if prior is not None else []
        )
        current_pronouns = set(projection.pronouns)
        knowledge_gap = bool(
            current_pronouns and current_pronouns != previously_known_pronouns
        )
        bias = float(disposition.learned_bias)
        respect = float(disposition.respect_propensity)
        hostility_probability = _clip01(
            0.45 * bias
            + 0.25 * (1.0 - respect)
            + 0.20 * self.context.norm_rigidity
            + 0.10 * self.context.institutional_hostility
        )
        hostility_draw = _stable_unit(
            self.seed, tick, observer_id, target_id, "hostility"
        )

        if (
            self.context.hostility_enabled
            and hostility_draw < hostility_probability
        ):
            deliberate = bool(bias >= 0.6 or respect <= 0.3)
            if knowledge_gap and not deliberate:
                event_type = GenderEventType.MISGENDERING
                context_code = "recognition_knowledge_gap"
            elif deliberate:
                event_type = GenderEventType.INVALIDATION
                context_code = "configured_observer_bias"
            else:
                event_type = GenderEventType.REJECTION
                context_code = "configured_social_rejection"
            outputs.append(
                GenderEventRequest(
                    target_id=target_id,
                    actor_id=observer_id,
                    type=event_type,
                    domain=(
                        "pronouns"
                        if current_pronouns
                        else "public_recognition"
                    ),
                    intensity=_clip01(
                        0.3 + 0.4 * hostility_probability
                    ),
                    visibility="public",
                    deliberate=deliberate,
                    context_code=context_code,
                )
            )
        else:
            affirmation_probability = _clip01(
                disposition.affirmation_tendency
                * respect
                * (0.5 + 0.5 * relationship_trust)
                * (1.0 - 0.5 * bias)
            )
            affirmation_draw = _stable_unit(
                self.seed, tick, observer_id, target_id, "affirmation"
            )
            if has_disclosure and affirmation_draw < affirmation_probability:
                outputs.append(
                    GenderEventRequest(
                        target_id=target_id,
                        actor_id=observer_id,
                        type=(
                            GenderEventType.CORRECT_NAME_PRONOUN
                            if projection.pronouns or projection.name
                            else GenderEventType.AFFIRMATION
                        ),
                        domain=(
                            "pronouns"
                            if projection.pronouns
                            else "public_recognition"
                        ),
                        intensity=_clip01(
                            0.35 + 0.4 * affirmation_probability
                        ),
                        visibility="public",
                        context_code="public_disclosure_respected",
                    )
                )

        support_probability = _clip01(
            self.context.community_visibility
            * disposition.affirmation_tendency
            * relationship_trust
            * 0.35
        )
        if (
            has_disclosure
            and _stable_unit(
                self.seed, tick, observer_id, target_id, "support"
            ) < support_probability
        ):
            outputs.append(
                GenderEventRequest(
                    target_id=target_id,
                    actor_id=observer_id,
                    type=GenderEventType.SUPPORT,
                    domain="social",
                    intensity=_clip01(0.3 + support_probability),
                    visibility="trusted",
                    context_code="configured_interpersonal_support",
                )
            )
        return outputs

    @staticmethod
    def _updated_recognition(
        *,
        tick: int,
        observer_id: int,
        target_id: int,
        projection: PublicGenderProjection,
        prior: GenderRecognitionState | None,
        disposition: GenderObserverDisposition,
        relationship_trust: float,
    ) -> GenderRecognitionState:
        previous_confidence = (
            prior.knowledge_confidence if prior is not None else 0.0
        )
        disclosure_present = bool(
            projection.labels or projection.pronouns or projection.name
        )
        target_confidence = 1.0 if disclosure_present else 0.0
        confidence = _clip01(
            previous_confidence
            + 0.45 * (target_confidence - previous_confidence)
        )
        return GenderRecognitionState(
            observer_id=observer_id,
            target_id=target_id,
            known_labels=list(projection.labels),
            known_pronouns=list(projection.pronouns),
            respect_propensity=disposition.respect_propensity,
            learned_bias=disposition.learned_bias,
            relationship_trust=relationship_trust,
            knowledge_confidence=confidence,
            last_update_tick=tick,
        )

    def state(self) -> GenderSocietyState:
        return GenderSocietyState(
            projections={
                agent_id: projection.model_copy(deep=True)
                for agent_id, projection in self.projections.items()
            },
            recognition=[
                state.model_copy(deep=True)
                for _, state in sorted(self.recognition.items())
            ],
            social_context=self.context.model_copy(deep=True),
            event_counts=dict(self.event_counts),
        )
