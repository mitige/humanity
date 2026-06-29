"""Global Workspace (GWT) competition + broadcast mechanism for Humanity v2.

FUNCTIONAL note: this implements the Global Workspace Theory (Baars/Dehaene)
mechanism as a *competition* among specialist "coalitions" (bids) for a single,
limited global broadcast channel. A winning coalition that crosses the ignition
threshold is broadcast globally ("ignition"); otherwise its influence is treated
as subliminal (attenuated). This is a functional model of access/broadcast, not
a claim about phenomenal experience: ignition here is a numeric thresholding of
softmax-normalized bids, not a subjective "lighting up".
"""
from __future__ import annotations

from collections import deque

import numpy as np

from schemas.models import Coalition, SimConfig, WorkspaceState
from core.constants import (
    AROUSAL_CEIL,
    AROUSAL_FLOOR,
    AROUSAL_THRESHOLD_GAIN,
    IGNITION_ADAPT,
    IGNITION_SCORE_WINDOW,
    SUBLIMINAL_FACTOR,
)


class GlobalWorkspace:
    """GWT competition arena: specialist bids compete, winner is broadcast.

    A small ring buffer of recent winner sources is kept so downstream
    mechanisms (e.g. the attention schema) can estimate attentional stability.
    """

    def __init__(self, config: SimConfig) -> None:
        """Keep config and a ring buffer of recent winning sources for stability."""
        self.config = config
        # Ring buffer of recent winner source labels (for AST stability metric).
        self._recent_winners: deque[str] = deque(maxlen=max(1, int(config.stream_length)))
        # Recent ignition scores -> homeostatic (relative-prominence) threshold.
        self._recent_scores: deque[float] = deque(maxlen=IGNITION_SCORE_WINDOW)

    # ------------------------------------------------------------- factory
    @staticmethod
    def make_coalition(
        source: str,
        content: str,
        activation: float,
        precision: float,
        vector: list[float] | None = None,
    ) -> Coalition:
        """Build a Coalition, clamping activation/precision to [0,1] and casting floats."""
        vec = [float(v) for v in (vector or [])]
        return Coalition(
            source=str(source),
            content=str(content),
            activation=float(np.clip(float(activation), 0.0, 1.0)),
            precision=float(np.clip(float(precision), 0.0, 1.0)),
            vector=vec,
        )

    # ------------------------------------------------------------- compete
    def compete(
        self,
        coalitions: list[Coalition],
        config: SimConfig,
        *,
        arousal: float | None = None,
        maintenance_source: str | None = None,
    ) -> WorkspaceState:
        """Run GWT competition with a proper ignition dynamic.

        Earlier versions gated ignition on a softmax-NORMALIZED share, which is
        structurally capped well below the threshold once several coalitions
        compete (~0.35 for 6 bids) — so ignition essentially never fired. GWT /
        the global neuronal workspace describes ignition as a non-linear,
        near-all-or-none amplification triggered when a winning coalition is both
        *strong* (absolute drive) and *clearly dominant* over its rivals, gated by
        global *arousal*. We model exactly that:

          1. drive_i = activation_i * (precision_i ** precision_weight)   (absolute, 0..1)
          2. hysteresis: a coalition matching ``maintenance_source`` (the content
             broadcast last tick) gets a small maintenance boost -> a sustained
             "train of thought".
          3. dominance: a recurrent winner-take-all (sharpening map s <- s**p / sum)
             estimates how clearly the winner beats its rivals (-> 1 for a clear
             winner, -> 1/n for a tie).
          4. ignition_score = winner_drive * dominance   (strong AND clear).
          5. arousal modulation: gated = ignition_score * (arousal / baseline);
             ignited iff gated >= ignition_threshold.
          6. broadcast_strength = gated (ignited) else gated * SUBLIMINAL_FACTOR.

        The softmax-normalized field is still written back into ``coalition.activation``
        (it feeds the Phi-proxy distribution and the UI bars); it no longer gates
        ignition. ``ignited`` here is a numeric thresholding, not a subjective
        "lighting up".
        """
        baseline = max(1e-6, float(config.arousal_baseline))
        ar = baseline if arousal is None else float(
            np.clip(float(arousal), AROUSAL_FLOOR, AROUSAL_CEIL)
        )

        # Empty competition: nothing reaches the workspace (null/unaware state).
        if not coalitions:
            return WorkspaceState(
                ignited=False,
                threshold=float(config.ignition_threshold),
                winner_source=None,
                winner_content=None,
                broadcast_strength=0.0,
                competition=[],
                broadcast_vector=[],
                ignition_score=0.0,
                winner_strength=0.0,
                dominance=0.0,
                arousal=round(ar, 6),
                effective_threshold=round(float(config.ignition_threshold), 6),
            )

        precisions = np.array([c.precision for c in coalitions], dtype=float)
        raw_act = np.array([c.activation for c in coalitions], dtype=float)
        pw = float(config.precision_weight)

        # 1) Absolute precision-weighted drive (stays in [0,1]).
        drive = np.clip(raw_act * np.power(precisions, pw), 0.0, 1.0)

        # 2) Hysteresis: sustain whatever was broadcast last tick.
        if maintenance_source is not None:
            boost = float(config.ignition_maintenance)
            for i, c in enumerate(coalitions):
                if c.source == maintenance_source:
                    drive[i] = float(np.clip(drive[i] + boost, 0.0, 1.0))

        # Softmax-normalized field (for the Phi-proxy distribution + UI bars).
        temp = max(1e-6, float(config.workspace_temp))
        shifted = drive / temp - float(np.max(drive / temp))
        exp = np.exp(shifted)
        denom = float(np.sum(exp))
        normalized = exp / denom if denom > 0.0 else np.full(len(coalitions), 1.0 / len(coalitions))
        for c, norm in zip(coalitions, normalized):
            c.activation = float(np.clip(float(norm), 0.0, 1.0))

        # 3) Dominance: how clearly the winner leads its nearest rival, as a
        #    NON-saturating relative margin (so it actually discriminates between
        #    a runaway winner and a near-tie, unlike a converged softmax share).
        winner_idx = int(np.argmax(drive))
        winner = coalitions[winner_idx]
        winner_drive = float(drive[winner_idx])
        ordered = np.sort(drive)[::-1]
        runner_up = float(ordered[1]) if len(ordered) > 1 else 0.0
        dom_rel = float(np.clip((winner_drive - runner_up) / (winner_drive + 1e-6), 0.0, 1.0))

        # 4) Ignition score = strong AND clearly dominant. ``competition_sharpness``
        #    sets how much dominance (vs raw strength) is required: a=1/(1+sharp)
        #    is the floor contribution of raw strength when there is no margin.
        sharp = max(0.0, float(config.competition_sharpness))
        a = 1.0 / (1.0 + sharp)
        ignition_score = float(np.clip(winner_drive * (a + (1.0 - a) * dom_rel), 0.0, 1.0))

        # 5) Effective ignition threshold = a HOMEOSTATIC center (nominal cutoff
        #    blended with the running mean of recent scores, so ignition tracks
        #    relative prominence and stays healthy across environments), then
        #    SHIFTED by arousal (rising vigilance lowers it -> easier access).
        threshold = float(config.ignition_threshold)
        recent_mean = float(np.mean(self._recent_scores)) if self._recent_scores else threshold
        center = (1.0 - IGNITION_ADAPT) * threshold + IGNITION_ADAPT * recent_mean
        effective_threshold = float(
            np.clip(center * (1.0 + AROUSAL_THRESHOLD_GAIN * (baseline - ar)), 0.05, 0.95)
        )
        ignited = bool(ignition_score >= effective_threshold)
        # Record this tick's score for the next round's adaptive baseline.
        self._recent_scores.append(float(ignition_score))

        # 6) Broadcast strength: full when ignited, attenuated (subliminal) else.
        broadcast_strength = float(
            np.clip(ignition_score if ignited else ignition_score * SUBLIMINAL_FACTOR, 0.0, 1.0)
        )

        broadcast_vector = self._broadcast_vector(
            coalitions, normalized, winner, float(normalized[winner_idx]), threshold, ignited
        )

        # Record the winning source for stability tracking.
        self._recent_winners.append(winner.source)

        return WorkspaceState(
            ignited=ignited,
            threshold=round(threshold, 6),
            winner_source=winner.source,
            winner_content=winner.content,
            broadcast_strength=round(broadcast_strength, 6),
            competition=coalitions,
            broadcast_vector=[round(float(v), 6) for v in broadcast_vector],
            ignition_score=round(ignition_score, 6),
            winner_strength=round(winner_drive, 6),
            dominance=round(dom_rel, 6),
            arousal=round(ar, 6),
            effective_threshold=round(effective_threshold, 6),
        )

    # ----------------------------------------------------- broadcast vector
    @staticmethod
    def _broadcast_vector(
        coalitions: list[Coalition],
        normalized: np.ndarray,
        winner: Coalition,
        top_norm: float,
        threshold: float,
        ignited: bool,
    ) -> list[float]:
        """Compute the globally broadcast feature vector.

        When ignited, the winner's content is broadcast verbatim. When subliminal,
        we broadcast a blended/attenuated trace: the elementwise mean of vectors
        whose normalized activation crossed threshold, or (if none did) the
        winner's vector attenuated by SUBLIMINAL_FACTOR.
        """
        if ignited:
            return [float(v) for v in winner.vector]

        # Gather above-threshold vectors of equal length (so elementwise mean is valid).
        above: list[list[float]] = []
        max_len = 0
        for c, norm in zip(coalitions, normalized):
            if float(norm) >= threshold and c.vector:
                above.append([float(v) for v in c.vector])
                max_len = max(max_len, len(c.vector))

        if above and max_len > 0:
            # Pad shorter vectors with zeros to align before averaging.
            padded = np.array(
                [vec + [0.0] * (max_len - len(vec)) for vec in above], dtype=float
            )
            mean_vec = np.mean(padded, axis=0)
            return [float(v) for v in mean_vec]

        # Fallback: attenuated winner vector (subliminal trace).
        return [float(v) * SUBLIMINAL_FACTOR for v in winner.vector]

    # ------------------------------------------------------- recent winners
    def recent_winners(self, n: int) -> list[str]:
        """Return up to the last ``n`` winning source labels (most recent last)."""
        if n <= 0:
            return []
        items = list(self._recent_winners)
        return items[-int(n):]
