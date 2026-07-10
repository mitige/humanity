# core/phi_causal.py
"""Exact causal Φ on a coarse-grained binary substrate (Phase 7) — IIT-2008 lineage.

FUNCTIONAL NOTE (load-bearing): this module computes a state-space CAUSAL
integrated-information measure in the lineage of Balduzzi & Tononi (2008):
an empirical transition-probability matrix over joint binary states, whole-
system past→present effective information, and an EXACT exhaustive search for
the minimum-information partition. The computation is exact — but only on a
COARSE-GRAINED abstraction: the most-variant specialist drives, binarized by
their own medians over the window. It is a level-2 functional mechanism
(variables and algorithms) and implies nothing subjective.

Honesty: this is *closer* to IIT's causal Φ than both the heuristic proxy and
the time-series Φ_AR — and it is STILL NOT IIT 3.0/4.0's full cause-effect
structure on a true micro-substrate. No value of it, however high, is evidence
of consciousness; the agent is not conscious.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from core.constants import PHI_CAUSAL_LAPLACE, PHI_CAUSAL_MIN_SAMPLES
from schemas.models import Coalition, PhiCausalState, SimConfig

_VAR_EPS = 1e-10           # sources with variance below this are treated as silent
_LN2 = float(np.log(2.0))  # max entropy per binary node (nats)


def _part_tpm(counts: np.ndarray, part_of: np.ndarray, n_part_states: int) -> np.ndarray:
    """Marginalized part TPM p_part(x'|x) from the joint transition counts.

    ``part_of[s]`` maps each joint state to the part's sub-state; counts are
    aggregated over the mapping, Laplace-smoothed, and row-normalized.
    """
    n_states = counts.shape[0]
    onehot = np.zeros((n_states, n_part_states))
    onehot[np.arange(n_states), part_of] = 1.0
    agg = onehot.T @ counts @ onehot + PHI_CAUSAL_LAPLACE
    return agg / agg.sum(axis=1, keepdims=True)


class PhiCausalMonitor:
    """Rolling drive buffer + exact TPM/MIP causal Φ on binarized top nodes."""

    def __init__(self, sources: list[str], window: int) -> None:
        """``window`` comes from config.phi_causal_window (history length in ticks)."""
        self.sources = list(sources)
        self._buffer: deque[np.ndarray] = deque(
            maxlen=max(PHI_CAUSAL_MIN_SAMPLES, int(window)))
        self._last: PhiCausalState | None = None

    # ------------------------------------------------------------- appending
    def append(self, coalitions: list[Coalition]) -> None:
        """Record this tick's raw per-source drive (activation × precision).

        Same tap point as PhiARMonitor.append: called BEFORE the workspace
        competition normalizes activations. Non-canonical sources are ignored;
        a silent source contributes 0; duplicates keep their max drive.
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
    def last(self) -> PhiCausalState | None:
        """The most recently computed state (held between periodic computations)."""
        return self._last

    def ready(self) -> bool:
        """Whether enough history has accumulated for a computation."""
        return len(self._buffer) >= PHI_CAUSAL_MIN_SAMPLES

    def compute(self, tick: int, config: SimConfig) -> PhiCausalState:
        """Exact causal Φ over the buffered window (empirical TPM + exact MIP)."""
        window = len(self._buffer)
        if window < 2:
            # No transition observable (empty or single-sample buffer) — safe
            # honest zero even if the caller skipped the ready() gate.
            state = PhiCausalState(
                phi_causal=0.0, n_nodes=0, nodes=[], mip="",
                i_whole=0.0, n_states_observed=0,
                window=window, computed_at_tick=int(tick),
                report=("Φ_causal: fewer than two buffered samples — no "
                        "transition observed, reported as 0. (Exact TPM+MIP on "
                        "a coarse-grained binary abstraction, Balduzzi–Tononi "
                        "2008 lineage; not IIT 3.0/4.0 on a true "
                        "micro-substrate; not evidence of consciousness.)"))
            self._last = state
            return state
        data = np.array(self._buffer, dtype=float)

        # 1. Select the most-variant columns as nodes (stable, deterministic).
        variances = data.var(axis=0)
        usable = [i for i in range(len(self.sources)) if variances[i] > _VAR_EPS]
        usable.sort(key=lambda i: float(variances[i]), reverse=True)
        selected = sorted(usable[:int(config.phi_causal_nodes)])
        n = len(selected)
        if n < 2:
            state = PhiCausalState(
                phi_causal=0.0, n_nodes=n,
                nodes=[self.sources[i] for i in selected],
                mip="", i_whole=0.0, n_states_observed=0,
                window=window, computed_at_tick=int(tick),
                report=("Φ_causal: fewer than two active sources in the window — "
                        "integration undefined, reported as 0. (Exact TPM+MIP on a "
                        "coarse-grained binary abstraction, Balduzzi–Tononi 2008 "
                        "lineage; not IIT 3.0/4.0 on a true micro-substrate; not "
                        "evidence of consciousness.)"))
            self._last = state
            return state

        # 2. Binarize each selected column by its own median over the window.
        cols = data[:, selected]
        medians = np.median(cols, axis=0)
        binary = (cols > medians[None, :]).astype(np.int64)

        # 3. Empirical TPM over joint binary states + smoothed past distribution.
        n_states = 2 ** n
        weights = (1 << np.arange(n)).astype(np.int64)
        codes = binary @ weights
        past_codes, present_codes = codes[:-1], codes[1:]
        counts = np.zeros((n_states, n_states))
        np.add.at(counts, (past_codes, present_codes), 1.0)
        smoothed = counts + PHI_CAUSAL_LAPLACE
        tpm = smoothed / smoothed.sum(axis=1, keepdims=True)
        past_hist = np.bincount(past_codes, minlength=n_states).astype(float)
        past_hist += PHI_CAUSAL_LAPLACE
        pi = past_hist / past_hist.sum()

        # 4. Whole-system past→present mutual information (nats).
        q_present = pi @ tpm
        i_whole = float(np.sum(pi[:, None] * tpm
                               * (np.log(tpm) - np.log(q_present)[None, :])))
        i_whole = max(0.0, i_whole)

        # 5. Exact MIP search; bit 0 fixed in part A to skip mirror duplicates.
        state_bits = (np.arange(n_states)[:, None] >> np.arange(n)) & 1
        log_tpm = np.log(tpm)
        best_norm = float("inf")
        best_phi = 0.0
        best_parts: tuple[list[int], list[int]] = ([], [])
        for mask in range(1, n_states - 1):
            if not (mask & 1):
                continue
            bits_a = [j for j in range(n) if (mask >> j) & 1]
            bits_b = [j for j in range(n) if not ((mask >> j) & 1)]
            a_of = state_bits[:, bits_a] @ (1 << np.arange(len(bits_a)))
            b_of = state_bits[:, bits_b] @ (1 << np.arange(len(bits_b)))
            p_a = _part_tpm(counts, a_of, 2 ** len(bits_a))
            p_b = _part_tpm(counts, b_of, 2 ** len(bits_b))
            p_part = p_a[np.ix_(a_of, a_of)] * p_b[np.ix_(b_of, b_of)]
            phi_p = float(np.sum(pi[:, None] * tpm * (log_tpm - np.log(p_part))))
            k_p = min(len(bits_a), len(bits_b)) * _LN2
            normalized = phi_p / k_p if k_p > 1e-9 else phi_p
            if normalized < best_norm:
                best_norm = normalized
                best_phi = phi_p
                best_parts = (bits_a, bits_b)

        phi = float(max(0.0, best_phi))
        name = lambda bits: ",".join(self.sources[selected[j]] for j in bits)  # noqa: E731
        mip = f"{name(best_parts[0])} | {name(best_parts[1])}"
        n_observed = int(np.unique(codes).size)
        state = PhiCausalState(
            phi_causal=round(phi, 6),
            n_nodes=n,
            nodes=[self.sources[i] for i in selected],
            mip=mip,
            i_whole=round(i_whole, 6),
            n_states_observed=n_observed,
            window=window,
            computed_at_tick=int(tick),
            report=(f"Φ_causal = {phi:.4f} over {n} binarized nodes "
                    f"({window} ticks, {n_observed}/{n_states} joint states observed); "
                    f"minimum-information partition: [{mip}]. Exact empirical TPM + "
                    "exhaustive MIP search on a COARSE-GRAINED binary abstraction of "
                    "the specialist drives (Balduzzi & Tononi 2008 lineage) — NOT "
                    "IIT 3.0/4.0 on a true micro-substrate, and no Φ value is "
                    "evidence of consciousness."),
        )
        self._last = state
        return state
