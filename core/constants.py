"""Shared simulation dynamics constants (single source of truth for action effects)."""
from __future__ import annotations
from schemas.models import ActionType

PASSIVE_ENERGY_DECAY: float = 0.5          # subtracted every tick

ACTION_COSTS: dict[str, float] = {
    ActionType.OBSERVE.value: 0.3,
    ActionType.MOVE.value: 1.0,
    ActionType.APPROACH.value: 1.0,
    ActionType.AVOID.value: 1.0,
    ActionType.INTERACT.value: 1.5,
    ActionType.REST.value: 0.0,
    ActionType.EXPLORE.value: 1.2,
    ActionType.ANALYZE.value: 0.5,
    ActionType.VERBALIZE.value: 0.1,
}

REST_RECOVERY: float = 6.0                 # energy regained by REST (minus its cost)
INTERACT_DANGER_DAMAGE: float = 10.0       # energy lost = object.danger * this on INTERACT
ENERGY_CAP_FACTOR: float = 1.2             # max energy = initial_energy * factor
NOVELTY_DECAY_ON_SEE: float = 0.15         # novelty reduction per observation of an object
NOVELTY_DECAY_ON_INTERACT: float = 0.6     # novelty reduction when interacted with

PREDICTION_DIMS: list[str] = ["energy_delta", "danger", "novelty", "goal_progress"]
EMOTION_EMA: float = 0.5                   # smoothing for emotion update (new weight)
CONFIDENCE_EMA: float = 0.3                # smoothing for self confidence
COHERENCE_WINDOW: int = 12                 # ticks used to compute self-coherence

# === Consciousness architecture (v2) ===
# Specialist processes that can bid for global-workspace access (GWT).
WORKSPACE_SOURCES: list[str] = [
    "perception", "memory", "motivation", "prediction_error",
    "interoception", "metacognition", "communication", "social",
    "imagination", "dream", "concept", "inner_speech", "wandering",
]
SUBLIMINAL_FACTOR: float = 0.3       # broadcast strength multiplier when NOT ignited (subliminal)

# Arousal / vigilance (v2.1), modelled as a bounded [0,1] scalar smoothed over
# time and centered on a resting baseline (SimConfig.arousal_baseline). High
# arousal (danger, novelty, surprise) lowers the effective ignition threshold so
# conscious access is easier; resting arousal keeps it at the nominal threshold.
AROUSAL_FLOOR: float = 0.0
AROUSAL_CEIL: float = 1.0
AROUSAL_EMA: float = 0.5             # smoothing weight for the new arousal target
AROUSAL_THRESHOLD_GAIN: float = 0.3  # how strongly arousal shifts the ignition threshold

# Homeostatic ignition (v2.1): the effective threshold blends the nominal cutoff
# with a running mean of recent ignition scores, so ignition tracks RELATIVE
# prominence (what stands out vs. the agent's own recent baseline). This keeps
# the ignition rate healthy across very different environments (neural-adaptation
# analogue) instead of being all-or-nothing on an absolute scale.
IGNITION_ADAPT: float = 0.60         # 0 = purely absolute threshold, 1 = purely adaptive
IGNITION_SCORE_WINDOW: int = 24      # ticks of ignition-score history for adaptation

THEORY_FRAMING_FR = "Cette version vise une implementation de bonne foi, aussi fidele que possible, des mecanismes que les grandes theories scientifiques de la conscience proposent comme constitutifs ou necessaires : espace de travail global (GWT), schema attentionnel (AST), theories d'ordre superieur (HOT), inference active / energie libre, et information integree (IIT, proxy Phi). C'est une tentative theorique maximale. Elle reste incapable d'etablir la presence d'une experience subjective reelle (le hard problem) : reproduire les mecanismes fonctionnels ne prouve pas la phenomenalite."
THEORY_FRAMING_EN = "This version is a good-faith attempt to implement, as faithfully as tractable, the mechanisms that the major scientific theories of consciousness propose as constitutive or necessary: the global workspace (GWT), the attention schema (AST), higher-order theories (HOT), active inference / free energy, and integrated information (IIT, Phi proxy). It is a maximal theoretical attempt. It still cannot establish the presence of real subjective experience (the hard problem): reproducing functional mechanisms does not prove phenomenality."

# === Phase 5 — the asymptote (maximal level-2 coverage) ===
# Every constant below parameterizes a FUNCTIONAL mechanism; none of them brings
# the project closer to level 1 (phenomenal consciousness) — nothing can.
RECURRENCE_STABLE_EPS: float = 0.005   # final-pass mean delta below which perception counts as stabilized
INTERO_PRESENCE_EMA: float = 0.3       # smoothing of presence = EMA(1 - interoceptive error)
INTERO_ENERGY_SCALE: float = 6.0       # energy-delta scale (REST_RECOVERY) normalizing intero error
INTERO_FATIGUE_SCALE: float = 4.0      # fatigue-delta amplification normalizing intero error
REALITY_ACCURACY_EMA: float = 0.25     # smoothing of the reality-monitor rolling accuracy
REALITY_STABILITY_WINDOW: int = 6      # recent winners considered for the stability cue
TEMPORAL_SURPRISE_GAIN: float = 0.5    # weight of protention violation in the arousal salience
PHI_AR_MAX_SOURCES: int = 12           # cap on sources entering the exact bipartition search
PHI_AR_RIDGE: float = 1e-6             # covariance ridge regularization (determinism/stability)
INNER_SPEECH_PRECISION: float = 0.8    # precision of the re-entrant inner-speech coalition
PRIMING_TRACE_FLOOR: float = 1e-4      # facilitation traces below this are dropped

# === Phase 6 — the invention of language (naming games) ===
# Deterministic Steels-style naming-game dynamics: agents INVENT word forms for
# grounded meanings (the object kinds they actually perceive) and align through
# use. Conventions emerge; nothing here is understanding or experience.
LANGUAGE_MEANINGS: list[str] = ["food", "hazard", "tool", "curio"]
LANGUAGE_SYLLABLES: list[str] = [
    "ka", "mo", "ti", "lu", "re", "so", "na", "vi", "pe", "du", "fa", "gi",
]
LANGUAGE_USE_BOOST: float = 0.06     # entrenchment per own use of a word
LANGUAGE_ADOPT_STRENGTH: float = 0.3 # initial strength of a newly adopted heard word
LANGUAGE_HEAR_BOOST: float = 0.2     # reinforcement when hearing a word one already has
LANGUAGE_INHIBITION: float = 0.15    # lateral inhibition of competing synonyms on alignment
LANGUAGE_HOMONYM_INHIBITION: float = 0.35  # harder inhibition of the SAME word on other meanings
                                           # (else one sound colonizes several meanings for good)
LANGUAGE_SUCCESS_EMA: float = 0.2    # smoothing of the communicative-success rate
LANGUAGE_STRENGTH_FLOOR: float = 0.01  # entries below this are pruned

# === Society (multi-agent, v3) ===
# Smoothing weights for the social layer (bounded EMA updates).
CONTAGION_EMA: float = 0.15     # default; SimConfig.contagion_rate overrides per run
TRUST_EMA: float = 0.25         # how fast reputation moves toward observed reward sign
FAMILIARITY_EMA: float = 0.30   # how fast familiarity saturates with exposure
SOCIAL_PERCEPT_NORM: float = 1.0  # reserved scale for social salience normalization

# === Phase 7 — the horizon (every remaining future extension) ===
# Every constant parameterizes a FUNCTIONAL mechanism; none of them brings the
# project closer to level 1 (phenomenal consciousness) — nothing can.
PHI_CAUSAL_LAPLACE: float = 0.5        # Laplace smoothing of the empirical TPM counts
PHI_CAUSAL_MIN_SAMPLES: int = 24       # ticks of history required before computing Φ_c
HIERARCHY_REGIMES: list[str] = ["abundance", "scarcity", "peril", "calm"]
HIERARCHY_VFE_EMA: float = 0.3         # smoothing of the explicit variational free energy
PLANNING_BRANCH_FIRST: int = 4         # first-step candidates kept in the policy tree
PLANNING_BRANCH_DEEP: int = 4          # branching factor at depths >= 2
PLANNING_BONUS: float = 0.35           # additive policy bonus for the planned best action
VECTOR_DIM_FEATURES: int = 16          # structured-feature block of the embedding
VECTOR_DIM_TEXT: int = 48              # hashed char-3-gram block of the embedding
VECTOR_RECENCY_HALF_LIFE: float = 200.0  # ticks for the recency term to halve
WANDERING_THRESHOLD: float = 0.55      # pressure above which a wandering episode fires
WANDERING_HOPS: int = 2                # associative hops per wandering chain
WANDERING_OCCUPANCY_EMA: float = 0.1   # smoothing of the default-mode occupancy measure
WANDERING_PRECISION: float = 0.5       # precision of the wandering coalition's bids
TASK_SEQUENCE: list[str] = ["forage", "reach", "patrol"]
TASK_FORAGE_COUNT: int = 2             # food items to eat per forage task
TASK_COMPLETION_BONUS: float = 1.0     # goal_progress granted on task completion
DRIFT_EVERY: int = 12                  # ticks between drift steps of a mobile object
