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

# === Society (multi-agent, v3) ===
# Smoothing weights for the social layer (bounded EMA updates).
CONTAGION_EMA: float = 0.15     # default; SimConfig.contagion_rate overrides per run
TRUST_EMA: float = 0.25         # how fast reputation moves toward observed reward sign
FAMILIARITY_EMA: float = 0.30   # how fast familiarity saturates with exposure
SOCIAL_PERCEPT_NORM: float = 1.0  # reserved scale for social salience normalization
