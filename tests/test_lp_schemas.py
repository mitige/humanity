from schemas.models import LearningState, ConceptState, PersonalityState, SimConfig
from core.constants import WORKSPACE_SOURCES


def test_states_default_safely():
    assert LearningState().q_values == {} and LearningState().effective_lr == 0.2
    assert ConceptState().dominant_concept is None and ConceptState().n_concepts == 0
    assert PersonalityState().label == "nascent" and PersonalityState().caution == 0.5


def test_config_defaults_disable_phase3():
    cfg = SimConfig()
    for flag in ("learning_enabled", "concepts_enabled", "meta_learning_enabled", "personality_enabled"):
        assert getattr(cfg, flag) is False
    assert cfg.n_concepts == 6 and cfg.value_learning_rate == 0.2


def test_concept_workspace_source():
    assert "concept" in WORKSPACE_SOURCES
