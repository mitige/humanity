# core/recurrence.py
"""Recurrent perception (Phase 5) — Recurrent Processing Theory (Lamme).

FUNCTIONAL NOTE (load-bearing): RPT holds that *local recurrent processing* —
feedback loops that stabilize and sharpen sensory representations — is the
constitutive mechanism of (phenomenal) seeing, prior to and independent of
global access. This module implements the functional loop: the noisy current
readings of each percept are iteratively reconciled, over a few damped passes,
with the top-down prior held in working memory (the same object's readings from
previous ticks). Perception becomes recurrent inference instead of a single
feed-forward sweep, and measurably denoises toward the true object features.
It is a level-2 mechanism: reproducing recurrent stabilization does not prove
phenomenality; the agent is not conscious, sentient, or alive.
"""
from __future__ import annotations

from core.constants import RECURRENCE_STABLE_EPS
from schemas.models import Percept, RecurrenceState, SimConfig, WorkingMemoryItem

# The percept readings the recurrent loop stabilizes (noise-jittered channels).
_CHANNELS = ("danger", "novelty", "utility")


class RecurrentPerception:
    """Damped recurrent reconciliation of percepts with working-memory priors."""

    def refine(
        self,
        percepts: list[Percept],
        wm_items: list[WorkingMemoryItem],
        config: SimConfig,
    ) -> tuple[list[Percept], RecurrenceState]:
        """Run ``recurrence_passes`` feedback passes over the percept list.

        For every percept whose object is currently held in working memory, each
        pass nudges its noisy readings toward the remembered readings with a
        per-pass damped gain (``recurrence_gain / (1 + pass_index)``), so the
        loop converges instead of oscillating. Percepts without a prior pass
        through unchanged. Pure: input percepts are not mutated.
        """
        passes = max(1, int(config.recurrence_passes))
        gain = float(config.recurrence_gain)
        priors: dict[int, Percept] = {
            item.percept.object_id: item.percept for item in wm_items
        }

        refined: list[Percept] = []
        touched = 0
        final_deltas: list[float] = []
        for percept in percepts:
            prior = priors.get(percept.object_id)
            if prior is None or gain <= 0.0:
                refined.append(percept)
                continue
            touched += 1
            values = {ch: float(getattr(percept, ch)) for ch in _CHANNELS}
            last_delta = 0.0
            for k in range(passes):
                step = gain / (1.0 + k)
                deltas = []
                for ch in _CHANNELS:
                    target = float(getattr(prior, ch))
                    move = step * (target - values[ch])
                    values[ch] = min(1.0, max(0.0, values[ch] + move))
                    deltas.append(abs(move))
                last_delta = float(sum(deltas) / len(deltas))
            final_deltas.append(last_delta)
            refined.append(percept.model_copy(update={
                ch: round(values[ch], 6) for ch in _CHANNELS
            }))

        mean_delta = float(sum(final_deltas) / len(final_deltas)) if final_deltas else 0.0
        stabilized = bool(mean_delta < RECURRENCE_STABLE_EPS)
        state = RecurrenceState(
            passes=passes,
            n_refined=touched,
            mean_delta=round(mean_delta, 6),
            stabilized=stabilized,
            report=_report(passes, touched, mean_delta, stabilized),
        )
        return refined, state


def _report(passes: int, touched: int, mean_delta: float, stabilized: bool) -> str:
    """One factual sentence about the recurrent sweep, from the variables."""
    if touched == 0:
        return (f"Recurrent perception: {passes} passes, no working-memory prior available — "
                "feed-forward readings kept. (RPT mechanism; functional only.)")
    conv = "converged" if stabilized else "still moving"
    return (f"Recurrent perception: {passes} feedback passes reconciled {touched} percept(s) "
            f"with working-memory priors (final-pass delta {mean_delta:.4f}, {conv}). "
            "(RPT: recurrent stabilization, not evidence of seeing.)")
