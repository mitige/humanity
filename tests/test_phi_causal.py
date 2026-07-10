import numpy as np

from core.constants import PHI_CAUSAL_MIN_SAMPLES
from core.global_workspace import GlobalWorkspace
from core.phi_causal import PhiCausalMonitor
from schemas.models import SimConfig


def _fill(monitor: PhiCausalMonitor, series: np.ndarray, sources: list[str]) -> None:
    """Feed a (T x n) drive matrix into the monitor as coalitions."""
    for row in series:
        coalitions = [GlobalWorkspace.make_coalition(s, f"{s}: x", activation=float(v),
                                                     precision=1.0, vector=[])
                      for s, v in zip(sources, row)]
        monitor.append(coalitions)


def _independent(T: int = 200, seed: int = 1) -> np.ndarray:
    """Two independent noise nodes (seeded — deterministic)."""
    rng = np.random.default_rng(seed)
    return rng.uniform(0.0, 1.0, size=(T, 2))


def _coupled(T: int = 200, seed: int = 2) -> np.ndarray:
    """Node B copies node A's previous value; A driven by a deterministic pattern.

    The pattern has exactly T/2 highs so the median binarization recovers it
    (an unbalanced two-valued series with a high majority binarizes to all 0).
    """
    rng = np.random.default_rng(seed)
    bits = rng.permutation(np.array([0, 1] * (T // 2)))
    a = np.where(bits == 1, 0.8, 0.2)
    b = np.zeros(T)
    b[1:] = a[:-1]
    b[0] = 0.2
    return np.stack([a, b], axis=1)


def test_independent_noise_phi_near_zero():
    srcs = ["a", "b"]
    m = PhiCausalMonitor(srcs, window=200)
    _fill(m, _independent(), srcs)
    st = m.compute(0, SimConfig())
    assert st.n_nodes == 2
    assert 0.0 <= st.phi_causal < 0.05


def test_coupled_system_phi_clearly_above_independent():
    srcs = ["a", "b"]
    cfg = SimConfig()
    indep = PhiCausalMonitor(srcs, window=200)
    _fill(indep, _independent(), srcs)
    phi_indep = indep.compute(0, cfg).phi_causal
    coup = PhiCausalMonitor(srcs, window=200)
    _fill(coup, _coupled(), srcs)
    st = coup.compute(0, cfg)
    assert st.phi_causal > phi_indep
    assert st.phi_causal > 0.3            # ~ln 2 expected for a perfect copy link
    assert st.i_whole >= st.phi_causal - 1e-9


def test_deterministic_same_buffer_identical_state():
    srcs = ["a", "b"]
    cfg = SimConfig()
    states = []
    for _ in range(2):
        m = PhiCausalMonitor(srcs, window=200)
        _fill(m, _coupled(), srcs)
        assert m.last is None
        st = m.compute(7, cfg)
        assert m.last == st
        states.append(st)
    assert states[0].model_dump() == states[1].model_dump()


def test_fewer_than_two_active_sources_reports_zero():
    srcs = ["a", "b", "c"]
    m = PhiCausalMonitor(srcs, window=48)
    series = np.zeros((48, 3))
    series[:, 0] = np.linspace(0.0, 1.0, 48)   # only one source ever varies
    _fill(m, series, srcs)
    st = m.compute(3, SimConfig())
    assert st.phi_causal == 0.0
    assert st.n_nodes < 2
    assert st.mip == ""
    assert "fewer than two" in st.report
    assert "not evidence of consciousness" in st.report


def test_ready_gating_at_min_samples():
    srcs = ["a", "b"]
    m = PhiCausalMonitor(srcs, window=96)
    # Feed past the threshold so the in-loop assertion exercises BOTH sides
    # of the flip (False while buffer < MIN, True from exactly MIN onward).
    series = _independent(T=PHI_CAUSAL_MIN_SAMPLES + 8)
    for i, row in enumerate(series):
        assert m.ready() is (i >= PHI_CAUSAL_MIN_SAMPLES)  # buffer holds i rows here
        _fill(m, row[None, :], srcs)
    assert m.ready() is True


def test_compute_on_empty_or_single_sample_buffer_is_safe_and_honest():
    cfg = SimConfig()
    m = PhiCausalMonitor(["a", "b"], window=96)
    st = m.compute(0, cfg)                      # never appended — must not crash
    assert st.phi_causal == 0.0
    assert st.n_nodes == 0 and st.nodes == [] and st.mip == ""
    assert st.window == 0 and st.computed_at_tick == 0
    assert "not evidence of consciousness" in st.report
    assert m.last == st
    _fill(m, np.array([[0.3, 0.9]]), ["a", "b"])
    st1 = m.compute(1, cfg)                     # single sample: no transition
    assert st1.phi_causal == 0.0 and st1.window == 1


def test_mip_string_format_and_node_selection():
    srcs = ["alpha", "beta", "gamma"]
    m = PhiCausalMonitor(srcs, window=200)
    rng = np.random.default_rng(3)
    series = rng.uniform(0.0, 1.0, size=(200, 3))
    _fill(m, series, srcs)
    st = m.compute(11, SimConfig(phi_causal_nodes=2))
    assert st.n_nodes == 2
    assert " | " in st.mip
    left, right = st.mip.split(" | ")
    part_names = [n for side in (left, right) for n in side.split(",")]
    assert left and right
    assert sorted(part_names) == sorted(st.nodes)
    assert set(st.nodes) <= set(srcs)
    assert st.n_states_observed >= 2
    assert st.window == 200 and st.computed_at_tick == 11
    assert "Balduzzi" in st.report and "not" in st.report.lower()
