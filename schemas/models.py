from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field


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
    at_tick: int
    type: str  # "stimulus" | "perturb" | "goal" | "inject" | "attend"
    agent_id: int = 0
    params: dict = Field(default_factory=dict)


class Scenario(BaseModel):
    """A declarative, reproducible scenario (Phase 4)."""
    name: str = "scenario"
    config: "ConfigPatch" = Field(default_factory=lambda: ConfigPatch())
    ticks: int = 20
    interventions: list[Intervention] = Field(default_factory=list)
    seed: int | None = None


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


class SimConfig(BaseModel):
    # world
    grid_size: int = 12
    n_objects: int = 10
    world_noise: float = 0.1
    perception_radius: int = 3
    random_seed: int = 42
    # agent
    initial_energy: float = 100.0
    # attention / working memory
    attention_capacity: int = 4
    working_memory_capacity: int = 5
    working_memory_decay: int = 4         # ticks until an unrefreshed item expires
    # personality / motivation drives
    curiosity: float = 1.0
    caution: float = 1.0
    energy_drive: float = 1.0
    coherence_drive: float = 1.0
    # learning
    learning_rate: float = 0.2
    # autobiographical memory
    memory_importance_threshold: float = 0.25
    memory_retrieval_k: int = 3
    # consciousness architecture (v2)
    ignition_threshold: float = 0.30     # GWT ignition cutoff on winner_strength*dominance*arousal
    workspace_temp: float = 0.5          # softmax temperature (broadcast field / Phi distribution)
    precision_weight: float = 1.0
    epistemic_weight: float = 1.0        # active-inference info-gain weight
    pragmatic_weight: float = 1.0        # active-inference goal weight
    stream_length: int = 20
    # ignition dynamics (v2.1): arousal (vigilance) + dominance weighting
    arousal_baseline: float = 0.45       # reference vigilance in [0,1] (nominal-threshold point)
    arousal_gain: float = 1.0            # how strongly salient signals raise arousal
    competition_sharpness: float = 3.0   # how much dominance (vs raw strength) ignition requires
    ignition_maintenance: float = 0.12   # hysteresis boost to a sustained winner (train of thought)
    # society (multi-agent, v3)
    n_agents: int = Field(default=1, ge=1)              # 1 => exact legacy single-agent behaviour
    comm_radius: int = Field(default=4, ge=0)           # earshot radius for VERBALIZE messages
    message_ttl: int = Field(default=2, ge=0)           # ticks a message stays deliverable
    contagion_rate: float = Field(default=0.15, ge=0.0, le=1.0)  # EMA weight of others' affect on one's own
    affiliation_drive: float = Field(default=1.0, ge=0.0)        # scales the 'affiliate' goal pressure
    # deep consciousness (Phase 2) — default OFF => Phase-1-identical behaviour
    circadian_enabled: bool = False
    circadian_period: int = Field(default=50, ge=1)
    night_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    sleep_enabled: bool = False
    dream_enabled: bool = False
    sleep_fatigue_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    wake_fatigue_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    max_sleep_ticks: int = Field(default=30, ge=1)
    replay_boost: float = Field(default=1.3, ge=1.0)
    consolidation_prune_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    imagination_enabled: bool = False
    imagination_horizon: int = Field(default=3, ge=1, le=6)
    curiosity_enabled: bool = False
    curiosity_window: int = Field(default=8, ge=2)
    agency_enabled: bool = False
    # learning & personality (Phase 3) — default OFF => Phases-1/2-identical
    learning_enabled: bool = False
    value_learning_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    value_learning_weight: float = Field(default=0.5, ge=0.0)
    concepts_enabled: bool = False
    n_concepts: int = Field(default=6, ge=1, le=32)
    concept_lr: float = Field(default=0.2, ge=0.0, le=1.0)
    meta_learning_enabled: bool = False
    meta_lr_min: float = Field(default=0.05, ge=0.0, le=1.0)
    meta_lr_max: float = Field(default=0.6, ge=0.0, le=1.0)
    personality_enabled: bool = False
    personality_drift: float = Field(default=0.05, ge=0.0, le=1.0)
    # scientific instrument (Phase 4)
    metrics_history_max: int = Field(default=1000, ge=1)
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
    satiation_weight: float = Field(default=3.0, ge=0.0)
    explore_reward_weight: float = Field(default=0.5, ge=0.0)
    # relational self (looking-glass self): the self-model is fed by how the other
    # agents regard this one. Default off (single-agent / regression byte-identical);
    # UI on. Has no effect for an isolated agent (no observers).
    social_mirror_enabled: bool = False
    social_mirror_weight: float = Field(default=0.3, ge=0.0)
    # self-opacity: a higher-order readout of what escaped the agent's access/
    # control each tick ("the consciousness of the lack of self-control"). Default
    # off (trace sub-object stays null ⇒ regression byte-identical); UI on.
    self_opacity_enabled: bool = False
    # individuation ("become someone"): a standing drive to grow into a coherent,
    # distinctive, continuous, self-authoring functional self. Default off (trace
    # sub-object null + no goal pressure => regression byte-identical); UI on.
    # This is level-2 self-integration, NOT phenomenal consciousness.
    individuation_enabled: bool = False
    individuation_drive: float = Field(default=1.0, ge=0.0)
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
    language_drive: float = Field(default=1.0, ge=0.0)


class ConfigPatch(BaseModel):
    """Partial config update for POST /config — all fields optional."""
    grid_size: int | None = None
    n_objects: int | None = None
    world_noise: float | None = None
    perception_radius: int | None = None
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


class GoalRequest(BaseModel):
    goal: str


class RunRequest(BaseModel):
    tps: float = 4.0          # ticks per second for the background loop
    max_ticks: int | None = None


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
    kind: str                     # "food" | "hazard" | "tool" | "curio"
    x: int | None = None          # default: a free cell near the agent
    y: int | None = None
    intensity: float = 1.0        # scales danger/energy_value/novelty


class CognitiveInjection(BaseModel):
    content: str
    source: str = "injection"     # appears as a coalition source in the workspace
    activation: float = 0.85
    precision: float = 0.9
    ttl: int = 1                  # ticks it remains in competition


class AttendRequest(BaseModel):
    target_id: int
    strength: float = 1.0
    ttl: int = 3


class PerturbRequest(BaseModel):
    type: str                     # "choc" | "surprise" | "apaisement"
    magnitude: float = 1.0


Scenario.model_rebuild()
