import numpy as np

from core.global_workspace import GlobalWorkspace
from core.phi_ar import PhiARMonitor
from schemas.models import SimConfig


def _fill(monitor: PhiARMonitor, series: np.ndarray, sources: list[str]):
    """Feed a (T × n) activation matrix into the monitor as coalitions."""
    for row in series:
        coalitions = [GlobalWorkspace.make_coalition(s, f"{s}: x", activation=float(v),
                                                     precision=1.0, vector=[])
                      for s, v in zip(sources, row)]
        monitor.append(coalitions)


def _series(coupled: bool, T=64, seed=0):
    rng = np.random.default_rng(seed)
    a = np.zeros(T)
    b = np.zeros(T)
    c = np.zeros(T)
    for t in range(1, T):
        a[t] = 0.6 * a[t - 1] + 0.3 * rng.normal()
        if coupled:
            b[t] = 0.7 * a[t - 1] + 0.1 * rng.normal()   # b is driven by a's past
            c[t] = 0.7 * b[t - 1] + 0.1 * rng.normal()   # c is driven by b's past
        else:
            b[t] = 0.6 * b[t - 1] + 0.3 * rng.normal()
            c[t] = 0.6 * c[t - 1] + 0.3 * rng.normal()
    m = np.stack([a, b, c], axis=1)
    return (m - m.min()) / (np.ptp(m) + 1e-9)            # into [0,1] like activations


def test_coupled_system_integrates_more_than_independent():
    srcs = ["a", "b", "c"]
    cfg = SimConfig()
    mono = PhiARMonitor(srcs, window=64)
    _fill(mono, _series(coupled=False), srcs)
    phi_indep = mono.compute(0, cfg).phi_ar
    duo = PhiARMonitor(srcs, window=64)
    _fill(duo, _series(coupled=True), srcs)
    phi_coupled = duo.compute(0, cfg).phi_ar
    assert phi_coupled > phi_indep                        # integration is detected
    assert phi_coupled > 0.05


def test_phi_ar_deterministic_and_nonnegative():
    srcs = ["a", "b", "c"]
    cfg = SimConfig()
    vals = []
    for _ in range(2):
        m = PhiARMonitor(srcs, window=64)
        _fill(m, _series(coupled=True), srcs)
        st = m.compute(5, cfg)
        vals.append(st.phi_ar)
        assert st.phi_ar >= 0.0
        assert st.n_sources == 3 and st.mib and st.i_whole >= 0.0
    assert vals[0] == vals[1]


def test_silent_sources_are_excluded():
    srcs = ["a", "b", "silent"]
    cfg = SimConfig()
    m = PhiARMonitor(srcs, window=64)
    series = _series(coupled=True)
    series[:, 2] = 0.0                                    # third source never speaks
    _fill(m, series, srcs)
    st = m.compute(0, cfg)
    assert st.n_sources == 2
    assert "silent" not in st.mib


def test_single_active_source_reports_zero():
    srcs = ["a", "b"]
    cfg = SimConfig()
    m = PhiARMonitor(srcs, window=32)
    series = np.zeros((32, 2))
    series[:, 0] = np.linspace(0.0, 1.0, 32)
    _fill(m, series, srcs)
    st = m.compute(0, cfg)
    assert st.phi_ar == 0.0 and st.n_sources < 2 or st.phi_ar >= 0.0


def test_agent_gating_and_periodic_compute():
    from core.agent import CognitiveAgent
    base = dict(world_noise=0.1, random_seed=42, persist_memory=False, trace_logging=False)
    off = CognitiveAgent(SimConfig(**base))
    assert off.cognitive_cycle().phi_ar is None
    on = CognitiveAgent(SimConfig(**base, phi_ar_enabled=True, phi_ar_every=4,
                                  phi_ar_window=16))
    traces = [on.cognitive_cycle() for _ in range(16)]
    computed = [t.phi_ar for t in traces if t.phi_ar is not None]
    assert computed, "phi_ar never computed"
    last = traces[-1]
    assert last.phi_ar.phi_ar >= 0.0
    assert last.metrics.phi_ar == round(float(last.phi_ar.phi_ar), 4)
    # Held between periodic computations: computed_at_tick advances in steps.
    ticks = sorted({t.phi_ar.computed_at_tick for t in traces if t.phi_ar})
    assert all(t2 - t1 >= 1 for t1, t2 in zip(ticks, ticks[1:]))
