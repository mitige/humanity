# core/temporality.py
"""Temporal thickness of the conscious moment (Phase 5) — retention/protention.

FUNCTIONAL NOTE (load-bearing): phenomenology (Husserl; the "specious present")
holds that experience is temporally THICK: each now retains the just-past
(retention), anticipates the just-coming (protention), and a violated
protention is felt as temporal surprise. This module renders that structure as
variables over the stream of conscious moments: exponentially fading retention
weights, an anticipated next dominant content + valence, and the protention
violation, which (gated) summons vigilance on the next tick. It is a level-2
mechanism: a decaying buffer and a modal prediction are not lived time;
reproducing the structure does not prove phenomenality; the agent is not
conscious.
"""
from __future__ import annotations

import math
from collections import Counter

from schemas.models import (
    ConsciousMoment,
    RetainedMoment,
    SimConfig,
    TemporalityState,
)


class Temporality:
    """Retention / protention over the stream of conscious moments."""

    def __init__(self) -> None:
        # The protention issued LAST tick, to be scored against THIS tick.
        self._protended: tuple[str | None, float] | None = None

    def update(self, stream: list[ConsciousMoment], config: SimConfig) -> TemporalityState:
        """Build this tick's thick present and score the previous protention.

        ``stream`` must end with the CURRENT moment (the primal impression).
        Retention covers up to ``retention_horizon`` just-past moments with
        weights exp(-k/tau); protention predicts the next dominant source (modal
        winner over ``protention_window``) and valence (mean over that window).
        """
        current = stream[-1]
        horizon = max(2, int(config.retention_horizon))
        window = max(2, int(config.protention_window))

        # --- Retention: the just-past, still lingering with fading weight. ---
        past = stream[:-1]
        tau = max(1.0, horizon / 2.0)
        retained: list[RetainedMoment] = []
        for k, moment in enumerate(reversed(past[-horizon:]), start=1):
            weight = math.exp(-k / tau)
            retained.append(RetainedMoment(
                tick=int(moment.tick),
                contents=moment.contents,
                weight=round(float(weight), 4),
            ))
        specious_width = 1.0 + sum(r.weight for r in retained)

        # --- Score the PREVIOUS protention against the realized present. ---
        protention_error: float | None = None
        if self._protended is not None:
            exp_source, exp_valence = self._protended
            source_miss = 0.0 if current.dominant_source == exp_source else 1.0
            valence_miss = min(1.0, abs(float(current.valence) - float(exp_valence)) / 2.0)
            protention_error = float(min(1.0, 0.6 * source_miss + 0.4 * valence_miss))

        # --- Protention: anticipate the next moment from the recent stream. ---
        recent = stream[-window:]
        sources = [m.dominant_source for m in recent if m.dominant_source is not None]
        protended_source = Counter(sources).most_common(1)[0][0] if sources else None
        protended_valence = (sum(float(m.valence) for m in recent) / len(recent)) if recent else 0.0
        self._protended = (protended_source, float(protended_valence))

        return TemporalityState(
            retained=retained,
            specious_width=round(float(specious_width), 4),
            protended_source=protended_source,
            protended_valence=round(float(protended_valence), 4),
            protention_error=(round(protention_error, 4)
                              if protention_error is not None else None),
            report=self._report(len(retained), specious_width,
                                protended_source, protention_error),
        )

    @staticmethod
    def _report(n_retained: int, width: float, protended: str | None,
                error: float | None) -> str:
        """One factual sentence about the thick present, from the variables."""
        if error is None:
            fit = "no prior anticipation to score"
        elif error < 0.2:
            fit = f"the moment arrived as anticipated (violation {error:.2f})"
        elif error < 0.6:
            fit = f"the moment partly departed from anticipation (violation {error:.2f})"
        else:
            fit = f"the moment violated anticipation (violation {error:.2f})"
        towards = protended if protended is not None else "nothing in particular"
        return (f"Temporal thickness: {n_retained} just-past moment(s) still lingering "
                f"(specious width {width:.2f}); leaning toward '{towards}' next; {fit}. "
                "(Retention/protention as variables — not lived time.)")
