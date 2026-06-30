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
