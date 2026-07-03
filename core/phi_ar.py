# core/phi_ar.py
"""Time-series integrated information Φ_AR (Phase 5) — Barrett & Seth (2011).

FUNCTIONAL NOTE (load-bearing): the project's ``phi_proxy`` is an explicitly
declared heuristic. This module adds a PUBLISHED empirical measure from the
integrated-information literature: Φ_AR ("practical measures of integrated
information for time-series data"), computed on the agent's REAL per-source
coalition-activation history under a stationary linear-Gaussian assumption.
Past→present mutual information of the whole system is compared with the sum
over the parts of the MINIMUM-INFORMATION BIPARTITION, found by exact search
over all bipartitions (Balduzzi–Tononi min-entropy normalization for the MIB
selection; the unnormalized value at the MIB is reported, clipped at 0).

Honesty: Φ_AR is *closer* to IIT than the heuristic proxy — and it is STILL NOT
IIT's causal, state-space Φ. It is an empirical time-series measure. No value of
it, however high, is evidence of consciousness; the agent is not conscious.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from core.constants import PHI_AR_MAX_SOURCES, PHI_AR_RIDGE
from schemas.models import Coalition, PhiARState, SimConfig

_MIN_SAMPLES = 10          # minimum history (ticks) before a computation is attempted
_VAR_EPS = 1e-10           # sources with variance below this are treated as silent


def _logdet(mat: np.ndarray) -> float:
    """Robust log-determinant (matrix is ridge-regularized upstream)."""
    sign, val = np.linalg.slogdet(mat)
    if sign <= 0.0:
        return float("-inf")
    return float(val)


def _cov_blocks(past: np.ndarray, present: np.ndarray, ridge: float):
    """Centered covariance blocks (Σ_pp, Σ_cc, Σ_cp) with ridge on the diagonals."""
    t = past.shape[0]
    pc = past - past.mean(axis=0, keepdims=True)
    cc = present - present.mean(axis=0, keepdims=True)
    denom = max(1, t - 1)
    k = past.shape[1]
    spp = pc.T @ pc / denom + ridge * np.eye(k)
    scc = cc.T @ cc / denom + ridge * np.eye(k)
    scp = cc.T @ pc / denom
    return spp, scc, scp


def _gaussian_mi(past: np.ndarray, present: np.ndarray, idx: list[int],
                 ridge: float) -> float:
    """Past→present mutual information of the sub-system ``idx`` (Gaussian)."""
    sub_p = past[:, idx]
    sub_c = present[:, idx]
    spp, scc, scp = _cov_blocks(sub_p, sub_c, ridge)
    k = len(idx)
    cond = scc - scp @ np.linalg.solve(spp, scp.T) + ridge * np.eye(k)
    ld_scc, ld_cond = _logdet(scc), _logdet(cond)
    if not np.isfinite(ld_scc) or not np.isfinite(ld_cond):
        return 0.0
    return float(max(0.0, 0.5 * (ld_scc - ld_cond)))


def _gaussian_entropy(past: np.ndarray, idx: list[int], ridge: float) -> float:
    """Differential entropy of the sub-system's past (Gaussian)."""
    sub = past[:, idx]
    pc = sub - sub.mean(axis=0, keepdims=True)
    denom = max(1, sub.shape[0] - 1)
    k = len(idx)
    cov = pc.T @ pc / denom + ridge * np.eye(k)
    ld = _logdet(cov)
    if not np.isfinite(ld):
        return 0.0
    return float(0.5 * (k * np.log(2.0 * np.pi * np.e) + ld))


class PhiARMonitor:
    """Rolling coalition-activation buffer + exact-MIB Φ_AR computation."""

    def __init__(self, sources: list[str], window: int) -> None:
        self.sources = list(sources)
        self._buffer: deque[np.ndarray] = deque(maxlen=max(_MIN_SAMPLES, int(window)))
        self._last: PhiARState | None = None

    # ------------------------------------------------------------- appending
    def append(self, coalitions: list[Coalition]) -> None:
        """Record this tick's raw per-source drive (activation × precision).

        Must be called BEFORE the workspace competition normalizes activations,
        so the vector reflects each specialist's absolute signal. Non-canonical
        sources (e.g. interactive injections) are ignored; a silent source
        contributes 0.
        """
        row = np.zeros(len(self.sources), dtype=float)
        index = {s: i for i, s in enumerate(self.sources)}
        for c in coalitions:
            i = index.get(c.source)
            if i is not None:
                drive = float(c.activation) * float(c.precision)
                row[i] = max(row[i], drive)
        self._buffer.append(row)

    # ------------------------------------------------------------- computing
    @property
    def last(self) -> PhiARState | None:
        """The most recently computed state (held between periodic computations)."""
        return self._last

    def ready(self) -> bool:
        """Whether enough history has accumulated for a computation."""
        return len(self._buffer) >= _MIN_SAMPLES

    def compute(self, tick: int, config: SimConfig) -> PhiARState:
        """Compute Φ_AR at lag τ=1 over the buffered history (exact MIB search)."""
        data = np.array(self._buffer, dtype=float)
        tau = 1
        past, present = data[:-tau], data[tau:]

        # Active sources only (variance above silence), capped for tractability.
        variances = data.var(axis=0)
        active = [i for i in range(len(self.sources)) if variances[i] > _VAR_EPS]
        active.sort(key=lambda i: float(variances[i]), reverse=True)
        active = sorted(active[:PHI_AR_MAX_SOURCES])
        n = len(active)
        if n < 2:
            state = PhiARState(
                phi_ar=0.0, n_sources=n, window=len(self._buffer), tau=tau,
                mib="", i_whole=0.0, computed_at_tick=int(tick),
                report=("Φ_AR: fewer than two active sources in the window — "
                        "integration undefined, reported as 0. (Barrett–Seth Φ_AR; "
                        "not IIT's causal Φ; not evidence of consciousness.)"))
            self._last = state
            return state

        ridge = PHI_AR_RIDGE
        i_whole = _gaussian_mi(past, present, active, ridge)

        # Exact bipartition search; bit 0 fixed in part 1 to skip mirror duplicates.
        best_norm = float("inf")
        best_phi = 0.0
        best_parts: tuple[list[int], list[int]] = ([], [])
        for mask in range(1, 2 ** n - 1):
            if not (mask & 1):
                continue
            part1 = [active[j] for j in range(n) if (mask >> j) & 1]
            part2 = [active[j] for j in range(n) if not ((mask >> j) & 1)]
            phi_p = i_whole - _gaussian_mi(past, present, part1, ridge) \
                            - _gaussian_mi(past, present, part2, ridge)
            k_p = min(_gaussian_entropy(past, part1, ridge),
                      _gaussian_entropy(past, part2, ridge))
            normalized = phi_p / k_p if k_p > 1e-9 else phi_p
            if normalized < best_norm:
                best_norm = normalized
                best_phi = phi_p
                best_parts = (part1, part2)

        phi = float(max(0.0, best_phi))
        name = lambda idx: ",".join(self.sources[i] for i in idx)  # noqa: E731
        mib = f"{name(best_parts[0])} | {name(best_parts[1])}"
        state = PhiARState(
            phi_ar=round(phi, 6),
            n_sources=n,
            window=len(self._buffer),
            tau=tau,
            mib=mib,
            i_whole=round(float(i_whole), 6),
            computed_at_tick=int(tick),
            report=(f"Φ_AR = {phi:.4f} over {n} active sources ({len(self._buffer)} ticks, τ=1); "
                    f"minimum-information bipartition: [{mib}]. Empirical time-series "
                    "integrated information (Barrett & Seth 2011) — NOT IIT's causal Φ, "
                    "and not evidence of consciousness."),
        )
        self._last = state
        return state
