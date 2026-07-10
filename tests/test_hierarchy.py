# tests/test_hierarchy.py
"""Unit tests for core/hierarchy.py (Phase 7 — slow context level + explicit VFE)."""
from __future__ import annotations

from core.constants import HIERARCHY_REGIMES
from core.hierarchy import HierarchicalModel
from schemas.models import Percept, SimConfig


def _percept(danger: float = 0.0, energy_value: float = 0.0, kind: str = "curio") -> Percept:
    """Minimal percept with the fields the hierarchy actually reads."""
    return Percept(object_id=1, kind=kind, dx=1, dy=0, distance=1.0,
                   danger=danger, novelty=0.0, utility=0.0, energy_value=energy_value)


def _cfg(**overrides) -> SimConfig:
    """SimConfig with the hierarchy enabled and defaults elsewhere."""
    return SimConfig(hierarchy_enabled=True, **overrides)


def test_sustained_danger_drives_peril_and_faster_learning():
    m = HierarchicalModel()
    cfg = _cfg()
    assert m.lr_factor() == 1.0                       # neutral before the first update
    st = None
    for _ in range(40):
        st = m.update([_percept(danger=1.0)], 0.5, [0.5, 0.4, 0.5, 0.6], cfg)
    assert st.regime == "peril"
    assert m.lr_factor() > 1.0
    assert st.top_down_gain == round(m.lr_factor(), 4)
    assert "not conscious" in st.report


def test_rich_food_drives_abundance_and_slower_learning():
    m = HierarchicalModel()
    cfg = _cfg()
    # Some error volatility keeps 'calm' from tying with 'abundance'.
    errors = [0.0, 0.4, 0.0, 0.4, 0.0, 0.4, 0.0, 0.4]
    st = None
    for _ in range(40):
        st = m.update([_percept(energy_value=10.0, kind="food")], 0.1, errors, cfg)
    assert st.regime == "abundance"
    assert m.lr_factor() < 1.0


def test_empty_percepts_and_low_errors_are_calmish_and_near_neutral():
    m = HierarchicalModel()
    cfg = _cfg()
    st = None
    for _ in range(40):
        st = m.update([], 0.05, [0.05] * 8, cfg)
    assert st.regime == "calm"
    assert abs(m.lr_factor() - 1.0) < 0.05


def test_vfe_decays_when_converged_and_flip_raises_complexity():
    m = HierarchicalModel()
    cfg = _cfg()
    states = [m.update([], 0.0, [0.0] * 8, cfg) for _ in range(60)]
    # Zero prediction error + converged posterior => VFE decays toward ~0.
    assert states[-1].vfe < 0.01
    assert states[-1].vfe < states[4].vfe
    settled_complexity = states[-1].complexity_term
    # A sudden regime flip (calm -> danger) raises the complexity term.
    flip = m.update([_percept(danger=1.0)] * 3, 0.0, [0.0] * 8, cfg)
    assert flip.complexity_term > settled_complexity + 1e-4


def test_posterior_is_a_proper_distribution_with_no_dead_regime():
    m = HierarchicalModel()
    cfg = _cfg(hierarchy_lr=0.4)
    scenes = [
        [_percept(danger=1.0)],
        [_percept(energy_value=10.0)],
        [],
        [_percept(danger=0.8), _percept(energy_value=6.0)],
    ]
    for i in range(32):
        st = m.update(scenes[i % len(scenes)], 0.3, [0.1 * (i % 5)] * 8, cfg)
        assert abs(sum(st.posterior.values()) - 1.0) < 1e-3   # rounded to 4 decimals
        assert set(st.posterior) == set(HIERARCHY_REGIMES)
        assert all(v > 0.0 for v in st.posterior.values())    # the 0.15 floor keeps all alive


def test_determinism_same_sequence_twice():
    def run() -> list[dict]:
        m = HierarchicalModel()
        cfg = _cfg()
        out = []
        for i in range(24):
            percepts = [_percept(danger=0.1 * (i % 3), energy_value=float(i % 7))]
            errors = [0.05 * ((i + j) % 4) for j in range(8)]
            out.append(m.update(percepts, 0.2 + 0.01 * (i % 5), errors, cfg).model_dump())
        return out

    assert run() == run()


def test_lr_factor_stays_within_gain_bounds():
    for gain in (0.0, 0.3, 1.0):
        m = HierarchicalModel()
        cfg = _cfg(hierarchy_gain=gain)
        for scene in ([_percept(danger=1.0)] * 5, [_percept(energy_value=10.0)] * 5, []):
            for _ in range(20):
                m.update(list(scene), 0.4, [0.6, 0.1, 0.5, 0.2], cfg)
                assert 1.0 - gain <= m.lr_factor() <= 1.0 + gain
        if gain == 0.0:
            assert m.lr_factor() == 1.0


def test_hostile_inputs_never_poison_the_posterior():
    """Negative danger/energy (Percept fields are unconstrained floats) must not
    produce a negative likelihood: np.power(neg, lr) would NaN the posterior
    permanently. Short/empty recent_errors must also be safe (volatility=0)."""
    m = HierarchicalModel()
    cfg = _cfg()
    hostile = [
        ([_percept(danger=-0.5)], 0.2, []),                    # negative danger, no errors
        ([_percept(energy_value=-30.0)], 0.2, [0.3]),          # negative energy, 1 error
        ([_percept(danger=-2.0, energy_value=-50.0)], 5.0, [0.1, 0.2]),
    ]
    for percepts, pe, errors in hostile:
        st = m.update(percepts, pe, errors, cfg)
        vals = list(st.posterior.values())
        assert all(v == v for v in vals), "posterior contains NaN"
        assert abs(sum(vals) - 1.0) < 1e-3
        assert all(v > 0.0 for v in vals)
        assert 1.0 - cfg.hierarchy_gain <= m.lr_factor() <= 1.0 + cfg.hierarchy_gain
    # And the model recovers normally afterwards: rich food -> abundance.
    st = None
    for _ in range(40):
        st = m.update([_percept(energy_value=10.0)], 0.1,
                      [0.0, 0.4, 0.0, 0.4, 0.0, 0.4, 0.0, 0.4], cfg)
    assert st.regime == "abundance"
