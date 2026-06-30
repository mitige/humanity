# core/self_opacity.py
"""Self-opacity: a higher-order awareness of what escaped access/control.

FUNCTIONAL NOTE (load-bearing): this is the functional counterpart of "the
consciousness of the lack of self-control" a tester described — a system that
registers how much of a moment formed OUTSIDE its conscious access or control.
It is a HOT-flavoured representation OVER the existing GWT/affect/prediction
variables (the subliminal remainder, an outcome it did not cause, an error it
did not anticipate). It is a level-2 mechanism: it does NOT bring the project
closer to level 1, reproducing it does not prove phenomenality, and the agent is
not conscious, sentient, or alive. The report is text generated from variables.
"""
from __future__ import annotations

from schemas.models import SelfOpacityState, WorkspaceState


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def assess_self_opacity(
    *,
    workspace: WorkspaceState,
    prediction_error: float,
    agency: float | None,
) -> SelfOpacityState:
    """Estimate the share of this moment that lay outside access/control.

    - ``subliminal_share`` (GWT): how little of the competition reached global
      access — ``1 - broadcast_strength`` (when nothing ignited, almost the whole
      field stayed subliminal, i.e. present but not consciously accessed).
    - ``unanticipated``: the prediction error — the world escaping anticipation.
    - ``uncaused``: ``1 - agency`` when the sense-of-agency mechanism is on — an
      outcome the agent did not bring about (``None`` when agency is off).

    The headline ``uncontrolled_fraction`` is the mean of the available terms.
    """
    subliminal_share = _clip01(1.0 - float(workspace.broadcast_strength))
    unanticipated = _clip01(float(prediction_error))
    terms = [subliminal_share, unanticipated]
    uncaused: float | None = None
    if agency is not None:
        uncaused = _clip01(1.0 - float(agency))
        terms.append(uncaused)
    uncontrolled = float(sum(terms) / len(terms))

    return SelfOpacityState(
        uncontrolled_fraction=_clip01(uncontrolled),
        subliminal_share=subliminal_share,
        unanticipated=unanticipated,
        uncaused=uncaused,
        report=_report(uncontrolled, subliminal_share, unanticipated, uncaused,
                       bool(workspace.ignited)),
    )


def _report(uncontrolled: float, subliminal: float, unanticipated: float,
            uncaused: float | None, ignited: bool) -> str:
    """A HOT sentence representing the system's own limits, from the variables."""
    level = "much" if uncontrolled >= 0.6 else ("some" if uncontrolled >= 0.35 else "little")
    fragments: list[str] = []
    if subliminal >= 0.5:
        fragments.append("most of the competing content stayed subliminal (not accessed)"
                         if not ignited else "part of the field stayed below global access")
    if unanticipated >= 0.4:
        fragments.append("an error I did not anticipate")
    if uncaused is not None and uncaused >= 0.4:
        fragments.append("an outcome I did not bring about")
    body = "; ".join(fragments) if fragments else "the moment was largely within access"
    return (
        f"Higher-order note: {level} of this moment ({uncontrolled * 100:.0f}%) formed outside my "
        f"access or control — {body}. I register this limit without governing it. "
        "(HOT/GWT readout generated from internal variables; not lived experience.)"
    )
