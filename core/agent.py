"""Orchestration layer: CognitiveAgent, SimulationManager and the singleton.

FUNCTIONAL NOTE
---------------
:class:`CognitiveAgent` wires together the already-implemented core modules into
a single cognitive cycle: perception -> attention -> working memory -> world
model prediction -> episodic retrieval -> policy -> world step -> error and
emotion update -> motivation -> self-model update -> introspection -> metrics ->
trace logging. Every stage operates on internal numeric variables. This is a
FUNCTIONAL simulation of processes associated with consciousness; the agent is
not conscious, sentient, or alive, and the introspective text it emits is
generated from those variables, not from any subjective experience.
"""
from __future__ import annotations

import asyncio
from collections import deque

from core.attention import Attention
from core.constants import (
    AROUSAL_CEIL,
    AROUSAL_EMA,
    AROUSAL_FLOOR,
    ENERGY_CAP_FACTOR,
)
from core.attention_schema import AttentionSchema
from core.autobiographical_memory import AutobiographicalMemory
from core.communication import build_message_content, message_coalition
from core.dialogue import IntrospectiveDialogue
from core.emotion import EmotionModel
from core.global_workspace import GlobalWorkspace
from core.integration import IntegrationMonitor
from core.introspection import DISCLAIMER_EN, Introspection
from core.metacognition import Metacognition
from core.motivation import MotivationSystem
from core.perception import Perception
from core.policy import Policy
from core.self_model import SelfModel
from core.shared_world import SharedWorld
from core.social_emotion import apply_contagion, update_trust
from core.theory_of_mind import TheoryOfMind
from core.working_memory import WorkingMemory
from core.world import World
from core.world_model import WorldModel
from schemas.models import (
    ActionDecision,
    ActionType,
    AgentView,
    AskResponse,
    AttendRequest,
    AttentionSchemaState,
    Coalition,
    CognitiveInjection,
    ConfigPatch,
    ConsciousMoment,
    CycleTrace,
    EmotionState,
    IntegrationState,
    IntrospectionReport,
    MemoryRecord,
    MetacognitiveState,
    Metrics,
    Percept,
    PerturbRequest,
    Prediction,
    RunRequest,
    SalientItem,
    SelfModelState,
    SimConfig,
    SocialState,
    WorldObject,
    WorldStimulus,
    WorkspaceState,
)
from storage.persistence import MemoryStore
from storage.trace_logger import TraceLogger


class CognitiveAgent:
    """A single simulated agent running a full cognitive cycle per tick."""

    def __init__(self, config: SimConfig, *, agent_id: int = 0,
                 shared_world: "SharedWorld | None" = None) -> None:
        """Instantiate the world and every cognitive module from ``config``."""
        self.config = config
        self.agent_id = int(agent_id)
        self._shared_world = shared_world
        self._build(config)

    def _build(self, config: SimConfig, *, preserve_identity: bool = False) -> None:
        """(Re)create all sub-systems. Optionally keep the persistent stores."""
        self.config = config
        self.world = World(config)
        self.world_model = WorldModel(config)
        self.perception = Perception()
        self.attention = Attention()
        self.working_memory = WorkingMemory(config)
        # Persistence + episodic memory.
        if not preserve_identity or not hasattr(self, "memory_store"):
            self.memory_store = MemoryStore()
        self.memory = AutobiographicalMemory(config, store=self.memory_store)
        self.emotion_model = EmotionModel()
        self.motivation = MotivationSystem(config)
        self.self_model = SelfModel(config)
        self.policy = Policy()
        self.introspection = Introspection()
        # v2 consciousness-architecture mechanisms.
        self.global_workspace = GlobalWorkspace(config)
        self.integration_monitor = IntegrationMonitor()
        self.attention_schema = AttentionSchema()
        self.metacognition = Metacognition()
        if not preserve_identity or not hasattr(self, "trace_logger"):
            self.trace_logger = TraceLogger()

        # Cycle bookkeeping.
        self.last_trace: CycleTrace | None = None
        self.last_emotion: EmotionState = EmotionState()
        self.last_prediction_error: float = 0.0
        self._prev_prediction_error: float = 0.0
        self._last_metrics: Metrics | None = None
        self._last_introspection: IntrospectionReport | None = None

        # v2 rolling buffers for the global-workspace / consciousness pipeline.
        self._recent_winners: deque[str] = deque(maxlen=max(1, int(config.stream_length)))
        self._recent_errors: deque[float] = deque(maxlen=max(1, int(config.stream_length)))
        self._stream: deque[ConsciousMoment] = deque(maxlen=max(1, int(config.stream_length)))
        # Previous metacognitive state (used to build the metacognition coalition).
        self._last_metacognition: MetacognitiveState | None = None
        self._last_workspace: WorkspaceState | None = None

        # Global arousal / vigilance (v2.1): modulates ignition. Starts at the
        # configured baseline; rises with danger/novelty/surprise, decays back.
        self._arousal: float = float(config.arousal_baseline)
        # Source broadcast last tick *if it ignited* — sustains a train of thought.
        self._last_ignited_source: str | None = None

        # Interaction buffers (additive). These default empty so the cognitive
        # cycle hooks that read them are no-ops until an interaction is issued,
        # leaving the default behaviour (and the existing tests) unchanged.
        self._pending_injections: list[CognitiveInjection] = []
        self._attend_bias: AttendRequest | None = None
        self._pending_surprise: float = 0.0
        self._dialogue = IntrospectiveDialogue()

        # Society layer (active only when a shared world is attached).
        self.theory_of_mind = TheoryOfMind()
        self._last_social: SocialState | None = None
        self._last_visible_agents: list[AgentView] = []
        self._last_audible_messages: list = []

    # ------------------------------------------------------------------ #
    # The cognitive cycle
    # ------------------------------------------------------------------ #
    def cognitive_cycle(self) -> CycleTrace:
        """Run one full cycle and return a fully-populated CycleTrace.

        The stages run in the documented order; every sub-object of the trace is
        produced from the live internal variables of this tick.
        """
        cfg = self.config

        # 1) Observe — from the shared world when in a society, else the solo world.
        if self._shared_world is not None:
            observation = self._shared_world.observe(self.agent_id)
        else:
            observation = self.world.observe()
        visible_agents = list(observation.visible_agents)
        audible_messages = list(observation.audible_messages)
        self._last_visible_agents = visible_agents
        self._last_audible_messages = audible_messages

        # 2) Perceive: encode raw observation into relative percepts.
        seen_counts = self._shared_world.seen_counts if self._shared_world is not None else self.world.seen_counts
        percepts: list[Percept] = self.perception.encode(observation, seen_counts)

        # 3) Motivation needs the *previous* self-model / emotion / error.
        self_state: SelfModelState = self.self_model.snapshot()
        prev_error = self.last_prediction_error
        uncertainty = float(self.world_model.current_uncertainty)
        goals = self.motivation.evaluate(
            self_state,
            self.last_emotion,
            percepts,
            prev_error,
            uncertainty,
            cfg,
            n_visible_agents=len(visible_agents),
            society_size=(len(self._shared_world.agents) if self._shared_world is not None else 1),
        )

        # 4) Attention: select salient items under the capacity bottleneck.
        salient: list[SalientItem] = self.attention.select(
            percepts, goals, prev_error, self.last_emotion, cfg
        )

        # 4b) HOOK (top-down attention steering, AST): if an attend-bias is
        #     pending and its target is currently salient, boost that item's
        #     saliency so its perception coalition rises. No-op when no bias is
        #     set, so default behaviour is unchanged.
        salient = self._apply_attend_bias(salient)

        # 5) Working memory: refresh/expire/evict.
        self.working_memory.update(salient, observation.tick)

        # 6) Episodic retrieval: similar past records.
        memory_matches: list[MemoryRecord] = self.memory.retrieve_similar(
            percepts, cfg.memory_retrieval_k
        )

        # 7) Candidate actions + predictions.
        candidates = self.policy.candidate_actions(salient, self_state)
        predictions: list[Prediction] = self.world_model.predict_all(
            observation, candidates
        )

        # Theory of mind: refresh models of visible others + their messages.
        if self._shared_world is not None:
            self.theory_of_mind.update(visible_agents, audible_messages,
                                       tick=observation.tick, grid_size=cfg.grid_size)

        # 6b) BUILD COALITIONS: each specialist process submits a bid for the
        #     single global-workspace broadcast channel (GWT). Bids carry an
        #     activation (raw strength), a precision (confidence weight) and a
        #     small feature vector used by the Phi-proxy.
        coalitions = self._build_coalitions(
            percepts=percepts,
            salient=salient,
            goals=goals,
            memory_matches=memory_matches,
            prev_error=prev_error,
            uncertainty=uncertainty,
            self_state=self_state,
            emotion=self.last_emotion,
            cfg=cfg,
        )

        # 6c) HOOK (cognitive injection): append one coalition per active
        #     injection so it competes in the next workspace round (tests the
        #     ignition threshold: subliminal vs conscious). No-op when the
        #     injection buffer is empty.
        coalitions.extend(self._injection_coalitions())

        # 6d) AROUSAL / vigilance (v2.1): a global gain that gates ignition.
        #     Salient drivers (danger, novelty in view, recent surprise/error, a
        #     queued surprise perturbation) raise it; otherwise it decays toward
        #     the configured baseline. High arousal makes conscious access easier,
        #     so stimuli / perturbations can push content over the ignition line.
        arousal = self._update_arousal(percepts, prev_error, cfg)

        # 7) Global workspace competition + broadcast (GWT ignition), modulated
        #    by arousal and sustained by the previously-ignited content.
        workspace = self.global_workspace.compete(
            coalitions,
            cfg,
            arousal=arousal,
            maintenance_source=self._last_ignited_source,
        )
        if workspace.winner_source is not None:
            self._recent_winners.append(workspace.winner_source)
        # Sustain an ignited winner into the next tick (hysteresis); clear it
        # otherwise so subliminal content does not get an unfair maintenance boost.
        self._last_ignited_source = workspace.winner_source if workspace.ignited else None

        # 8a) Attention schema (AST): the system's model of its own attention.
        attention_schema = self.attention_schema.update(
            workspace, list(self._recent_winners), cfg
        )

        # 8b) Metacognition (HOT): higher-order representation of first-order state.
        metacognition = self.metacognition.update(
            prediction_error=prev_error,
            uncertainty=float(self.world_model.current_uncertainty),
            workspace=workspace,
            confidence=float(self_state.confidence),
            recent_errors=list(self._recent_errors),
            config=cfg,
        )

        # 9) Policy: choose an action (active inference; value == -EFE).
        decision: ActionDecision = self.policy.choose_action(
            predictions,
            memory_matches,
            self_state,
            goals,
            self.last_emotion,
            salient,
            cfg,
        )

        # The prediction backing the chosen action (for trace + error).
        chosen_prediction = self._prediction_for(predictions, decision)

        # 10) Act on the world.
        if self._shared_world is not None:
            result = self._shared_world.step(self.agent_id, decision)
        else:
            result = self.world.step(decision)

        # 11) Prediction error + world-model learning.
        current_error = self.world_model.compute_error(chosen_prediction, result)
        # 11b) HOOK (perturbation: forced surprise): inject extra prediction
        #      error so confusion + the metacognitive error monitor respond
        #      (active inference). No-op when no surprise is pending.
        if self._pending_surprise > 0.0:
            current_error = float(
                min(1.0, max(0.0, current_error + self._pending_surprise))
            )
            self._pending_surprise = 0.0
        self.world_model.update(chosen_prediction, result)
        self._recent_errors.append(float(current_error))
        error_reduction = prev_error - current_error

        # 12) Emotion update from this tick's signals.
        emotion = self.emotion_model.update(
            danger=float(result.actual.get("danger", 0.0)),
            uncertainty=float(self.world_model.current_uncertainty),
            novelty=float(result.actual.get("novelty", 0.0)),
            prediction_error=current_error,
            energy=float(result.new_energy),
            initial_energy=float(cfg.initial_energy),
            goal_progress=float(result.actual.get("goal_progress", 0.0)),
            error_reduction=error_reduction,
            prev=self.last_emotion,
            config=cfg,
        )

        # Emotional contagion from visible others (no-op when alone).
        if self._shared_world is not None and visible_agents:
            others = {m.agent_id: m for m in self.theory_of_mind.all_models()}
            emotion = apply_contagion(emotion, visible_agents, others, rate=cfg.contagion_rate, grid_size=cfg.grid_size)
            # Reputation: nudge trust of nearby others by this tick's reward sign.
            reward_sign = float(result.energy_delta) + float(result.actual.get("goal_progress", 0.0))
            for av in visible_agents:
                if av.distance <= 1.5:
                    update_trust(self.theory_of_mind.model_of(av.id), reward_sign, rate=0.25)

        # 13) Emotion already updated above; now compute the IIT-inspired
        #     integration proxy over the (post-competition) coalitions.
        integration = self.integration_monitor.phi_proxy(
            workspace.competition, workspace.broadcast_strength
        )

        # 14) BIND: assemble the unified ConsciousMoment (phenomenal-binding
        #     analogue). A one-line FR synthesis of what the system is aware of,
        #     its dominant affect and the chosen action.
        conscious_moment = self._bind_moment(
            tick=result.tick,
            workspace=workspace,
            attention_schema=attention_schema,
            decision=decision,
            emotion=emotion,
            mood=float(self.self_model.snapshot().mood),
            integration=integration,
            chosen_prediction=chosen_prediction,
        )
        self._stream.append(conscious_moment)

        # 15) Self-model update; fold the conscious contents into the narrative.
        self.self_model.update(
            decision=decision,
            result=result,
            prediction_error=current_error,
            emotion=emotion,
            goals=goals,
            tick=result.tick,
            conscious_contents=conscious_moment.contents,
        )
        self_state_after = self.self_model.snapshot()
        # Re-bind valence with the freshly updated mood for consistency.
        conscious_moment.valence = float(self_state_after.mood)

        # 16) Episodic storage (importance-gated). GWT: globally-broadcast
        #     (ignited / conscious) content is better encoded, so its importance
        #     is boosted; the importance gate still applies.
        base_importance = self.memory.compute_importance(
            energy_delta=float(result.energy_delta),
            danger=max((p.danger for p in percepts), default=0.0),
            prediction_error=float(current_error),
            emotion=emotion,
        )
        if workspace.ignited:
            base_importance = float(min(1.0, base_importance * 1.5 + 0.1))
        self.memory.store_experience(
            tick=result.tick,
            perception=percepts,
            action=decision.action,
            target_id=decision.target_id,
            result_energy_delta=result.energy_delta,
            prediction_error=current_error,
            emotion=emotion,
            importance=base_importance,
            summary=decision.rationale,
        )

        # 17) Introspection (generated from state, augmented with v2 sub-states).
        introspection = self.introspection.generate(
            observation=observation,
            salient=salient,
            prediction=chosen_prediction,
            decision=decision,
            memory_matches=memory_matches,
            self_model=self_state_after,
            emotion=emotion,
            workspace=workspace,
            attention_schema=attention_schema,
            metacognition=metacognition,
            integration=integration,
        )

        # 18) Metrics (existing fields + v2 consciousness metrics).
        metrics = Metrics(
            tick=result.tick,
            prediction_error=round(float(current_error), 4),
            self_coherence=round(float(self_state_after.coherence), 4),
            attention_focus=round(float(self.attention.focus(salient)), 4),
            working_memory_load=round(float(self.working_memory.load()), 4),
            autobiographical_memory_count=int(self.memory.count()),
            goal_pressure=round(float(self.motivation.total_pressure(goals)), 4),
            emotional_state=emotion,
            energy=round(float(result.new_energy), 4),
            uncertainty=round(float(self.world_model.current_uncertainty), 4),
            novelty_score=round(float(result.actual.get("novelty", 0.0)), 4),
            action_confidence=round(float(decision.confidence), 4),
            phi_proxy=round(float(integration.phi_proxy), 4),
            free_energy=round(float(chosen_prediction.expected_free_energy), 4),
            broadcast_strength=round(float(workspace.broadcast_strength), 4),
            meta_confidence=round(float(metacognition.meta_confidence), 4),
            awareness_level=round(float(attention_schema.awareness_level), 4),
            ignition=bool(workspace.ignited),
            arousal=round(float(workspace.arousal), 4),
        )

        # Publish this agent's social signal so others can perceive it.
        if self._shared_world is not None:
            affects = {"fear": emotion.fear, "curiosity": emotion.curiosity,
                       "satisfaction": emotion.satisfaction, "fatigue": emotion.fatigue,
                       "confusion": emotion.confusion}
            dom_affect = max(affects, key=affects.get)
            self._shared_world.agents[self.agent_id].publish(
                decision.action, dom_affect, float(self_state_after.mood))
            # VERBALIZE => emit a grounded message (delivered next tick).
            last_emitted = None
            if decision.action == ActionType.VERBALIZE:
                content, vector = build_message_content(self.agent_id, conscious_moment)
                self._shared_world.post_message(self.agent_id, content, vector)
                last_emitted = content
            self._last_social = SocialState(
                agent_id=self.agent_id,
                others=self.theory_of_mind.all_models(),
                affiliation_pressure=float(next((g.pressure for g in goals if g.need == "affiliate"), 0.0)),
                last_emitted=last_emitted,
                received_count=len(audible_messages),
            )
        else:
            self._last_social = None

        # 19) Assemble the trace (with the 5 new sub-objects) and persist.
        trace = CycleTrace(
            tick=result.tick,
            observation=observation,
            salient=salient,
            working_memory=self.working_memory.contents(),
            prediction=chosen_prediction,
            decision=decision,
            result=result,
            emotion=emotion,
            goals=goals,
            self_model=self_state_after,
            introspection=introspection,
            metrics=metrics,
            workspace=workspace,
            attention_schema=attention_schema,
            metacognition=metacognition,
            conscious_moment=conscious_moment,
            integration=integration,
            social=self._last_social,
        )
        self.trace_logger.log(trace)

        # Update rolling state for the next tick.
        self._prev_prediction_error = prev_error
        self.last_prediction_error = current_error
        self.last_emotion = emotion
        self.last_trace = trace
        self._last_metrics = metrics
        self._last_introspection = introspection
        self._last_metacognition = metacognition
        self._last_workspace = workspace
        return trace

    @staticmethod
    def _prediction_for(
        predictions: list[Prediction], decision: ActionDecision
    ) -> Prediction:
        """Return the prediction matching the chosen (action, target)."""
        for pred in predictions:
            if pred.action == decision.action and pred.target_id == decision.target_id:
                return pred
        # Fallback: first prediction or a neutral one (keeps the trace populated).
        if predictions:
            return predictions[0]
        return Prediction(
            action=decision.action,
            target_id=decision.target_id,
            expected_energy_delta=0.0,
            expected_danger=0.0,
            expected_novelty=0.0,
            expected_goal_progress=0.0,
            uncertainty=0.5,
            value=0.0,
        )

    # ------------------------------------------------------------------ #
    # Interaction hooks (additive; no-ops when buffers are empty)
    # ------------------------------------------------------------------ #
    def _apply_attend_bias(self, salient: list[SalientItem]) -> list[SalientItem]:
        """Top-down attention steering (AST): boost the biased target's saliency.

        If ``self._attend_bias`` is set and its ``target_id`` matches a currently
        salient percept, that item's saliency is multiplied by ``(1 + strength)``
        and the list is re-sorted so the boosted item can win the perception
        coalition. The bias ttl is decremented each cycle and the bias dropped
        when it reaches zero; if the target is not visible this cycle the bias is
        kept pending (only its ttl ticks down). No-op when no bias is set.
        """
        bias = self._attend_bias
        if bias is None:
            return salient
        boosted = list(salient)
        for item in boosted:
            if item.percept.object_id == int(bias.target_id):
                item.saliency = float(
                    max(0.0, item.saliency * (1.0 + float(bias.strength)))
                )
        boosted.sort(key=lambda it: it.saliency, reverse=True)
        # Decrement ttl; drop the bias when it expires.
        bias.ttl = int(bias.ttl) - 1
        if bias.ttl <= 0:
            self._attend_bias = None
        return boosted

    def _injection_coalitions(self) -> list[Coalition]:
        """Build one coalition per active cognitive injection (GWT competition).

        Each injection contributes a coalition via
        :meth:`GlobalWorkspace.make_coalition` carrying its activation/precision.
        Each injection's ttl is decremented and injections with ttl<=0 are
        dropped. Returns an empty list (no-op) when nothing is pending.
        """
        if not self._pending_injections:
            return []
        coalitions: list[Coalition] = []
        survivors: list[CognitiveInjection] = []
        for inj in self._pending_injections:
            coalitions.append(
                self.global_workspace.make_coalition(
                    str(inj.source),
                    str(inj.content),
                    activation=float(inj.activation),
                    precision=float(inj.precision),
                    vector=[float(inj.activation), float(inj.precision), 0.0, 0.0],
                )
            )
            inj.ttl = int(inj.ttl) - 1
            if inj.ttl > 0:
                survivors.append(inj)
        self._pending_injections = survivors
        return coalitions

    # ------------------------------------------------------------------ #
    # Arousal / vigilance (v2.1)
    # ------------------------------------------------------------------ #
    def _update_arousal(
        self, percepts: list[Percept], prev_error: float, cfg: SimConfig
    ) -> float:
        """Update and return the global arousal level for this tick.

        Arousal is a bounded, EMA-smoothed scalar. Its target rises with the most
        dangerous/novel thing in view, the recent prediction error, and any queued
        surprise perturbation; absent those it relaxes toward ``arousal_baseline``.
        Higher arousal lowers the effective ignition threshold, so salient events
        (and injected stimuli/perturbations) can reach conscious access.
        """
        max_danger = max((float(p.danger) for p in percepts), default=0.0)
        max_novelty = max((float(p.novelty) for p in percepts), default=0.0)
        surprise = float(self._pending_surprise)
        gain = float(cfg.arousal_gain)
        # Salience in [0,1]: how much the current situation demands vigilance.
        salience = gain * (
            0.55 * max_danger + 0.35 * max_novelty + 0.45 * float(prev_error) + 0.6 * surprise
        )
        salience = min(1.0, max(0.0, salience))
        # Target arousal tracks salience directly so vigilance can dip BELOW the
        # baseline in calm stretches (raising the ignition bar) and rise above it
        # when salient (lowering the bar). ``arousal_baseline`` is the reference
        # level at which the ignition threshold is nominal, not a floor.
        target = min(AROUSAL_CEIL, max(AROUSAL_FLOOR, salience))
        self._arousal = float(
            min(
                AROUSAL_CEIL,
                max(
                    AROUSAL_FLOOR,
                    (1.0 - AROUSAL_EMA) * self._arousal + AROUSAL_EMA * target,
                ),
            )
        )
        return self._arousal

    # ------------------------------------------------------------------ #
    # Global-workspace coalition construction (GWT)
    # ------------------------------------------------------------------ #
    def _build_coalitions(
        self,
        *,
        percepts: list[Percept],
        salient: list[SalientItem],
        goals: list,
        memory_matches: list[MemoryRecord],
        prev_error: float,
        uncertainty: float,
        self_state: SelfModelState,
        emotion: EmotionState,
        cfg: SimConfig,
    ) -> list[Coalition]:
        """Build one bid per active specialist source (GWT competition input).

        Each coalition carries an activation (raw bid strength), a precision
        (confidence weighting) and a small feature vector summarizing its content
        (used by the Phi-proxy). Sources with nothing to contribute are skipped.
        """
        mk = self.global_workspace.make_coalition
        coalitions: list[Coalition] = []

        # --- perception: the single most salient item. ---
        if salient:
            top = salient[0]
            p = top.percept
            coalitions.append(
                mk(
                    "perception",
                    f"perception: object {p.object_id} ({p.kind})",
                    activation=float(top.saliency),
                    precision=float(max(0.0, 1.0 - cfg.world_noise - uncertainty)),
                    vector=[
                        float(p.danger),
                        float(p.novelty),
                        float(p.utility),
                        float(min(p.energy_value / 10.0, 1.0)),
                    ],
                )
            )

        # --- memory: best episodic match. ---
        if memory_matches:
            best = memory_matches[0]
            max_emotion = max(
                best.emotion.fear,
                best.emotion.curiosity,
                best.emotion.satisfaction,
                best.emotion.fatigue,
                best.emotion.confusion,
            )
            coalitions.append(
                mk(
                    "memory",
                    f"memory: record {best.id} ({best.action.value})",
                    activation=float(best.importance),
                    precision=float(best.importance),
                    vector=[
                        float(max_emotion),
                        float(min(abs(best.result_energy_delta) / 10.0, 1.0)),
                        float(best.prediction_error),
                        0.0,
                    ],
                )
            )

        # --- motivation: top goal pressure. ---
        if goals:
            top_goal = max(goals, key=lambda g: g.pressure)
            total = self.motivation.total_pressure(goals)
            norm_pressure = (
                float(top_goal.pressure) / float(total) if total > 0.0 else 0.0
            )
            coalitions.append(
                mk(
                    "motivation",
                    f"motivation: need '{top_goal.need}'",
                    activation=norm_pressure,
                    precision=float(cfg.coherence_drive)
                    / max(1.0, float(cfg.coherence_drive)),
                    vector=[norm_pressure, 0.0, float(min(top_goal.pressure, 1.0)), 0.0],
                )
            )

        # --- prediction_error: surprise signal (high precision). ---
        coalitions.append(
            mk(
                "prediction_error",
                "prediction error (surprise)",
                activation=float(max(prev_error, uncertainty)),
                precision=0.9,
                vector=[float(prev_error), float(uncertainty), 0.0, 0.0],
            )
        )

        # --- interoception: low-energy / fatigue / strong mood. ---
        energy_norm = float(self_state.energy) / max(1.0, float(cfg.initial_energy))
        low_energy = max(0.0, 1.0 - energy_norm)
        intero_activation = max(low_energy, float(emotion.fatigue), abs(float(self_state.mood)))
        coalitions.append(
            mk(
                "interoception",
                "interoception: internal bodily state",
                activation=float(intero_activation),
                precision=float(self_state.confidence),
                vector=[
                    float(min(energy_norm, 1.0)),
                    float(emotion.fatigue),
                    float((self_state.mood + 1.0) / 2.0),
                    float(emotion.fear),
                ],
            )
        )

        # --- metacognition: the *previous* higher-order state. ---
        if self._last_metacognition is not None:
            mc = self._last_metacognition
            coalitions.append(
                mk(
                    "metacognition",
                    "metacognition: higher-order representation",
                    activation=float(max(mc.error_monitor, 1.0 - mc.meta_confidence)),
                    precision=float(mc.meta_confidence),
                    vector=[
                        float(mc.error_monitor),
                        float(mc.meta_confidence),
                        float(mc.perception_reliability),
                        float(mc.prediction_reliability),
                    ],
                )
            )

        # --- social: the most salient visible other (theory of mind). ---
        social_coalition = self.theory_of_mind.social_coalition(grid_size=cfg.grid_size)
        if social_coalition is not None:
            coalitions.append(social_coalition)

        # --- communication: the most salient received message. ---
        if self._shared_world is not None:
            best_msg = None
            best_sal = -1.0
            for msg in self._last_audible_messages:
                sal = sum(msg.vector) if msg.vector else 0.3
                if sal > best_sal:
                    best_sal, best_msg = sal, msg
            if best_msg is not None:
                other = self.theory_of_mind.model_of(best_msg.sender_id)
                coalitions.append(message_coalition(best_msg, other))

        return coalitions

    # ------------------------------------------------------------------ #
    # Conscious-moment binding
    # ------------------------------------------------------------------ #
    @staticmethod
    def _bind_moment(
        *,
        tick: int,
        workspace: WorkspaceState,
        attention_schema: AttentionSchemaState,
        decision: ActionDecision,
        emotion: EmotionState,
        mood: float,
        integration: IntegrationState,
        chosen_prediction: Prediction,
    ) -> ConsciousMoment:
        """Bind the tick's global state into a single unified ConsciousMoment.

        This is a functional phenomenal-binding analogue: it composes the
        access-conscious content (GWT winner / AST aware_of), the dominant
        functional affect and the chosen action into one momentary global state.
        It does NOT establish phenomenal experience.
        """
        aware_of = attention_schema.aware_of
        # Dominant functional affect label.
        affects = {
            "fear": float(emotion.fear),
            "curiosity": float(emotion.curiosity),
            "satisfaction": float(emotion.satisfaction),
            "fatigue": float(emotion.fatigue),
            "confusion": float(emotion.confusion),
        }
        dom_affect = max(affects, key=affects.get)
        contents = (
            f"Aware of: {aware_of}; dominant affect: {dom_affect}; "
            f"action: {decision.action.value}"
            + (f"#{decision.target_id}" if decision.target_id is not None else "")
            + "."
        )
        access = "global access (ignition)" if workspace.ignited else "subliminal"
        summary = (
            f"t{tick}: {access}, Phi-proxy={integration.phi_proxy:.2f}, "
            f"awareness={attention_schema.awareness_level:.2f}, "
            f"arousal={workspace.arousal:.2f}."
        )
        return ConsciousMoment(
            tick=int(tick),
            contents=contents,
            ignited=bool(workspace.ignited),
            dominant_source=workspace.winner_source,
            awareness_level=float(attention_schema.awareness_level),
            valence=float(mood),
            phi_proxy=float(integration.phi_proxy),
            free_energy=float(chosen_prediction.expected_free_energy),
            arousal=float(workspace.arousal),
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    # Accessors / lifecycle
    # ------------------------------------------------------------------ #
    def introspect(self) -> IntrospectionReport:
        """Regenerate an introspection report from the current internal state."""
        if self._shared_world is not None:
            observation = self._shared_world.observe(self.agent_id)
            seen_counts = self._shared_world.seen_counts
        else:
            observation = self.world.observe()
            seen_counts = self.world.seen_counts
        percepts = self.perception.encode(observation, seen_counts)
        self_state = self.self_model.snapshot()
        goals = self.motivation.evaluate(
            self_state,
            self.last_emotion,
            percepts,
            self.last_prediction_error,
            float(self.world_model.current_uncertainty),
            self.config,
        )
        salient = self.attention.select(
            percepts, goals, self.last_prediction_error, self.last_emotion, self.config
        )
        candidates = self.policy.candidate_actions(salient, self_state)
        predictions = self.world_model.predict_all(observation, candidates)
        memory_matches = self.memory.retrieve_similar(
            percepts, self.config.memory_retrieval_k
        )
        decision = self.policy.choose_action(
            predictions,
            memory_matches,
            self_state,
            goals,
            self.last_emotion,
            salient,
            self.config,
        )
        chosen = self._prediction_for(predictions, decision)
        report = self.introspection.generate(
            observation=observation,
            salient=salient,
            prediction=chosen,
            decision=decision,
            memory_matches=memory_matches,
            self_model=self_state,
            emotion=self.last_emotion,
        )
        self._last_introspection = report
        return report

    def set_goal(self, goal: str) -> None:
        """Register a new explicit goal on the self-model."""
        self.self_model.set_goal(goal)

    def metrics(self) -> Metrics:
        """Return the latest metrics, or a neutral baseline before any tick."""
        if self._last_metrics is not None:
            return self._last_metrics
        return Metrics(
            tick=(self._shared_world.tick if self._shared_world is not None else self.world.tick),
            prediction_error=0.0,
            self_coherence=float(self.self_model.snapshot().coherence),
            attention_focus=0.0,
            working_memory_load=float(self.working_memory.load()),
            autobiographical_memory_count=int(self.memory.count()),
            goal_pressure=0.0,
            emotional_state=self.last_emotion,
            energy=round(float(self._shared_world.agents[self.agent_id].energy if self._shared_world is not None else self.world.agent_energy), 4),
            uncertainty=round(float(self.world_model.current_uncertainty), 4),
            novelty_score=0.0,
            action_confidence=0.0,
        )

    def reset(self) -> None:
        """Rebuild every sub-system from the current config (preserving stores)."""
        self._build(self.config, preserve_identity=True)

    def apply_config(self, patch: dict | ConfigPatch) -> SimConfig:
        """Merge a partial config patch and rebuild, preserving identity/stores.

        Returns the resulting :class:`SimConfig`.
        """
        if isinstance(patch, ConfigPatch):
            updates = patch.model_dump(exclude_none=True)
        else:
            updates = {k: v for k, v in dict(patch).items() if v is not None}
        merged = self.config.model_copy(update=updates)
        self._build(merged, preserve_identity=True)
        return self.config

    def self_model_state(self) -> SelfModelState:
        """Return the current self-model state snapshot."""
        return self.self_model.snapshot()

    def recent_memories(self, n: int) -> list[MemoryRecord]:
        """Return the ``n`` most recent autobiographical records."""
        return self.memory.recent(n)

    def world_snapshot(self) -> dict:
        """Return a JSON-serializable snapshot of the world."""
        return self.world.snapshot()

    # ------------------------------------------------------------------ #
    # Interaction modalities (grounded; read/affect real internal variables)
    # ------------------------------------------------------------------ #
    def ask(self, question: str, intent: str | None = None) -> AskResponse:
        """Introspective-dialogue probe (GWT/HOT reportability).

        Builds a French answer grounded ONLY in the live internal variables of
        the latest cycle (workspace, attention schema, metacognition, decision,
        prediction, emotion, self-model, recent memories). If no cycle has run
        yet, one is run first so there is real state to report. The answer is
        explicitly framed as a report generated from internal variables and
        carries the canonical functional-simulation disclaimer.
        """
        if self.last_trace is None:
            self.cognitive_cycle()
        trace = self.last_trace
        self_state = self.self_model.snapshot()
        recent = self.recent_memories(3)
        return self._dialogue.answer(
            question=question,
            intent=intent,
            conscious_moment=trace.conscious_moment if trace else None,
            workspace=trace.workspace if trace else self.workspace_state(),
            attention_schema=trace.attention_schema if trace else None,
            metacognition=trace.metacognition if trace else self._last_metacognition,
            decision=trace.decision if trace else None,
            prediction=trace.prediction if trace else None,
            emotion=trace.emotion if trace else self.last_emotion,
            self_model=self_state,
            recent_memories=recent,
            disclaimer=DISCLAIMER_EN,
        )

    def inject(self, injection: CognitiveInjection) -> dict:
        """Cognitive injection: queue a coalition for the next competition (GWT).

        The injection competes in the workspace on the next cycle(s) per its
        ttl, testing the ignition threshold (subliminal vs conscious access).
        """
        self._pending_injections.append(injection)
        return {"accepted": True, "pending": len(self._pending_injections)}

    def attend(self, req: AttendRequest) -> dict:
        """Attention steering: bias top-down attention toward a target (AST).

        The bias boosts the target's saliency on subsequent cycles (per its
        ttl) so its perception coalition is more likely to win global access.
        """
        self._attend_bias = req
        return {"ok": True, "target_id": int(req.target_id)}

    def perturb(self, req: PerturbRequest) -> dict:
        """Perturbation: apply a choc / surprise / apaisement to internal state.

        - ``choc``: drain world energy (also synced into the self-model).
        - ``surprise``: queue forced prediction error for the next cycle
          (feeds confusion + the metacognitive error monitor).
        - ``apaisement``: reduce the last fear scalar and raise self-model mood.

        Returns a small dict describing the applied effect. All values are
        clamped to their valid ranges.
        """
        ptype = str(req.type).strip().lower()
        magnitude = float(req.magnitude)
        if ptype == "choc":
            cap = float(self.config.initial_energy) * ENERGY_CAP_FACTOR
            if self._shared_world is not None:
                body = self._shared_world.agents[self.agent_id]
                new_energy = float(min(cap, max(0.0, float(body.energy) - magnitude * 10.0)))
                body.energy = new_energy
            else:
                new_energy = float(
                    min(cap, max(0.0, float(self.world.agent_energy) - magnitude * 10.0))
                )
                self.world.agent_energy = new_energy
            # Sync the self-model's energy view so reports stay consistent.
            self.self_model._state.energy = new_energy
            return {
                "type": "choc",
                "energy": round(new_energy, 4),
                "drained": round(magnitude * 10.0, 4),
            }
        if ptype == "surprise":
            forced = float(min(1.0, max(0.0, magnitude)))
            self._pending_surprise = forced
            return {"type": "surprise", "pending_prediction_error": round(forced, 4)}
        if ptype == "apaisement":
            mag = float(min(1.0, max(0.0, magnitude)))
            old_fear = float(self.last_emotion.fear)
            new_fear = float(max(0.0, old_fear * (1.0 - mag)))
            self.last_emotion.fear = new_fear
            new_mood = float(
                max(-1.0, min(1.0, float(self.self_model._state.mood) + 0.2 * magnitude))
            )
            self.self_model._state.mood = new_mood
            return {
                "type": "apaisement",
                "fear": round(new_fear, 4),
                "mood": round(new_mood, 4),
            }
        return {"type": ptype, "applied": False, "reason": "unknown type"}

    def world_stimulus(self, stim: WorldStimulus) -> WorldObject:
        """World stimulus: inject a real object into the world the agent uses.

        Targets the shared world (society) when attached, else the solo world.
        """
        if self._shared_world is not None:
            return self._shared_world.inject_object(
                kind=stim.kind, x=stim.x, y=stim.y, intensity=stim.intensity,
                near_agent=self.agent_id,
            )
        return self.world.inject_object(
            kind=stim.kind, x=stim.x, y=stim.y, intensity=stim.intensity
        )

    # ------------------------------------------------------------------ #
    # v2 consciousness-architecture accessors
    # ------------------------------------------------------------------ #
    def workspace_state(self) -> WorkspaceState:
        """Return the latest global-workspace competition outcome (GWT).

        Before any cycle has run, returns a neutral, non-ignited state.
        """
        if self._last_workspace is not None:
            return self._last_workspace
        return WorkspaceState(
            ignited=False,
            threshold=float(self.config.ignition_threshold),
            winner_source=None,
            winner_content=None,
            broadcast_strength=0.0,
            competition=[],
            broadcast_vector=[],
        )

    def consciousness_state(self) -> dict:
        """Return the bound v2 consciousness sub-states from the latest cycle."""
        trace = self.last_trace
        ws = self.workspace_state()
        if trace is not None:
            return {
                "conscious_moment": trace.conscious_moment.model_dump(),
                "attention_schema": trace.attention_schema.model_dump(),
                "metacognition": trace.metacognition.model_dump(),
                "integration": trace.integration.model_dump(),
                "workspace": {
                    "ignited": bool(ws.ignited),
                    "winner_source": ws.winner_source,
                    "winner_content": ws.winner_content,
                    "broadcast_strength": float(ws.broadcast_strength),
                    "threshold": float(ws.threshold),
                },
            }
        # No cycle yet: neutral placeholders.
        return {
            "conscious_moment": None,
            "attention_schema": None,
            "metacognition": None,
            "integration": None,
            "workspace": {
                "ignited": False,
                "winner_source": None,
                "winner_content": None,
                "broadcast_strength": 0.0,
                "threshold": float(self.config.ignition_threshold),
            },
        }

    def stream(self, n: int) -> list[ConsciousMoment]:
        """Return up to the last ``n`` ConsciousMoments (most recent last)."""
        if n <= 0:
            return []
        items = list(self._stream)
        return items[-int(n):]


class SimulationManager:
    """Owns one :class:`CognitiveAgent` and an asyncio background tick loop.

    All ticking is serialized through an :class:`asyncio.Lock` so the background
    loop and ad-hoc ``tick()`` calls never run a cycle concurrently.
    """

    def __init__(self, config: SimConfig | None = None) -> None:
        """Create the manager and its agent (default config if none given)."""
        self.config = config or SimConfig()
        self.agent = CognitiveAgent(self.config)
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.running: bool = False

    # ------------------------------------------------------------------ #
    # Ticking
    # ------------------------------------------------------------------ #
    def tick(self) -> CycleTrace:
        """Run a single synchronous cognitive cycle and return its trace."""
        return self.agent.cognitive_cycle()

    async def _locked_tick(self) -> CycleTrace:
        """Run one cycle while holding the shared lock."""
        async with self._lock:
            return self.agent.cognitive_cycle()

    async def async_tick(self) -> CycleTrace:
        """Async-safe single tick guarded by the shared lock."""
        return await self._locked_tick()

    async def run(self, req: RunRequest) -> None:
        """Start a background loop ticking at ``req.tps`` until paused/max_ticks."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop(req))

    async def _run_loop(self, req: RunRequest) -> None:
        """Background loop body: tick under the lock, sleep 1/tps, honor limits."""
        tps = req.tps if req.tps and req.tps > 0 else 1.0
        delay = 1.0 / tps
        ticks_done = 0
        try:
            while self.running:
                async with self._lock:
                    self.agent.cognitive_cycle()
                ticks_done += 1
                if req.max_ticks is not None and ticks_done >= req.max_ticks:
                    break
                await asyncio.sleep(delay)
        finally:
            self.running = False

    def pause(self) -> None:
        """Stop the background loop (it finishes its current tick first)."""
        self.running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    # ------------------------------------------------------------------ #
    # Lifecycle / state
    # ------------------------------------------------------------------ #
    def reset(self, patch: dict | ConfigPatch | None = None) -> None:
        """Pause, then reset the agent, optionally applying a config patch."""
        self.pause()
        if patch is not None:
            self.config = self.agent.apply_config(patch)
        else:
            self.agent.reset()
            self.config = self.agent.config

    # ------------------------------------------------------------------ #
    # Interaction modalities (lock-guarded wrappers delegating to the agent)
    # ------------------------------------------------------------------ #
    async def ask(self, question: str, intent: str | None = None) -> AskResponse:
        """Lock-guarded introspective-dialogue probe (may run one cycle)."""
        async with self._lock:
            return self.agent.ask(question, intent)

    async def inject(self, injection: CognitiveInjection) -> dict:
        """Lock-guarded cognitive injection (queue a workspace coalition)."""
        async with self._lock:
            return self.agent.inject(injection)

    async def attend(self, req: AttendRequest) -> dict:
        """Lock-guarded attention steering (top-down saliency bias)."""
        async with self._lock:
            return self.agent.attend(req)

    async def perturb(self, req: PerturbRequest) -> dict:
        """Lock-guarded perturbation (choc / surprise / apaisement)."""
        async with self._lock:
            return self.agent.perturb(req)

    async def world_stimulus(self, stim: WorldStimulus) -> WorldObject:
        """Lock-guarded world stimulus (inject a real object into the world)."""
        async with self._lock:
            return self.agent.world_stimulus(stim)

    def state(self) -> dict:
        """Return a JSON-serializable summary of the current simulation state."""
        metrics = self.agent.metrics()
        intro = self.agent._last_introspection
        intro_summary = (
            intro.self_state if intro is not None else "No introspective report generated yet."
        )
        ws = self.agent.workspace_state()
        return {
            "world": self.agent.world_snapshot(),
            "metrics": metrics.model_dump(),
            "running": bool(self.running),
            "introspection_summary": intro_summary,
            "self_model": self.agent.self_model_state().model_dump(),
            "working_memory_load": float(self.agent.working_memory.load()),
            # v2 consciousness-architecture summary fields.
            "phi_proxy": float(metrics.phi_proxy),
            "free_energy": float(metrics.free_energy),
            "awareness_level": float(metrics.awareness_level),
            "ignition": bool(metrics.ignition),
            "broadcast_strength": float(metrics.broadcast_strength),
            "winner_source": ws.winner_source,
            "arousal": float(metrics.arousal),
        }


# ---------------------------------------------------------------------- #
# Module-level singleton
# ---------------------------------------------------------------------- #
_MANAGER: SimulationManager | None = None


def get_manager() -> "SocietyManager":
    """Return the process-wide SocietyManager (society of `config.n_agents`)."""
    global _MANAGER
    if _MANAGER is None:
        from core.society import SocietyManager
        _MANAGER = SocietyManager()
    return _MANAGER
