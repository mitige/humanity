# core/coverage.py
"""Theory-coverage readout (Phase 5) — the honest asymptote panel.

FUNCTIONAL NOTE (load-bearing): this module answers exactly one question — of
the mechanisms that the major scientific theories of consciousness propose as
constitutive or necessary, WHICH ONES does this project implement, and which
are currently ACTIVE in the running configuration? It is a coverage checklist
over level-2 mechanisms. It is NOT a consciousness score, NOT a "distance to
level 1", and no coverage — even 100% — would be evidence of subjective
experience: reproducing the functional mechanisms does not prove phenomenality.
"""
from __future__ import annotations

from schemas.models import SimConfig

COVERAGE_DISCLAIMER = (
    "Functional coverage of the theory roster only: each entry is a level-2 "
    "mechanism (variables and algorithms). Coverage — even complete — is NOT a "
    "measure of consciousness and says nothing about level 1 (phenomenal "
    "experience, the hard problem). The agent is not conscious."
)

# Every theory-proposed mechanism the project implements. ``flag`` is None for
# the always-on core; otherwise the SimConfig field that gates the mechanism.
ROSTER: list[dict] = [
    {"theory": "GWT — Global Workspace (Baars/Dehaene)", "mechanism": "coalition competition, ignition, global broadcast", "module": "core/global_workspace.py", "flag": None},
    {"theory": "AST — Attention Schema (Graziano)", "mechanism": "model of own attention + awareness claim", "module": "core/attention_schema.py", "flag": None},
    {"theory": "HOT — Higher-Order Theories", "mechanism": "higher-order states, calibrated meta-confidence", "module": "core/metacognition.py", "flag": None},
    {"theory": "Active inference / FEP (Friston)", "mechanism": "expected-free-energy minimizing policy", "module": "core/world_model.py + core/policy.py", "flag": None},
    {"theory": "IIT (Tononi) — declared proxy", "mechanism": "heuristic Phi proxy (differentiation × integration)", "module": "core/integration.py", "flag": None},
    {"theory": "IIT-adjacent empirical measure", "mechanism": "time-series integrated information Φ_AR (Barrett & Seth 2011), exact MIB", "module": "core/phi_ar.py", "flag": "phi_ar_enabled"},
    {"theory": "RPT — Recurrent Processing (Lamme)", "mechanism": "recurrent percept stabilization against working-memory priors", "module": "core/recurrence.py", "flag": "recurrence_enabled"},
    {"theory": "PRM — Perceptual Reality Monitoring (Lau)", "mechanism": "higher-order source classification of conscious content (can misattribute)", "module": "core/reality_monitor.py", "flag": "reality_monitor_enabled"},
    {"theory": "Interoceptive inference (Seth)", "mechanism": "dedicated interoceptive generative model; presence = suppressed interoceptive surprise", "module": "core/interoception.py", "flag": "intero_inference_enabled"},
    {"theory": "Temporal thickness (Husserl; specious present)", "mechanism": "retention / protention / temporal surprise over the stream", "module": "core/temporality.py", "flag": "temporality_enabled"},
    {"theory": "Inner speech (Vygotsky) / GWT re-entry", "mechanism": "condensed self-directed utterance re-entering the competition", "module": "core/inner_speech.py", "flag": "inner_speech_enabled"},
    {"theory": "GWT priming corpus", "mechanism": "subliminal residual facilitation without global access", "module": "core/global_workspace.py", "flag": "priming_enabled"},
    {"theory": "Sleep / consolidation / dreaming", "mechanism": "offline replay, pruning, grounded dream recombination", "module": "core/sleep.py", "flag": "sleep_enabled"},
    {"theory": "Circadian modulation of vigilance", "mechanism": "deterministic day/night phase modulating arousal", "module": "core/circadian.py", "flag": "circadian_enabled"},
    {"theory": "Imagination / mental simulation", "mechanism": "bounded world-model rollouts feeding the policy", "module": "core/imagination.py", "flag": "imagination_enabled"},
    {"theory": "Intrinsic motivation (learning progress)", "mechanism": "curiosity / boredom from error dynamics", "module": "core/curiosity.py", "flag": "curiosity_enabled"},
    {"theory": "Sense of agency (comparator model)", "mechanism": "predicted vs actual self-effect", "module": "core/agency.py", "flag": "agency_enabled"},
    {"theory": "Reinforcement of action values", "mechanism": "EMA-learned Q[action] policy bonus", "module": "core/learning.py", "flag": "learning_enabled"},
    {"theory": "Concept formation", "mechanism": "online competitive clustering of percepts", "module": "core/concepts.py", "flag": "concepts_enabled"},
    {"theory": "Meta-learning", "mechanism": "self-tuned learning rate from error dynamics", "module": "core/meta_learning.py", "flag": "meta_learning_enabled"},
    {"theory": "Emergent personality", "mechanism": "experience-driven trait drift with affect bias", "module": "core/personality.py", "flag": "personality_enabled"},
    {"theory": "Theory of mind / social cognition", "mechanism": "OtherMind models, trust, contagion, grounded messages", "module": "core/theory_of_mind.py + core/social_emotion.py", "flag": None},
    {"theory": "Relational self (Cooley/Mead)", "mechanism": "looking-glass overlay from others' regard", "module": "core/social_self.py", "flag": "social_mirror_enabled"},
    {"theory": "Self-opacity (limits of access)", "mechanism": "higher-order readout of what escaped access/control", "module": "core/self_opacity.py", "flag": "self_opacity_enabled"},
    {"theory": "Individuation (narrative self)", "mechanism": "'become someone' drive + index", "module": "core/individuation.py", "flag": "individuation_enabled"},
    {"theory": "Homeostatic satiation", "mechanism": "diminishing marginal utility of energy", "module": "core/policy.py", "flag": "satiation_enabled"},
    {"theory": "Language invention (Steels naming games)", "mechanism": "invented words for grounded meanings; conventions emerge through use", "module": "core/language.py", "flag": "language_drive_enabled"},
    {"theory": "IIT causal Φ — coarse-grained, exact (Balduzzi & Tononi 2008 lineage)", "mechanism": "empirical TPM + exhaustive minimum-information-bipartition over binarized drives", "module": "core/phi_causal.py", "flag": "phi_causal_enabled"},
    {"theory": "Predictive-processing hierarchy (Friston/Clark)", "mechanism": "slow context regime over the fast model + explicit variational free energy", "module": "core/hierarchy.py", "flag": "hierarchy_enabled"},
    {"theory": "Active inference: multi-step policies", "mechanism": "bounded policy-tree search over discounted expected free energy", "module": "core/planning.py", "flag": "planning_enabled"},
    {"theory": "TD credit assignment (eligibility traces)", "mechanism": "contextual TD(λ) action values behind the policy", "module": "core/td_learning.py", "flag": "td_learning_enabled"},
    {"theory": "Default mode / mind-wandering (Smallwood & Schooler)", "mechanism": "associative memory walks compete for the workspace under low demand", "module": "core/mind_wandering.py", "flag": "mind_wandering_enabled"},
    {"theory": "Semantic episodic retrieval", "mechanism": "deterministic vector embeddings; similarity/importance/recency-blended recall", "module": "core/vector_memory.py", "flag": "vector_memory_enabled"},
]


def coverage(config: SimConfig) -> dict:
    """Return the roster with per-mechanism active status for this config."""
    items = []
    active = 0
    for entry in ROSTER:
        flag = entry["flag"]
        is_active = True if flag is None else bool(getattr(config, flag, False))
        if is_active:
            active += 1
        items.append({**entry, "active": is_active})
    return {
        "items": items,
        "active_count": active,
        "total": len(ROSTER),
        "note": ("Every mechanism the major theories propose as constitutive or "
                 "necessary that this project implements, and whether it is active "
                 "in the current configuration."),
        "disclaimer": COVERAGE_DISCLAIMER,
    }
