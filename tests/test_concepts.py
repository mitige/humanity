from core.concepts import ConceptFormation
from schemas.models import SimConfig


def _cfg(**kw):
    return SimConfig(**{"concepts_enabled": True, "n_concepts": 4, "concept_lr": 0.2, **kw})


def test_disabled_is_neutral():
    c = ConceptFormation(SimConfig())
    st = c.observe([0.1, 0.2, 0.3], SimConfig(concepts_enabled=False))
    assert st.dominant_concept is None and st.n_concepts == 0


def test_distinct_percepts_form_distinct_concepts_then_assign():
    c = ConceptFormation(_cfg())
    a1 = c.observe([1.0, 0.0, 0.0], _cfg())
    b1 = c.observe([0.0, 1.0, 0.0], _cfg())
    assert a1.dominant_concept == 0 and b1.dominant_concept == 1
    a2 = c.observe([0.95, 0.02, 0.0], _cfg())
    assert a2.dominant_concept == 0 and a2.n_concepts == 2
    assert a2.match > 0.5


def test_capacity_caps_concept_count_and_is_deterministic():
    cfg = _cfg(n_concepts=2)
    c1, c2 = ConceptFormation(cfg), ConceptFormation(cfg)
    vecs = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0.5, 0.5, 0.5]]
    out1 = [c1.observe(v, cfg).dominant_concept for v in vecs]
    out2 = [c2.observe(v, cfg).dominant_concept for v in vecs]
    assert out1 == out2
    assert len(c1.prototypes) <= 2
