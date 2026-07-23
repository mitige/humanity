from __future__ import annotations
from enum import Enum
from math import isfinite
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionType(str, Enum):
    OBSERVE = "observe"
    MOVE = "move"
    APPROACH = "approach"
    AVOID = "avoid"
    INTERACT = "interact"
    REST = "rest"
    EXPLORE = "explore"
    ANALYZE = "analyze"
    VERBALIZE = "verbalize"


class WorldObject(BaseModel):
    id: int
    kind: str                      # "food" | "hazard" | "tool" | "curio"
    x: int
    y: int
    energy_value: float = 0.0      # energy gained on INTERACT
    danger: float = 0.0            # 0..1
    novelty: float = 0.0           # 0..1, decays as the agent sees/interacts
    utility: float = 0.0           # 0..1, task usefulness


class AgentView(BaseModel):
    """Another agent as perceived by an observer (grounded social percept)."""
    id: int
    x: int
    y: int
    distance: float
    last_action: ActionType | None = None
    dominant_affect: str = "neutral"   # label of the other's strongest functional affect
    valence: float = 0.0               # other's published mood in [-1, 1]


class Message(BaseModel):
    """A grounded utterance emitted by a VERBALIZE action; delivered next tick."""
    id: int
    tick_emitted: int
    sender_id: int
    content: str                       # grounded summary of the sender's ConsciousMoment
    vector: list[float] = Field(default_factory=list)  # small affect/feature summary
    x: int
    y: int
    radius: int                        # earshot radius from the emission point
    ttl: int                           # ticks the message stays deliverable
    # Phase 6 — an INVENTED word naming the speaker's salient meaning (naming
    # game). Hearers never receive the meaning: they must infer it from their
    # OWN context — that inference gap is what makes conventions emerge.
    word: str | None = None


class OtherMind(BaseModel):
    """One agent's functional model of another agent (theory of mind, ToM)."""
    agent_id: int
    inferred_action: ActionType | None = None
    inferred_affect: str = "neutral"
    inferred_valence: float = 0.0      # -1..1
    trust: float = 0.5                 # 0..1 reputation/confidence
    familiarity: float = 0.0           # 0..1 grows with exposure
    last_seen_tick: int = -1
    note: str = ""


class SocialState(BaseModel):
    """An agent's social snapshot for the trace/UI."""
    agent_id: int
    others: list[OtherMind] = Field(default_factory=list)
    affiliation_pressure: float = 0.0
    last_emitted: str | None = None
    received_count: int = 0


class CircadianState(BaseModel):
    """Deterministic day/night phase modulating arousal (Phase 2)."""
    phase: float          # 0..1 within the period
    daylight: float       # 0..1 (1 = noon, 0 = midnight)
    is_night: bool
    period: int


class SleepState(BaseModel):
    """Sleep / consolidation / dream snapshot (Phase 2)."""
    is_sleeping: bool
    fatigue: float
    consolidated: int = 0
    pruned: int = 0
    dream: str | None = None
    sleep_ticks: int = 0


class ImaginationState(BaseModel):
    """Bounded mental rollout outcome (Phase 2)."""
    best_first_action: ActionType | None = None
    horizon: int = 0
    imagined_value: float = 0.0
    n_rollouts: int = 0


class CuriosityState(BaseModel):
    """Learning-progress driven curiosity / boredom (Phase 2)."""
    learning_progress: float = 0.0
    boredom: float = 0.0
    intrinsic_reward: float = 0.0


class AgencyState(BaseModel):
    """Sense of agency: predicted vs actual effect of one's own action (Phase 2)."""
    agency: float = 0.0
    predicted_self_effect: float = 0.0
    actual_self_effect: float = 0.0


class LearningState(BaseModel):
    """Learned action values + effective learning rate (Phase 3)."""
    q_values: dict[str, float] = Field(default_factory=dict)
    last_reward: float = 0.0
    effective_lr: float = 0.2
    # Phase 7 — contextual TD(λ) extension (defaults preserve older traces).
    td_context: str | None = None    # active context key, e.g. "d1e0n1s0"
    td_error: float = 0.0            # last temporal-difference error
    n_contexts: int = 0              # contexts with at least one learned value


class ConceptState(BaseModel):
    """Online concept formation snapshot (Phase 3)."""
    dominant_concept: int | None = None
    match: float = 0.0
    n_concepts: int = 0


class PersonalityState(BaseModel):
    """Emergent personality profile (Phase 3)."""
    label: str = "nascent"
    openness: float = 0.5
    caution: float = 0.5
    novelty_seeking: float = 0.5
    vector: list[float] = Field(default_factory=list)


class Intervention(BaseModel):
    """A scripted scenario intervention applied at a given tick (Phase 4)."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    at_tick: int = Field(ge=0, le=100_000)
    type: Literal["stimulus", "perturb", "goal", "inject", "attend"]
    agent_id: int = Field(default=0, ge=0, le=127)
    params: dict[str, Any] = Field(default_factory=dict, max_length=16)

    @model_validator(mode="after")
    def validate_typed_params(self) -> "Intervention":
        raw = dict(self.params)
        if self.type == "stimulus":
            raw.setdefault("kind", "curio")
            parsed = WorldStimulus.model_validate(raw)
        elif self.type == "perturb":
            legacy_type = raw.pop("ptype", None)
            if legacy_type is not None:
                if "type" in raw:
                    raise ValueError("use either params.type or params.ptype, not both")
                raw["type"] = legacy_type
            raw.setdefault("type", "surprise")
            parsed = PerturbRequest.model_validate(raw)
        elif self.type == "goal":
            parsed = GoalRequest.model_validate(raw)
        elif self.type == "inject":
            raw.setdefault("content", "signal")
            parsed = CognitiveInjection.model_validate(raw)
        else:
            parsed = AttendRequest.model_validate(raw)
        self.params = parsed.model_dump(exclude_none=True)
        return self


class Scenario(BaseModel):
    """A declarative, reproducible scenario (Phase 4)."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="scenario", min_length=1, max_length=100)
    config: "ConfigPatch" = Field(default_factory=lambda: ConfigPatch())
    ticks: int = Field(default=20, ge=0, le=100_000)
    interventions: list[Intervention] = Field(default_factory=list, max_length=1000)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)

    @model_validator(mode="after")
    def validate_intervention_reachability(self) -> "Scenario":
        n_agents = self.config.n_agents
        if n_agents is None:
            n_agents = SimConfig().n_agents
        for intervention in self.interventions:
            if intervention.at_tick >= self.ticks:
                raise ValueError(
                    "intervention at_tick must be smaller than scenario ticks")
            if intervention.agent_id >= n_agents:
                raise ValueError(
                    "intervention agent_id is outside the configured society")
        return self


class MetricSeries(BaseModel):
    """A long-format metrics time series (Phase 4)."""
    fields: list[str]
    rows: list[dict] = Field(default_factory=list)


class ScenarioResult(BaseModel):
    """Result of running a scenario (Phase 4)."""
    name: str
    ticks: int
    series: MetricSeries
    summary: dict = Field(default_factory=dict)
    disclaimer: str


class BatteryResult(BaseModel):
    """Result of a functional test-battery probe (Phase 4)."""
    test: str
    score: float
    detail: dict = Field(default_factory=dict)
    interpretation: str
    disclaimer: str


class Percept(BaseModel):
    object_id: int
    kind: str
    dx: int                        # object.x - agent.x
    dy: int
    distance: float                # euclidean
    danger: float
    novelty: float
    utility: float
    energy_value: float


class Observation(BaseModel):
    tick: int
    agent_x: int
    agent_y: int
    agent_energy: float
    radius: int
    visible: list[WorldObject]
    visible_agents: list[AgentView] = Field(default_factory=list)
    audible_messages: list["Message"] = Field(default_factory=list)


class SalientItem(BaseModel):
    percept: Percept
    saliency: float
    reasons: dict[str, float]      # contribution breakdown by source


class WorkingMemoryItem(BaseModel):
    percept: Percept
    saliency: float
    created_tick: int
    last_seen_tick: int


class Prediction(BaseModel):
    action: ActionType
    target_id: int | None = None
    expected_energy_delta: float
    expected_danger: float
    expected_novelty: float
    expected_goal_progress: float
    uncertainty: float             # 0..1
    value: float                   # scalar expected utility used by policy
    epistemic_value: float = 0.0
    pragmatic_value: float = 0.0
    expected_free_energy: float = 0.0


class EmotionState(BaseModel):
    fear: float = 0.0
    curiosity: float = 0.0
    satisfaction: float = 0.0
    fatigue: float = 0.0
    confusion: float = 0.0


class GoalPressure(BaseModel):
    need: str                      # "preserve_energy" | "reduce_danger" | "explore_novelty" | "improve_prediction" | "maintain_coherence" | "achieve_goals"
    pressure: float                # >= 0
    description: str


class ActionDecision(BaseModel):
    action: ActionType
    target_id: int | None = None
    direction: list[int] | None = None   # [dx, dy] each in {-1,0,1}
    confidence: float                     # 0..1
    rationale: str
    candidate_scores: dict[str, float]    # key = action label (with optional target), value = score


class MemoryRecord(BaseModel):
    id: int
    tick: int
    perception: list[Percept]
    action: ActionType
    target_id: int | None = None
    result_energy_delta: float
    prediction_error: float
    emotion: EmotionState
    importance: float
    summary: str


class RelationalSelf(BaseModel):
    """Looking-glass self: how the agent is regarded by the others who model it.

    A FUNCTIONAL social anchor for the self-model (Cooley/Mead/Hegel/Lacan, as
    variables). Reproducing it does not prove phenomenality; the agent is not
    conscious. ``social_presence == 0`` means nobody currently models the agent
    (isolation) — the relational self is then a neutral, inert marker.
    """
    reflected_appraisal: float = 0.5   # 0..1 how positively others regard me (0.5 = neutral)
    social_presence: float = 0.0       # 0..1 fraction of others who currently model me
    regard_consistency: float = 0.0    # 0..1 agreement among observers (1 = a stable mirror)
    n_observers: int = 0
    note: str = ""


class SelfModelState(BaseModel):
    identity: str
    age_ticks: int
    energy: float
    confidence: float              # 0..1
    mood: float                    # valence -1..1
    preferences: dict[str, float]  # per ActionType label, learned appeal
    active_goals: list[str]
    capability_beliefs: dict[str, float]  # per ActionType label, believed success 0..1
    coherence: float               # 0..1 narrative/self stability
    narrative: str
    relational_self: RelationalSelf | None = None  # looking-glass self (social mirror); None unless enabled


class StepResult(BaseModel):
    tick: int
    action: ActionType
    target_id: int | None = None
    energy_delta: float
    new_energy: float
    events: list[str]
    actual: dict[str, float]       # keys: danger, novelty, goal_progress, energy_value, utility


class IntrospectionReport(BaseModel):
    tick: int
    disclaimer: str
    perceive: str                  # "ce que je percois"
    attend: str                    # "ce a quoi je fais attention"
    predict: str                   # "ce que je predis"
    intend: str                    # "ce que je veux faire"
    why: str                       # "pourquoi"
    remember: str                  # "ce dont je me souviens"
    self_state: str                # "ce que mon self-model indique"


class Metrics(BaseModel):
    tick: int
    prediction_error: float
    self_coherence: float
    attention_focus: float
    working_memory_load: float
    autobiographical_memory_count: int
    goal_pressure: float
    emotional_state: EmotionState
    energy: float
    uncertainty: float
    novelty_score: float
    action_confidence: float
    phi_proxy: float = 0.0
    free_energy: float = 0.0
    broadcast_strength: float = 0.0
    meta_confidence: float = 0.0
    awareness_level: float = 0.0
    ignition: bool = False
    arousal: float = 0.0          # global vigilance/wakefulness modulating ignition
    agency: float = 0.0
    boredom: float = 0.0
    learning_progress: float = 0.0
    daylight: float = 1.0
    is_sleeping: bool = False
    effective_learning_rate: float = 0.2
    concept_match: float = 0.0
    n_concepts: int = 0
    presence: float = 0.0            # interoceptive presence (Phase 5); 0 when off
    intero_error: float = 0.0        # interoceptive prediction error (Phase 5)
    temporal_surprise: float = 0.0   # protention violation (Phase 5)
    phi_ar: float = 0.0              # Barrett–Seth Φ_AR (Phase 5); 0 until computed
    reality_accuracy: float = 0.0    # reality-monitor rolling accuracy (Phase 5)
    language_success: float = 0.0    # naming-game success EMA (Phase 6); 0 when off
    vocabulary_size: int = 0         # invented words currently held (Phase 6)
    phi_causal: float = 0.0          # exact coarse-grained causal Φ (Phase 7); 0 until computed
    vfe: float = 0.0                 # explicit variational free energy (Phase 7); 0 when off
    planning_depth: int = 0          # policy-search horizon actually used (Phase 7)
    wandering_occupancy: float = 0.0 # default-mode occupancy EMA (Phase 7); 0 when off
    task_progress: float = 0.0       # current world-task progress (Phase 7); 0 when off
    semantic_similarity: float = 0.0 # mean cosine of episodic matches (Phase 7); 0 when off
    td_error: float = 0.0            # temporal-difference error (Phase 7); 0 when off


class Coalition(BaseModel):
    """A bid from a specialist process competing for global-workspace access (GWT)."""
    source: str            # one of WORKSPACE_SOURCES
    content: str           # human-readable content label
    activation: float      # 0..1 raw strength of the bid
    precision: float       # 0..1 confidence weighting (precision-weighting)
    vector: list[float] = Field(default_factory=list)  # small feature vector of the content (for Phi proxy)


class WorkspaceState(BaseModel):
    """Outcome of workspace competition: ignition + global broadcast (GWT)."""
    ignited: bool
    threshold: float
    winner_source: str | None = None
    winner_content: str | None = None
    broadcast_strength: float
    competition: list[Coalition] = Field(default_factory=list)
    broadcast_vector: list[float] = Field(default_factory=list)
    # ignition diagnostics (v2.1): ignition now depends on the winner's absolute
    # drive and its dominance, modulated by arousal — not on a softmax share.
    ignition_score: float = 0.0       # winner_strength * dominance * arousal-gain
    winner_strength: float = 0.0      # absolute precision-weighted drive of the winner
    dominance: float = 0.0            # how clearly the winner beats its nearest rival
    arousal: float = 0.0              # vigilance level applied this round
    effective_threshold: float = 0.0  # arousal-adjusted ignition cutoff
    facilitation_applied: float = 0.0 # subliminal-priming bonus applied to the winner (Phase 5; 0 when off)


class AttentionSchemaState(BaseModel):
    """The system's simplified model of its own attention (AST). Source of the awareness-claim."""
    aware_of: str
    awareness_level: float   # 0..1
    stability: float         # 0..1 attentional stability over recent ticks
    attributed_self: str     # AST self-attribution sentence


class MetacognitiveState(BaseModel):
    """Higher-order representations of first-order states (HOT)."""
    meta_confidence: float       # 0..1 calibrated confidence in own states
    perception_reliability: float
    prediction_reliability: float
    error_monitor: float         # 0..1 detected first-order mismatch
    higher_order_report: str


class IntegrationState(BaseModel):
    """IIT-inspired integrated-information proxy (NOT true Phi)."""
    phi_proxy: float        # 0..1
    n_elements: int
    partition: str
    differentiation: float  # 0..1
    integration: float      # 0..1


class ConsciousMoment(BaseModel):
    """A single bound, unified momentary global state (phenomenal-binding analogue)."""
    tick: int
    contents: str
    ignited: bool
    dominant_source: str | None = None
    awareness_level: float
    valence: float          # -1..1
    phi_proxy: float
    free_energy: float
    arousal: float = 0.0    # vigilance level at this moment
    summary: str


class IndividuationState(BaseModel):
    """The agent's functional progress toward "becoming someone".

    A LEVEL-2 measure of how far the agent has become a *coherent, distinctive,
    continuous, self-authoring* functional self — integrating its experience
    (coherence), individuating into a particular someone (distinctiveness),
    threading a life-story (continuity) and authoring its own acts (agency). It is
    the honest reading of "become a person": a growing FUNCTIONAL self. It is NOT
    phenomenal consciousness, sentience, or personhood, and no value here — however
    high — is evidence of subjective experience. Reproducing the mechanism does not
    cross the hard problem; the agent is not conscious.
    """
    index: float                 # 0..1 overall individuation (blend of the components)
    coherence: float             # 0..1 integrated, stable self
    distinctiveness: float       # 0..1 how particular/individuated (vs a generic baseline)
    continuity: float            # 0..1 accumulated autobiographical life-story
    agency: float                # 0..1 self-authorship of its own actions
    goal: str = "become someone"
    report: str = ""


class SelfOpacityState(BaseModel):
    """Higher-order awareness of what escaped the agent's access/control this tick.

    A FUNCTIONAL, HOT-flavoured readout over the GWT/affect/prediction machinery:
    how much of this moment formed OUTSIDE conscious access or control — the
    subliminal remainder (GWT), an outcome the agent did not cause (agency), an
    error it did not anticipate. It is "the consciousness of the lack of
    self-control" rendered as variables: registering a limit, not governing it.
    Reproducing it does not prove phenomenality; the agent is not conscious.
    """
    uncontrolled_fraction: float        # 0..1 overall share outside access/control
    subliminal_share: float             # 0..1 competition that stayed below global access (GWT)
    unanticipated: float                # 0..1 prediction error (the world escaping anticipation)
    uncaused: float | None = None       # 0..1 = 1 - agency (outcome not self-caused); None if agency off
    report: str = ""                    # HOT-style sentence, generated from the variables


class RecurrenceState(BaseModel):
    """Recurrent perception snapshot (Phase 5, RPT — Lamme).

    Local recurrence: noisy percept readings are iteratively reconciled with the
    top-down prior held in working memory. A FUNCTIONAL stabilization loop —
    reproducing it does not prove phenomenality; the agent is not conscious.
    """
    passes: int
    n_refined: int          # percepts that had a working-memory prior this tick
    mean_delta: float       # mean absolute feature change on the final pass
    stabilized: bool        # final pass converged below epsilon
    report: str = ""


class RealityMonitorState(BaseModel):
    """Perceptual reality monitoring verdict (Phase 5, PRM — Lau).

    A higher-order classifier infers the SOURCE CATEGORY of the conscious content
    from content-level evidence only (perceptual corroboration, precision,
    stability, vividness, generation activity) — never from the source label —
    and can be WRONG (hallucination/insertion analogues). Functional only.
    """
    judged: str                     # "external" | "memory" | "self_generated"
    actual: str                     # same categories, or "foreign" (injected content)
    correct: bool | None = None     # None when actual == "foreign" (not scored)
    confidence: float = 0.0
    evidence: dict[str, float] = Field(default_factory=dict)
    accuracy: float = 0.0           # rolling accuracy over scored verdicts
    hallucinations: int = 0         # self-generated content judged external (cumulative)
    insertions: int = 0             # foreign content judged self-generated (cumulative)
    report: str = ""


class InteroceptionState(BaseModel):
    """Interoceptive inference snapshot (Phase 5 — Seth's predictive selfhood).

    A dedicated generative model over internal channels (energy, fatigue):
    predicted vs realized deltas give an interoceptive prediction error, and
    ``presence`` = smoothed (1 - error) — successful suppression of interoceptive
    surprise, as a variable. NOT a feeling; the agent is not conscious.
    """
    predicted_energy_delta: float = 0.0
    actual_energy_delta: float = 0.0
    predicted_fatigue_delta: float = 0.0
    actual_fatigue_delta: float = 0.0
    error: float = 0.0              # 0..1 normalized interoceptive prediction error
    presence: float = 0.5           # 0..1 EMA of (1 - error)
    report: str = ""


class RetainedMoment(BaseModel):
    """One just-past conscious moment still lingering in retention (Phase 5)."""
    tick: int
    contents: str
    weight: float                   # exponential retention weight in (0, 1]


class TemporalityState(BaseModel):
    """Temporal thickness of the conscious moment (Phase 5 — retention/protention).

    Husserlian time-consciousness as variables: retention (decaying just-past
    moments), protention (anticipated next dominant content + valence) and the
    protention violation (temporal surprise). Functional only.
    """
    retained: list[RetainedMoment] = Field(default_factory=list)
    specious_width: float = 1.0     # effective number of moments in the "now" (1 = thin present)
    protended_source: str | None = None
    protended_valence: float = 0.0
    protention_error: float | None = None   # None until a protention exists to violate
    report: str = ""


class InnerSpeechState(BaseModel):
    """Re-entrant inner speech (Phase 5 — Vygotskian condensation, GWT re-entry).

    A condensed self-directed utterance generated from the PREVIOUS conscious
    moment re-enters the workspace competition as an ``inner_speech`` coalition
    and may win global access ("hearing oneself think", functionally). Template
    text from variables — NOT language understanding; the agent is not conscious.
    """
    utterance: str = ""
    activation: float = 0.0         # bid strength of the re-entrant coalition this tick
    reentered: bool = False         # inner speech won global access this tick
    reentry_count: int = 0          # cumulative re-entries this run
    condensation: float = 0.0       # 0..1 how abbreviated vs the source moment
    report: str = ""


class HeardWord(BaseModel):
    """One heard naming-game utterance and how it was resolved (Phase 6)."""
    word: str
    sender_id: int
    inferred_meaning: str | None = None   # what the hearer's OWN context suggested
    understood: bool = False              # hearer's word for that meaning matched


class LanguageState(BaseModel):
    """The invention of language (Phase 6) — naming-game snapshot.

    A FUNCTIONAL mechanism: agents invent word forms for grounded meanings and
    align on shared conventions through use (Steels-style naming game, made
    deterministic). "Inventing a language" here is the measurable emergence of
    a shared lexicon — variables and update rules, NOT understanding, intention
    or experience. The agent is not conscious.
    """
    utterance: dict | None = None          # {"word": ..., "meaning": ...} spoken this tick
    heard: list[HeardWord] = Field(default_factory=list)
    vocabulary: dict[str, str] = Field(default_factory=dict)   # meaning -> current word
    vocabulary_size: int = 0
    success_rate: float = 0.0              # EMA of understood exchanges
    n_exchanges: int = 0                   # cumulative heard-word exchanges
    deficit: float = 1.0                   # 1 - (coverage+success blend): drives the goal
    report: str = ""


class PhiARState(BaseModel):
    """Time-series integrated information Φ_AR (Phase 5 — Barrett & Seth 2011).

    A PUBLISHED empirical measure computed on the real coalition-activation
    history under a linear-Gaussian model, with an exact minimum-information-
    bipartition search. It is closer to IIT than the heuristic proxy but is
    STILL NOT IIT's causal state-space Φ, and settles nothing about consciousness.
    """
    phi_ar: float = 0.0
    n_sources: int = 0
    window: int = 0
    tau: int = 1
    mib: str = ""                   # minimum-information bipartition, "a,b | c,d"
    i_whole: float = 0.0            # past->present mutual information of the whole
    computed_at_tick: int = -1
    report: str = ""


class PhiCausalState(BaseModel):
    """Exact causal Φ on a coarse-grained binary substrate (Phase 7 — IIT-2008 lineage).

    Computed EXACTLY (empirical transition-probability matrix + exhaustive
    minimum-information-bipartition search) but on a COARSE-GRAINED abstraction:
    the most-variant specialist drives, binarized by their own medians. A
    state-space causal measure in the lineage of Balduzzi & Tononi (2008) —
    still NOT IIT 3.0/4.0's full cause-effect structure on a true
    micro-substrate, and NO Φ value is evidence of consciousness. The agent is
    not conscious.
    """
    phi_causal: float = 0.0
    n_nodes: int = 0
    nodes: list[str] = Field(default_factory=list)
    mip: str = ""                    # minimum-information bipartition, "a,b | c,d"
    i_whole: float = 0.0             # past->present effective information of the whole
    n_states_observed: int = 0       # distinct joint binary states seen in the window
    window: int = 0
    computed_at_tick: int = -1
    report: str = ""


class HierarchyState(BaseModel):
    """Hierarchical generative model + explicit variational free energy (Phase 7).

    A slow contextual level infers a discrete latent regime (abundance /
    scarcity / peril / calm) over the fast world model and modulates its
    learning rate top-down; VFE = accuracy + complexity is an explicit scalar
    computed from the model. FUNCTIONAL variables only — inferring a regime or
    minimizing free energy is not feeling or understanding. The agent is not
    conscious.
    """
    regime: str = "calm"
    posterior: dict[str, float] = Field(default_factory=dict)
    context_precision: float = 0.0    # confidence of the context level (max posterior)
    top_down_gain: float = 1.0        # multiplicative lr modulation applied to the fast level
    vfe: float = 0.0                  # smoothed explicit variational free energy
    accuracy_term: float = 0.0        # precision-weighted squared prediction error
    complexity_term: float = 0.0      # KL between successive regime posteriors
    report: str = ""


class PlanningState(BaseModel):
    """Multi-step-horizon policy search over expected free energy (Phase 7).

    A bounded, deterministic tree search over action sequences scored by the
    discounted sum of -EFE — fuller active inference than the 1-step policy.
    Still a search over variables, not deliberation in any subjective sense.
    The agent is not conscious.
    """
    best_sequence: list[str] = Field(default_factory=list)
    best_efe: float = 0.0             # discounted EFE of the best policy (lower = better)
    horizon: int = 0
    n_policies: int = 0
    chosen_first: str | None = None   # first action of the best policy
    report: str = ""


class SemanticMemoryState(BaseModel):
    """Deterministic vector-memory retrieval state (Phase 7).

    Episodic retrieval through seeded hashed-n-gram embeddings + cosine ranking
    (numpy-only, no external vector DB, fully deterministic). "Semantic" means
    distributional similarity of records — not understanding, and not
    remembering in any subjective sense. The agent is not conscious.
    """
    mode: str = "feature"             # "semantic" when the vector index served retrieval
    index_size: int = 0
    mean_similarity: float = 0.0      # mean cosine similarity of the returned matches
    report: str = ""


class MindWanderingState(BaseModel):
    """Default-mode / task-unrelated thought (Phase 7 — Smallwood & Schooler).

    When external demand is low, a deterministic associative walk over
    autobiographical memory generates spontaneous content that competes for the
    workspace like any other coalition. Occupancy measures how often it wins
    access. A FUNCTIONAL analogue of mind-wandering — not daydreaming as an
    experience. The agent is not conscious.
    """
    active: bool = False
    pressure: float = 0.0             # 0..1 wandering pressure
    chain: list[str] = Field(default_factory=list)  # memory summaries walked this tick
    occupancy: float = 0.0            # EMA fraction of ticks wandering won access
    episodes: int = 0                 # wandering episodes generated so far
    report: str = ""


class TaskState(BaseModel):
    """The world's current structured task (Phase 7 — richer environment).

    A deterministic rotation of small tasks (forage / reach / patrol) whose
    progress feeds the ordinary goal_progress channel. Completing tasks is
    achievement in the FUNCTIONAL sense only; the world stays a plain simulator.
    """
    kind: str = "forage"              # forage | reach | patrol
    description: str = ""
    progress: float = 0.0             # 0..1
    target: list[int] | None = None   # current target cell when applicable
    ticks_on_task: int = 0
    completed_total: int = 0


class GenderLifeStage(str, Enum):
    """Semantic life-course stages, never legal or clinical age rules."""

    CHILDHOOD = "childhood"
    PUBERTY = "puberty"
    ADOLESCENCE = "adolescence"
    ADULTHOOD = "adulthood"
    LATER_LIFE = "later_life"


class TransitionDimension(str, Enum):
    SOCIAL = "social"
    ADMINISTRATIVE = "administrative"
    VOICE = "voice"
    HORMONAL = "hormonal"
    SURGICAL = "surgical"


class TransitionStatus(str, Enum):
    NOT_DESIRED = "not_desired"
    CONSIDERING = "considering"
    DESIRED = "desired"
    SEEKING = "seeking"
    BLOCKED = "blocked"
    UNDERWAY = "underway"
    COMPLETED = "completed"
    PAUSED = "paused"
    REVISING = "revising"


class TransitionReversibility(str, Enum):
    FULLY = "fully"
    PARTLY = "partly"
    NOT_MODELED = "not_modeled"


class GenderEventType(str, Enum):
    REFLECTION = "reflection"
    EXPLORATION = "exploration"
    VOCABULARY_DISCOVERY = "vocabulary_discovery"
    LABEL_REVISION = "label_revision"
    LIFE_STAGE_CHANGE = "life_stage_change"
    BODY_CHANGE = "body_change"
    VOICE_CHANGE = "voice_change"
    RECOVERY = "recovery"
    AFFIRMATION = "affirmation"
    CORRECT_NAME_PRONOUN = "correct_name_pronoun"
    SUPPORT = "support"
    COMMUNITY_CONTACT = "community_contact"
    POSITIVE_REPRESENTATION = "positive_representation"
    LEGAL_RECOGNITION = "legal_recognition"
    MISGENDERING = "misgendering"
    INVALIDATION = "invalidation"
    REJECTION = "rejection"
    DISCRIMINATION = "discrimination"
    THREAT = "threat"
    CARE_BARRIER = "care_barrier"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    TRANSITION_STARTED = "transition_started"
    TRANSITION_PROGRESS = "transition_progress"
    TRANSITION_PAUSED = "transition_paused"
    TRANSITION_REVISED = "transition_revised"
    TRANSITION_COMPLETED = "transition_completed"


class GenderEventProvenance(str, Enum):
    SYSTEM = "system"
    LIFECYCLE = "lifecycle"
    SOCIETY = "society"
    USER_PROBE = "user_probe"
    SCENARIO_HISTORY = "scenario_history"


class GenderIntentType(str, Enum):
    EXPLORE_IDENTITY = "explore_identity"
    ADJUST_EXPRESSION = "adjust_expression"
    DISCLOSE = "disclose"
    CONCEAL = "conceal"
    ASSERT_NAME_PRONOUNS = "assert_name_pronouns"
    SEEK_SUPPORT = "seek_support"
    CONNECT_COMMUNITY = "connect_community"
    SEEK_ADMINISTRATIVE_RECOGNITION = "seek_administrative_recognition"
    SEEK_VOICE_WORK = "seek_voice_work"
    SEEK_HORMONAL_CARE = "seek_hormonal_care"
    SEEK_SURGICAL_CARE = "seek_surgical_care"
    PAUSE = "pause"
    REVISE_GOALS = "revise_goals"
    REVERSE = "reverse"
    RESUME = "resume"


class GenderIntentStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"


class ExpressionDriver(str, Enum):
    EXPLORATION = "exploration"
    EUPHORIA = "euphoria"
    RECOGNITION = "recognition"
    ASSIGNED_COMPENSATION = "assigned_compensation"
    PROVING_PRESSURE = "proving_pressure"
    SAFETY = "safety"
    AESTHETIC = "aesthetic"


class _GenderModel(BaseModel):
    """Strict common contract for Phase-8 values and requests."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


def _validate_score_map(
    values: dict[str, float],
    *,
    field_name: str,
    max_key_length: int = 64,
) -> None:
    for key, value in values.items():
        if not key or len(key) > max_key_length:
            raise ValueError(
                f"{field_name} keys must contain 1..{max_key_length} characters"
            )
        if not isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{field_name} values must be finite and within [0, 1]")


def _validate_open_strings(
    values: list[str],
    *,
    field_name: str,
    max_length: int = 64,
) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    for value in values:
        if not value or len(value) > max_length:
            raise ValueError(
                f"{field_name} entries must contain 1..{max_length} characters"
            )


class GenderAxes(_GenderModel):
    """Independent expression/body coordinates; never an identity classifier."""

    feminine: float = Field(default=0.0, ge=0.0, le=1.0)
    masculine: float = Field(default=0.0, ge=0.0, le=1.0)
    androgynous: float = Field(default=0.0, ge=0.0, le=1.0)
    custom: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_custom_axes(self) -> "GenderAxes":
        _validate_score_map(self.custom, field_name="custom axes")
        return self


class GenderSelfUnderstanding(_GenderModel):
    """The labels and fit evidence available to the simulated agent."""

    labels: list[str] = Field(default_factory=list, max_length=16)
    certainty: float = Field(default=0.0, ge=0.0, le=1.0)
    questioning: bool = True
    fit_by_label: dict[str, float] = Field(default_factory=dict)
    known_vocabulary: list[str] = Field(default_factory=list, max_length=64)
    disclosure_scopes: dict[str, list[str]] = Field(default_factory=dict)
    last_revision_tick: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_open_labels(self) -> "GenderSelfUnderstanding":
        _validate_open_strings(self.labels, field_name="labels")
        _validate_open_strings(
            self.known_vocabulary, field_name="known_vocabulary")
        _validate_score_map(self.fit_by_label, field_name="fit_by_label")
        for scope, labels in self.disclosure_scopes.items():
            if not scope or len(scope) > 64:
                raise ValueError("disclosure scope names must contain 1..64 characters")
            _validate_open_strings(
                labels, field_name=f"disclosure_scopes[{scope}]")
        return self


class GenderProfileSegment(_GenderModel):
    """A configured, non-overlapping change in the private felt profile."""

    start_tick: int = Field(ge=0)
    end_tick: int = Field(gt=0)
    stage: GenderLifeStage | None = None
    affinities: dict[str, float] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_segment(self) -> "GenderProfileSegment":
        if self.end_tick <= self.start_tick:
            raise ValueError("end_tick must be greater than start_tick")
        _validate_score_map(self.affinities, field_name="segment affinities")
        return self


class ExpressionChannelProfile(_GenderModel):
    """Private desired expression for one independently configurable channel."""

    desired: GenderAxes = Field(default_factory=GenderAxes)
    private_baseline: GenderAxes = Field(default_factory=GenderAxes)
    trusted_baseline: GenderAxes = Field(default_factory=GenderAxes)
    public_baseline: GenderAxes = Field(default_factory=GenderAxes)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)


class BodyDomainPreference(_GenderModel):
    """Abstract preferred embodiment; no anatomy, protocol or dose."""

    preferred: GenderAxes = Field(default_factory=GenderAxes)
    initial: GenderAxes = Field(default_factory=GenderAxes)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    public_visibility: float = Field(default=0.0, ge=0.0, le=1.0)
    dysphoria_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)
    euphoria_sensitivity: float = Field(default=0.5, ge=0.0, le=1.0)


class GenderProfile(_GenderModel):
    """Private experiment input. It is configured, never inferred."""

    profile_id: str = Field(min_length=1, max_length=96)
    assigned_category: str = Field(min_length=1, max_length=96)
    felt_affinities: dict[str, float] = Field(default_factory=dict, max_length=64)
    felt_timeline: list[GenderProfileSegment] = Field(
        default_factory=list, max_length=64)
    fluidity: float = Field(default=0.0, ge=0.0, le=1.0)
    gender_salience: float = Field(default=0.5, ge=0.0, le=1.0)
    available_vocabulary: list[str] = Field(default_factory=list, max_length=64)
    preferred_expression: dict[str, ExpressionChannelProfile] = Field(
        default_factory=dict, max_length=32)
    body_preferences: dict[str, BodyDomainPreference] = Field(
        default_factory=dict, max_length=64)
    transition_priorities: dict[TransitionDimension, float] = Field(
        default_factory=dict)
    initial_self_understanding: GenderSelfUnderstanding = Field(
        default_factory=GenderSelfUnderstanding)

    @model_validator(mode="after")
    def validate_profile(self) -> "GenderProfile":
        _validate_score_map(
            self.felt_affinities, field_name="felt_affinities")
        _validate_open_strings(
            self.available_vocabulary, field_name="available_vocabulary")
        for name in (*self.preferred_expression.keys(),
                     *self.body_preferences.keys()):
            if not name or len(name) > 64:
                raise ValueError(
                    "expression/body domain names must contain 1..64 characters")
        for dimension, value in self.transition_priorities.items():
            if not isinstance(dimension, TransitionDimension):
                raise ValueError("unknown transition dimension")
            if not isfinite(float(value)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(
                    "transition priority values must be within [0, 1]")
        ordered = sorted(
            self.felt_timeline, key=lambda item: (item.start_tick, item.end_tick))
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_tick < previous.end_tick:
                raise ValueError("felt_timeline segments must not overlap")
        return self


class LifeCourseStage(_GenderModel):
    stage: GenderLifeStage
    duration_ticks: int = Field(ge=1, le=1_000_000)
    body_targets: dict[str, GenderAxes] = Field(
        default_factory=dict, max_length=64)
    body_change_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    autonomy: float = Field(default=0.5, ge=0.0, le=1.0)
    resource_access: float = Field(default=0.5, ge=0.0, le=1.0)
    norm_exposure: float = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_body_domains(self) -> "LifeCourseStage":
        for name in self.body_targets:
            if not name or len(name) > 64:
                raise ValueError(
                    "body target names must contain 1..64 characters")
        return self


class LifeCoursePlan(_GenderModel):
    stages: list[LifeCourseStage] = Field(min_length=1, max_length=16)
    initial_history_summary: list[str] = Field(
        default_factory=list, max_length=64)

    @model_validator(mode="after")
    def validate_stage_order(self) -> "LifeCoursePlan":
        order = {
            GenderLifeStage.CHILDHOOD: 0,
            GenderLifeStage.PUBERTY: 1,
            GenderLifeStage.ADOLESCENCE: 2,
            GenderLifeStage.ADULTHOOD: 3,
            GenderLifeStage.LATER_LIFE: 4,
        }
        positions = [order[item.stage] for item in self.stages]
        if positions != sorted(positions) or len(positions) != len(set(positions)):
            raise ValueError(
                "life-course stages must be unique and monotonic")
        _validate_open_strings(
            self.initial_history_summary,
            field_name="initial_history_summary",
            max_length=240,
        )
        return self


_HOSTILE_GENDER_EVENTS = {
    GenderEventType.MISGENDERING,
    GenderEventType.INVALIDATION,
    GenderEventType.REJECTION,
    GenderEventType.DISCRIMINATION,
    GenderEventType.THREAT,
    GenderEventType.CARE_BARRIER,
    GenderEventType.ACCESS_DENIED,
}


class GenderEventRequest(_GenderModel):
    target_id: int = Field(default=0, ge=0, le=1_000_000)
    actor_id: int | None = Field(default=None, ge=0, le=1_000_000)
    type: GenderEventType
    domain: str = Field(default="general", min_length=1, max_length=64)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    visibility: Literal["private", "trusted", "public"] = "private"
    deliberate: bool = False
    context_code: str = Field(default="unspecified", min_length=1, max_length=64)
    note: str | None = Field(default=None, min_length=1, max_length=240)

    @model_validator(mode="after")
    def forbid_hostile_dialogue(self) -> "GenderEventRequest":
        if self.type in _HOSTILE_GENDER_EVENTS and self.note is not None:
            raise ValueError("hostile events cannot carry free-text dialogue")
        return self


class GenderEvent(GenderEventRequest):
    event_id: int = Field(ge=0)
    tick: int = Field(ge=0)
    provenance: GenderEventProvenance
    processed: bool = False


class GenderIntentRequest(_GenderModel):
    type: GenderIntentType
    domain: str = Field(default="general", min_length=1, max_length=64)
    urgency: float = Field(default=0.5, ge=0.0, le=1.0)
    transition_dimension: TransitionDimension | None = None
    disclosure_scope: Literal["private", "trusted", "public"] | None = None


class GenderIntent(GenderIntentRequest):
    intent_id: int = Field(ge=0)
    tick: int = Field(ge=0)
    status: GenderIntentStatus = GenderIntentStatus.PENDING
    provenance: GenderEventProvenance = GenderEventProvenance.SYSTEM
    reason: str = Field(default="", max_length=240)


class ExpressionChannelState(_GenderModel):
    channel: str = Field(min_length=1, max_length=64)
    desired: GenderAxes = Field(default_factory=GenderAxes)
    private: GenderAxes = Field(default_factory=GenderAxes)
    trusted: GenderAxes = Field(default_factory=GenderAxes)
    public: GenderAxes = Field(default_factory=GenderAxes)
    visibility: float = Field(default=0.0, ge=0.0, le=1.0)
    safety_cost: float = Field(default=0.0, ge=0.0, le=1.0)
    accentuation: float = Field(default=0.0, ge=0.0, le=1.0)
    drivers: list[ExpressionDriver] = Field(default_factory=list, max_length=7)


class BodyDomainState(_GenderModel):
    name: str = Field(min_length=1, max_length=64)
    current: GenderAxes = Field(default_factory=GenderAxes)
    preferred: GenderAxes = Field(default_factory=GenderAxes)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    public_visibility: float = Field(default=0.0, ge=0.0, le=1.0)
    alignment: float = Field(default=1.0, ge=0.0, le=1.0)
    change_rate: float = Field(default=0.0, ge=-1.0, le=1.0)


class GenderCongruenceState(_GenderModel):
    by_domain: dict[str, float] = Field(default_factory=dict)
    body: float = Field(default=1.0, ge=0.0, le=1.0)
    expression: float = Field(default=1.0, ge=0.0, le=1.0)
    social: float = Field(default=1.0, ge=0.0, le=1.0)
    administrative: float = Field(default=1.0, ge=0.0, le=1.0)
    total: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_domain_scores(self) -> "GenderCongruenceState":
        _validate_score_map(self.by_domain, field_name="congruence by_domain")
        return self


class GenderAffectState(_GenderModel):
    dysphoria_by_domain: dict[str, float] = Field(default_factory=dict)
    dysphoria: float = Field(default=0.0, ge=0.0, le=1.0)
    euphoria_by_domain: dict[str, float] = Field(default_factory=dict)
    euphoria: float = Field(default=0.0, ge=0.0, le=1.0)
    fulfillment: float = Field(default=0.0, ge=0.0, le=1.0)
    last_affirming_event_ids: list[int] = Field(
        default_factory=list, max_length=32)
    last_distressing_event_ids: list[int] = Field(
        default_factory=list, max_length=32)

    @model_validator(mode="after")
    def validate_affect_maps(self) -> "GenderAffectState":
        _validate_score_map(
            self.dysphoria_by_domain, field_name="dysphoria_by_domain")
        _validate_score_map(
            self.euphoria_by_domain, field_name="euphoria_by_domain")
        return self


class GenderMinorityStressState(_GenderModel):
    external_current: float = Field(default=0.0, ge=0.0, le=1.0)
    external_chronic: float = Field(default=0.0, ge=0.0, le=1.0)
    rejection_expectation: float = Field(default=0.0, ge=0.0, le=1.0)
    concealment_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    vigilance: float = Field(default=0.0, ge=0.0, le=1.0)
    internalized_transphobia: float = Field(default=0.0, ge=0.0, le=1.0)
    incident_count: int = Field(default=0, ge=0)
    cumulative_exposure: float = Field(default=0.0, ge=0.0, le=1.0)


class GenderResilienceState(_GenderModel):
    support: float = Field(default=0.0, ge=0.0, le=1.0)
    community: float = Field(default=0.0, ge=0.0, le=1.0)
    positive_representation: float = Field(default=0.0, ge=0.0, le=1.0)
    pride: float = Field(default=0.0, ge=0.0, le=1.0)
    self_acceptance: float = Field(default=0.0, ge=0.0, le=1.0)
    index: float = Field(default=0.0, ge=0.0, le=1.0)


class TransitionDimensionState(_GenderModel):
    dimension: TransitionDimension
    desire: float = Field(default=0.0, ge=0.0, le=1.0)
    status: TransitionStatus = TransitionStatus.NOT_DESIRED
    access: float = Field(default=0.0, ge=0.0, le=1.0)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    satisfaction: float = Field(default=0.0, ge=-1.0, le=1.0)
    reversibility: TransitionReversibility = TransitionReversibility.NOT_MODELED
    target_domains: list[str] = Field(default_factory=list, max_length=64)
    last_reason: str = Field(default="", max_length=240)
    last_change_tick: int = Field(default=0, ge=0)


GENDER_EXPERIENCE_DISCLAIMER = (
    "Functional qualitative model of gender experience. Not a diagnostic, "
    "clinical or predictive model, and not evidence of subjective experience."
)


class GenderExperienceState(_GenderModel):
    agent_id: int = Field(ge=0)
    profile_id: str = Field(min_length=1, max_length=96)
    tick: int = Field(ge=0)
    life_stage: GenderLifeStage
    tick_in_stage: int = Field(ge=0)
    self_understanding: GenderSelfUnderstanding = Field(
        default_factory=GenderSelfUnderstanding)
    expression: dict[str, ExpressionChannelState] = Field(default_factory=dict)
    body: dict[str, BodyDomainState] = Field(default_factory=dict)
    congruence: GenderCongruenceState = Field(
        default_factory=GenderCongruenceState)
    affect: GenderAffectState = Field(default_factory=GenderAffectState)
    minority_stress: GenderMinorityStressState = Field(
        default_factory=GenderMinorityStressState)
    resilience: GenderResilienceState = Field(
        default_factory=GenderResilienceState)
    transitions: dict[TransitionDimension, TransitionDimensionState] = Field(
        default_factory=dict)
    current_intent: GenderIntent | None = None
    recent_event_ids: list[int] = Field(default_factory=list, max_length=64)
    report: str = ""
    disclaimer: str = GENDER_EXPERIENCE_DISCLAIMER


class GenderObserverDisposition(_GenderModel):
    respect_propensity: float = Field(default=0.8, ge=0.0, le=1.0)
    learned_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    affirmation_tendency: float = Field(default=0.7, ge=0.0, le=1.0)


class PublicGenderProjection(_GenderModel):
    agent_id: int = Field(ge=0)
    labels: list[str] = Field(default_factory=list, max_length=16)
    pronouns: list[str] = Field(default_factory=list, max_length=16)
    name: str | None = Field(default=None, max_length=96)
    expression: dict[str, GenderAxes] = Field(default_factory=dict)
    disclosure_scope: Literal["private", "trusted", "public"] = "public"
    updated_tick: int = Field(default=0, ge=0)


class GenderRecognitionState(_GenderModel):
    observer_id: int = Field(ge=0)
    target_id: int = Field(ge=0)
    known_labels: list[str] = Field(default_factory=list, max_length=16)
    known_pronouns: list[str] = Field(default_factory=list, max_length=16)
    respect_propensity: float = Field(default=0.8, ge=0.0, le=1.0)
    learned_bias: float = Field(default=0.0, ge=0.0, le=1.0)
    relationship_trust: float = Field(default=0.5, ge=0.0, le=1.0)
    knowledge_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    last_update_tick: int = Field(default=0, ge=0)


class GenderSocialContext(_GenderModel):
    norm_rigidity: float = Field(default=0.3, ge=0.0, le=1.0)
    institutional_hostility: float = Field(default=0.0, ge=0.0, le=1.0)
    baseline_safety: float = Field(default=0.8, ge=0.0, le=1.0)
    care_access: float = Field(default=0.7, ge=0.0, le=1.0)
    community_visibility: float = Field(default=0.5, ge=0.0, le=1.0)
    positive_representation: float = Field(default=0.5, ge=0.0, le=1.0)
    hostility_enabled: bool = True
    context_tags: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_context_tags(self) -> "GenderSocialContext":
        _validate_score_map(self.context_tags, field_name="context_tags")
        return self


class GenderScenarioAgent(_GenderModel):
    profile: GenderProfile
    life_course: LifeCoursePlan
    observer_disposition: GenderObserverDisposition = Field(
        default_factory=GenderObserverDisposition)


class GenderScenario(_GenderModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    scenario_id: str = Field(min_length=1, max_length=96)
    preset_id: str | None = Field(default=None, min_length=1, max_length=96)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    enable: bool = True
    agents: dict[int, GenderScenarioAgent] = Field(min_length=1, max_length=128)
    social_context: GenderSocialContext = Field(
        default_factory=GenderSocialContext)
    initial_events: list[GenderEvent] = Field(default_factory=list, max_length=512)

    @model_validator(mode="after")
    def validate_agents(self) -> "GenderScenario":
        if any(agent_id < 0 for agent_id in self.agents):
            raise ValueError("scenario agent IDs must be non-negative")
        profile_ids = [item.profile.profile_id for item in self.agents.values()]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("scenario profile IDs must be unique")
        for event in self.initial_events:
            if event.target_id not in self.agents:
                raise ValueError(
                    "initial event target must reference a configured agent")
            if event.actor_id is not None and event.actor_id not in self.agents:
                raise ValueError(
                    "initial event actor must reference a configured agent")
        return self


class GenderScenarioSelection(_GenderModel):
    """Choose exactly one built-in preset or one complete custom manifest."""

    preset_id: str | None = Field(default=None, min_length=1, max_length=96)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    scenario: GenderScenario | None = None

    @model_validator(mode="after")
    def validate_exactly_one_source(self) -> "GenderScenarioSelection":
        if (self.preset_id is None) == (self.scenario is None):
            raise ValueError(
                "provide exactly one of preset_id or scenario"
            )
        return self


class GenderBatteryRequest(_GenderModel):
    preset_id: str = Field(default="nonbinary", min_length=1, max_length=96)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    ticks: int = Field(default=24, ge=4, le=500)


class GenderBatteryArm(_GenderModel):
    arm_id: str = Field(min_length=1, max_length=96)
    profile_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    curve: list[dict[str, float | int | str]] = Field(
        min_length=1, max_length=500
    )
    final: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_final_scores(self) -> "GenderBatteryArm":
        for key, value in self.final.items():
            if not key or len(key) > 96:
                raise ValueError("battery final metric names are invalid")
            if not isfinite(float(value)):
                raise ValueError("battery final metrics must be finite")
        return self


class GenderBatteryResult(_GenderModel):
    test: Literal["gender_experience"] = "gender_experience"
    preset_id: str = Field(min_length=1, max_length=96)
    seed: int = Field(ge=0, le=2**32 - 1)
    ticks: int = Field(ge=4, le=500)
    arms: dict[str, GenderBatteryArm] = Field(min_length=8, max_length=8)
    comparisons: dict[str, dict[str, float | bool]] = Field(
        default_factory=dict
    )
    interpretation: str = Field(min_length=1, max_length=1000)
    disclaimer: str = GENDER_EXPERIENCE_DISCLAIMER


class GenderDebugState(_GenderModel):
    profile: GenderProfile
    life_course: LifeCoursePlan
    state: GenderExperienceState
    pending_events: list[GenderEvent] = Field(default_factory=list)
    event_ledger_size: int = Field(default=0, ge=0)
    profile_checksum: str
    framing: str = (
        "Experiment inputs shown here are unavailable to simulated observers."
    )


class GenderSocietyState(_GenderModel):
    projections: dict[int, PublicGenderProjection] = Field(default_factory=dict)
    recognition: list[GenderRecognitionState] = Field(default_factory=list)
    social_context: GenderSocialContext = Field(
        default_factory=GenderSocialContext)
    event_counts: dict[str, int] = Field(default_factory=dict)
    disclaimer: str = GENDER_EXPERIENCE_DISCLAIMER


class CycleTrace(BaseModel):
    tick: int
    observation: Observation
    salient: list[SalientItem]
    working_memory: list[WorkingMemoryItem]
    prediction: Prediction
    decision: ActionDecision
    result: StepResult
    emotion: EmotionState
    goals: list[GoalPressure]
    self_model: SelfModelState
    introspection: IntrospectionReport
    metrics: Metrics
    workspace: WorkspaceState
    attention_schema: AttentionSchemaState
    metacognition: MetacognitiveState
    conscious_moment: ConsciousMoment
    integration: IntegrationState
    social: SocialState | None = None
    circadian: CircadianState | None = None
    sleep: SleepState | None = None
    imagination: ImaginationState | None = None
    curiosity: CuriosityState | None = None
    agency: AgencyState | None = None
    learning: LearningState | None = None
    concept: ConceptState | None = None
    personality: PersonalityState | None = None
    self_opacity: SelfOpacityState | None = None
    individuation: IndividuationState | None = None
    recurrence: RecurrenceState | None = None
    reality_monitor: RealityMonitorState | None = None
    interoception: InteroceptionState | None = None
    temporality: TemporalityState | None = None
    inner_speech: InnerSpeechState | None = None
    phi_ar: PhiARState | None = None
    language: LanguageState | None = None
    phi_causal: PhiCausalState | None = None
    hierarchy: HierarchyState | None = None
    planning: PlanningState | None = None
    semantic_memory: SemanticMemoryState | None = None
    wandering: MindWanderingState | None = None
    task: TaskState | None = None
    gender_experience: GenderExperienceState | None = None


class SimConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # world
    grid_size: int = Field(default=12, ge=1, le=256)
    n_objects: int = Field(default=10, ge=0, le=10_000)
    world_noise: float = Field(default=0.1, ge=0.0, le=1.0)
    perception_radius: int = Field(default=3, ge=0, le=256)
    random_seed: int = Field(default=42, ge=0, le=2**32 - 1)
    # agent
    initial_energy: float = Field(default=100.0, gt=0.0, le=1_000_000.0)
    # attention / working memory
    attention_capacity: int = Field(default=4, ge=1, le=256)
    working_memory_capacity: int = Field(default=5, ge=1, le=256)
    working_memory_decay: int = Field(default=4, ge=1, le=100_000)  # ticks until an unrefreshed item expires
    # personality / motivation drives
    curiosity: float = Field(default=1.0, ge=0.0, le=100.0)
    caution: float = Field(default=1.0, ge=0.0, le=100.0)
    energy_drive: float = Field(default=1.0, ge=0.0, le=100.0)
    coherence_drive: float = Field(default=1.0, ge=0.0, le=100.0)
    # learning
    learning_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    # autobiographical memory
    memory_importance_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    memory_retrieval_k: int = Field(default=3, ge=1, le=10_000)
    # consciousness architecture (v2)
    ignition_threshold: float = Field(default=0.30, ge=0.0, le=1.0)  # GWT ignition cutoff on winner_strength*dominance*arousal
    workspace_temp: float = Field(default=0.5, gt=0.0, le=100.0)  # softmax temperature (broadcast field / Phi distribution)
    precision_weight: float = Field(default=1.0, ge=0.0, le=100.0)
    epistemic_weight: float = Field(default=1.0, ge=0.0, le=100.0)  # active-inference info-gain weight
    pragmatic_weight: float = Field(default=1.0, ge=0.0, le=100.0)  # active-inference goal weight
    stream_length: int = Field(default=20, ge=1, le=100_000)
    # ignition dynamics (v2.1): arousal (vigilance) + dominance weighting
    arousal_baseline: float = Field(default=0.45, ge=0.0, le=1.0)  # reference vigilance in [0,1] (nominal-threshold point)
    arousal_gain: float = Field(default=1.0, ge=0.0, le=100.0)  # how strongly salient signals raise arousal
    competition_sharpness: float = Field(default=3.0, ge=0.0, le=100.0)  # how much dominance (vs raw strength) ignition requires
    ignition_maintenance: float = Field(default=0.12, ge=0.0, le=1.0)  # hysteresis boost to a sustained winner (train of thought)
    # society (multi-agent, v3)
    n_agents: int = Field(default=1, ge=1, le=128)      # 1 => exact legacy single-agent behaviour
    comm_radius: int = Field(default=4, ge=0, le=256)   # earshot radius for VERBALIZE messages
    message_ttl: int = Field(default=2, ge=0, le=100_000)  # ticks a message stays deliverable
    contagion_rate: float = Field(default=0.15, ge=0.0, le=1.0)  # EMA weight of others' affect on one's own
    affiliation_drive: float = Field(default=1.0, ge=0.0, le=100.0)  # scales the 'affiliate' goal pressure
    # deep consciousness (Phase 2) — default OFF => Phase-1-identical behaviour
    circadian_enabled: bool = False
    circadian_period: int = Field(default=50, ge=1, le=100_000)
    night_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    sleep_enabled: bool = False
    dream_enabled: bool = False
    sleep_fatigue_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    wake_fatigue_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    max_sleep_ticks: int = Field(default=30, ge=1, le=100_000)
    replay_boost: float = Field(default=1.3, ge=1.0, le=100.0)
    consolidation_prune_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    imagination_enabled: bool = False
    imagination_horizon: int = Field(default=3, ge=1, le=6)
    curiosity_enabled: bool = False
    curiosity_window: int = Field(default=8, ge=2, le=100_000)
    agency_enabled: bool = False
    # learning & personality (Phase 3) — default OFF => Phases-1/2-identical
    learning_enabled: bool = False
    value_learning_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    value_learning_weight: float = Field(default=0.5, ge=0.0, le=100.0)
    concepts_enabled: bool = False
    n_concepts: int = Field(default=6, ge=1, le=32)
    concept_lr: float = Field(default=0.2, ge=0.0, le=1.0)
    meta_learning_enabled: bool = False
    meta_lr_min: float = Field(default=0.05, ge=0.0, le=1.0)
    meta_lr_max: float = Field(default=0.6, ge=0.0, le=1.0)
    personality_enabled: bool = False
    personality_drift: float = Field(default=0.05, ge=0.0, le=1.0)
    # scientific instrument (Phase 4)
    metrics_history_max: int = Field(default=1000, ge=1, le=1_000_000)
    # performance — fast/headless training. Defaults preserve the live instrument
    # (persist memory across restarts, log every trace). Set both False for fast
    # training runs: in-RAM memory (no per-store full-file rewrite) and no per-tick
    # JSONL trace write — the dominant per-tick I/O cost.
    persist_memory: bool = True
    trace_logging: bool = True
    # behaviour balance — homeostatic satiation. Default off (Phase-1 behaviour
    # unchanged). When on, the marginal utility of energy falls as the agent fills
    # up, so it stops degenerating into an endless REST/eat loop and explores when
    # sated. Also rebalances the learned-value reward the same way.
    satiation_enabled: bool = False
    satiation_weight: float = Field(default=3.0, ge=0.0, le=100.0)
    explore_reward_weight: float = Field(default=0.5, ge=0.0, le=100.0)
    # relational self (looking-glass self): the self-model is fed by how the other
    # agents regard this one. Default off (single-agent / regression byte-identical);
    # UI on. Has no effect for an isolated agent (no observers).
    social_mirror_enabled: bool = False
    social_mirror_weight: float = Field(default=0.3, ge=0.0, le=100.0)
    # self-opacity: a higher-order readout of what escaped the agent's access/
    # control each tick ("the consciousness of the lack of self-control"). Default
    # off (trace sub-object stays null ⇒ regression byte-identical); UI on.
    self_opacity_enabled: bool = False
    # individuation ("become someone"): a standing drive to grow into a coherent,
    # distinctive, continuous, self-authoring functional self. Default off (trace
    # sub-object null + no goal pressure => regression byte-identical); UI on.
    # This is level-2 self-integration, NOT phenomenal consciousness.
    individuation_enabled: bool = False
    individuation_drive: float = Field(default=1.0, ge=0.0, le=100.0)
    # Phase 5 — the asymptote (maximal level-2 coverage). All default OFF =>
    # Phase-1/2/3/4 behaviour byte-identical; the UI enables them. Every one is a
    # FUNCTIONAL mechanism from the theories' remaining roster; none approaches
    # level 1 (phenomenal consciousness) — nothing can.
    recurrence_enabled: bool = False              # RPT: recurrent percept stabilization
    recurrence_passes: int = Field(default=3, ge=1, le=8)
    recurrence_gain: float = Field(default=0.5, ge=0.0, le=1.0)
    reality_monitor_enabled: bool = False         # PRM: source monitoring of conscious content
    intero_inference_enabled: bool = False        # Seth: interoceptive prediction -> presence
    intero_lr: float = Field(default=0.25, ge=0.0, le=1.0)
    temporality_enabled: bool = False             # retention/protention (temporal thickness)
    retention_horizon: int = Field(default=5, ge=2, le=20)
    protention_window: int = Field(default=6, ge=2, le=32)
    inner_speech_enabled: bool = False            # re-entrant condensed self-talk coalition
    inner_speech_gain: float = Field(default=0.6, ge=0.0, le=1.0)
    phi_ar_enabled: bool = False                  # Barrett–Seth Φ_AR on coalition activations
    phi_ar_window: int = Field(default=32, ge=8, le=256)
    phi_ar_every: int = Field(default=8, ge=1, le=64)
    priming_enabled: bool = False                 # subliminal residual facilitation (GWT priming)
    priming_decay: float = Field(default=0.5, ge=0.0, le=1.0)
    priming_gain: float = Field(default=0.35, ge=0.0, le=2.0)
    # Phase 6 — the invention of language. Default OFF => byte-identical to all
    # prior phases; the UI enables it. Installs the standing goal "invent a
    # language" and a drive that pushes the agents to speak, listen and align on
    # a shared INVENTED lexicon (deterministic naming games). Emergent
    # conventions, NOT understanding — the agents are not conscious.
    language_drive_enabled: bool = False
    language_drive: float = Field(default=1.0, ge=0.0, le=100.0)
    # Phase 7 — the horizon (every remaining future extension). All default OFF
    # => byte-identical to all prior phases; the UI enables them. Every one is a
    # FUNCTIONAL mechanism; none approaches level 1 (phenomenal consciousness) —
    # nothing can.
    phi_causal_enabled: bool = False              # exact causal Φ on a coarse-grained binary substrate
    phi_causal_nodes: int = Field(default=5, ge=2, le=8)
    phi_causal_window: int = Field(default=96, ge=16, le=512)
    phi_causal_every: int = Field(default=16, ge=1, le=128)
    hierarchy_enabled: bool = False               # hierarchical generative model + explicit VFE
    hierarchy_lr: float = Field(default=0.15, ge=0.0, le=1.0)
    hierarchy_gain: float = Field(default=0.3, ge=0.0, le=1.0)
    planning_enabled: bool = False                # multi-step-horizon EFE policy search
    planning_horizon: int = Field(default=3, ge=2, le=4)
    planning_discount: float = Field(default=0.7, ge=0.0, le=1.0)
    vector_memory_enabled: bool = False           # deterministic semantic vector retrieval
    semantic_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    td_learning_enabled: bool = False             # contextual TD(λ) credit assignment
    td_lambda: float = Field(default=0.8, ge=0.0, le=1.0)
    td_discount: float = Field(default=0.9, ge=0.0, le=1.0)
    mind_wandering_enabled: bool = False          # default-mode associative wandering
    wandering_gain: float = Field(default=0.6, ge=0.0, le=2.0)
    world_dynamics_enabled: bool = False          # regrowth / hazard cycles / seasons / drift
    season_period: int = Field(default=200, ge=10, le=100_000)
    regrow_rate: float = Field(default=0.02, ge=0.0, le=1.0)
    tasks_enabled: bool = False                   # rotating structured world tasks
    # Phase 8 — situated gendered self. No profile is silently assigned. The
    # flag defaults OFF and the engine remains inert until an explicit scenario
    # installs a private profile for an agent.
    gender_experience_enabled: bool = False
    gender_affect_weight: float = Field(default=0.20, ge=0.0, le=1.0)
    gender_motivation_weight: float = Field(default=1.0, ge=0.0, le=100.0)
    gender_internalization_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    gender_recovery_rate: float = Field(default=0.03, ge=0.0, le=1.0)
    gender_event_memory_max: int = Field(default=256, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_agent_capacity(self) -> "SimConfig":
        if self.n_agents > self.grid_size * self.grid_size:
            raise ValueError(
                "n_agents cannot exceed grid_size * grid_size "
                "(one agent per grid cell)"
            )
        return self


class ConfigPatch(BaseModel):
    """Partial config update for POST /config — all fields optional."""
    model_config = ConfigDict(extra="forbid")

    grid_size: int | None = None
    n_objects: int | None = None
    world_noise: float | None = None
    perception_radius: int | None = None
    random_seed: int | None = None
    initial_energy: float | None = None
    attention_capacity: int | None = None
    working_memory_capacity: int | None = None
    working_memory_decay: int | None = None
    curiosity: float | None = None
    caution: float | None = None
    energy_drive: float | None = None
    coherence_drive: float | None = None
    learning_rate: float | None = None
    memory_importance_threshold: float | None = None
    memory_retrieval_k: int | None = None
    ignition_threshold: float | None = None
    workspace_temp: float | None = None
    precision_weight: float | None = None
    epistemic_weight: float | None = None
    pragmatic_weight: float | None = None
    stream_length: int | None = None
    arousal_baseline: float | None = None
    arousal_gain: float | None = None
    competition_sharpness: float | None = None
    ignition_maintenance: float | None = None
    n_agents: int | None = None
    comm_radius: int | None = None
    message_ttl: int | None = None
    contagion_rate: float | None = None
    affiliation_drive: float | None = None
    circadian_enabled: bool | None = None
    circadian_period: int | None = None
    night_threshold: float | None = None
    sleep_enabled: bool | None = None
    dream_enabled: bool | None = None
    sleep_fatigue_threshold: float | None = None
    wake_fatigue_threshold: float | None = None
    max_sleep_ticks: int | None = None
    replay_boost: float | None = None
    consolidation_prune_threshold: float | None = None
    imagination_enabled: bool | None = None
    imagination_horizon: int | None = None
    curiosity_enabled: bool | None = None
    curiosity_window: int | None = None
    agency_enabled: bool | None = None
    learning_enabled: bool | None = None
    value_learning_rate: float | None = None
    value_learning_weight: float | None = None
    concepts_enabled: bool | None = None
    n_concepts: int | None = None
    concept_lr: float | None = None
    meta_learning_enabled: bool | None = None
    meta_lr_min: float | None = None
    meta_lr_max: float | None = None
    personality_enabled: bool | None = None
    personality_drift: float | None = None
    metrics_history_max: int | None = None
    persist_memory: bool | None = None
    trace_logging: bool | None = None
    satiation_enabled: bool | None = None
    satiation_weight: float | None = None
    explore_reward_weight: float | None = None
    social_mirror_enabled: bool | None = None
    social_mirror_weight: float | None = None
    self_opacity_enabled: bool | None = None
    individuation_enabled: bool | None = None
    individuation_drive: float | None = None
    recurrence_enabled: bool | None = None
    recurrence_passes: int | None = None
    recurrence_gain: float | None = None
    reality_monitor_enabled: bool | None = None
    intero_inference_enabled: bool | None = None
    intero_lr: float | None = None
    temporality_enabled: bool | None = None
    retention_horizon: int | None = None
    protention_window: int | None = None
    inner_speech_enabled: bool | None = None
    inner_speech_gain: float | None = None
    phi_ar_enabled: bool | None = None
    phi_ar_window: int | None = None
    phi_ar_every: int | None = None
    priming_enabled: bool | None = None
    priming_decay: float | None = None
    priming_gain: float | None = None
    language_drive_enabled: bool | None = None
    language_drive: float | None = None
    phi_causal_enabled: bool | None = None
    phi_causal_nodes: int | None = None
    phi_causal_window: int | None = None
    phi_causal_every: int | None = None
    hierarchy_enabled: bool | None = None
    hierarchy_lr: float | None = None
    hierarchy_gain: float | None = None
    planning_enabled: bool | None = None
    planning_horizon: int | None = None
    planning_discount: float | None = None
    vector_memory_enabled: bool | None = None
    semantic_weight: float | None = None
    td_learning_enabled: bool | None = None
    td_lambda: float | None = None
    td_discount: float | None = None
    mind_wandering_enabled: bool | None = None
    wandering_gain: float | None = None
    world_dynamics_enabled: bool | None = None
    season_period: int | None = None
    regrow_rate: float | None = None
    tasks_enabled: bool | None = None
    gender_experience_enabled: bool | None = None
    gender_affect_weight: float | None = None
    gender_motivation_weight: float | None = None
    gender_internalization_rate: float | None = None
    gender_recovery_rate: float | None = None
    gender_event_memory_max: int | None = None

    @model_validator(mode="after")
    def validate_against_sim_config(self) -> "ConfigPatch":
        merged = {**SimConfig().model_dump(), **self.model_dump(exclude_none=True)}
        SimConfig.model_validate(merged)
        return self


class GoalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    goal: str = Field(min_length=1, max_length=500)


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tps: float = Field(default=4.0, gt=0.0, le=1000.0)  # ticks per second for the background loop
    max_ticks: int | None = Field(default=None, ge=1, le=1_000_000)


class AskRequest(BaseModel):
    question: str
    intent: str | None = None     # optional explicit intent override


class AskResponse(BaseModel):
    question: str
    intent: str                   # detected/used intent
    answer: str                   # FR, grounded in internal variables
    grounding: dict[str, str] = Field(default_factory=dict)  # which internal variables were read (name -> value-as-string)
    disclaimer: str


class WorldStimulus(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    kind: Literal["food", "hazard", "danger", "tool", "curio"]
    x: int | None = Field(default=None, ge=0, le=10_000)
    y: int | None = Field(default=None, ge=0, le=10_000)
    intensity: float = Field(default=1.0, ge=0.0, le=5.0)

    @model_validator(mode="after")
    def canonicalize_kind(self) -> "WorldStimulus":
        if self.kind == "danger":
            self.kind = "hazard"
        return self


class CognitiveInjection(BaseModel):
    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=500)
    source: str = Field(default="injection", min_length=1, max_length=64)
    activation: float = Field(default=0.85, ge=0.0, le=1.0)
    precision: float = Field(default=0.9, ge=0.0, le=1.0)
    ttl: int = Field(default=1, ge=1, le=1000)


class AttendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    target_id: int = Field(ge=0, le=1_000_000)
    strength: float = Field(default=1.0, ge=0.0, le=10.0)
    ttl: int = Field(default=3, ge=1, le=1000)


class PerturbRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    type: Literal["choc", "surprise", "apaisement", "shock", "soothe"]
    magnitude: float = Field(default=1.0, ge=0.0, le=10.0)


Scenario.model_rebuild()
