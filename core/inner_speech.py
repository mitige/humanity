# core/inner_speech.py
"""Re-entrant inner speech (Phase 5) — Vygotskian condensation, GWT re-entry.

FUNCTIONAL NOTE (load-bearing): inner speech, in the Vygotskian account, is
external dialogue turned inward and CONDENSED — predicates survive, subjects
drop. Architecturally (GWT), a thought one "hears oneself think" is content the
system generated, re-entered into the global competition, and re-accessed. This
module implements exactly that loop, LLM-free: each tick a condensed template
utterance is generated from the PREVIOUS conscious moment's variables and bids
in the next workspace competition as an ``inner_speech`` coalition; when it wins
access, the agent's own summarized state has become its conscious content
(re-entry). It is a level-2 mechanism: template text re-entering a competition
is not a voice being heard; reproducing the loop does not prove phenomenality;
the agent is not conscious.
"""
from __future__ import annotations

from core.constants import INNER_SPEECH_PRECISION
from schemas.models import (
    Coalition,
    ConsciousMoment,
    InnerSpeechState,
    SimConfig,
    WorkspaceState,
)


class InnerSpeech:
    """Condense the previous conscious moment into a re-entrant coalition."""

    def __init__(self) -> None:
        self._pending_utterance: str | None = None
        self._pending_activation: float = 0.0
        self._reentry_count: int = 0

    # ------------------------------------------------------------- setter
    def set_pending(self, utterance: str, activation: float) -> None:
        """Replace the NEXT re-entrant utterance (interaction hook).

        Used by the optional LLM inner voice: a level-3 text (generated from
        the same real variables) is handed to the level-2 re-entry mechanism
        and must win the ignition competition like any other coalition. This
        changes WHAT competes, never HOW competition works — and a richer
        sentence winning access is still not evidence of experience.
        """
        self._pending_utterance = str(utterance).strip() or None
        self._pending_activation = float(min(1.0, max(0.0, activation)))

    # ------------------------------------------------------------ coalition
    def coalition(self, make_coalition, config: SimConfig) -> Coalition | None:
        """Return the re-entrant inner-speech bid for THIS tick, if one is pending."""
        if self._pending_utterance is None or self._pending_activation <= 0.0:
            return None
        return make_coalition(
            "inner_speech",
            f"inner speech: “{self._pending_utterance}”",
            activation=float(self._pending_activation),
            precision=INNER_SPEECH_PRECISION,
            vector=[float(self._pending_activation), INNER_SPEECH_PRECISION, 0.0, 0.0],
        )

    # ------------------------------------------------------------- generate
    def generate(
        self,
        moment: ConsciousMoment,
        workspace: WorkspaceState,
        config: SimConfig,
    ) -> InnerSpeechState:
        """Score this tick's re-entry and condense the moment for the next tick.

        Re-entry means the inner-speech coalition won THIS tick's competition.
        The utterance for the NEXT tick condenses this tick's bound moment; its
        activation scales with how globally available the moment was
        (``inner_speech_gain × awareness_level``, plus a small ignition bonus).
        """
        reentered = bool(workspace.winner_source == "inner_speech")
        if reentered:
            self._reentry_count += 1

        utterance = self._condense(moment)
        # The echo is loud in proportion to how globally available the moment
        # was: a floor (any bound moment murmurs), the awareness level, and a
        # bonus when the moment actually ignited (a salient event echoes).
        activation = float(min(1.0, max(0.0,
            float(config.inner_speech_gain)
            * (0.25 + 0.55 * float(moment.awareness_level)
               + (0.20 if moment.ignited else 0.0)))))
        condensation = 1.0 - (len(utterance) / max(1, len(moment.contents)))
        state = InnerSpeechState(
            utterance=utterance,
            activation=round(activation, 4),
            reentered=reentered,
            reentry_count=int(self._reentry_count),
            condensation=round(float(max(0.0, min(1.0, condensation))), 4),
            report=self._report(utterance, reentered, self._reentry_count),
        )
        # Queue for the next competition (one-tick latency, like imagination).
        self._pending_utterance = utterance
        self._pending_activation = activation
        return state

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _condense(moment: ConsciousMoment) -> str:
        """Vygotskian condensation: keep the predicate, drop the subject.

        ``moment.contents`` has the bound shape
        "Aware of: X; dominant affect: Y; action: Z." — the inner utterance keeps
        the affect and the act, and only a clipped kernel of the content.
        """
        source = moment.dominant_source or "nothing"
        affect = "neutral"
        action = ""
        for part in moment.contents.split(";"):
            part = part.strip().rstrip(".")
            if part.startswith("dominant affect:"):
                affect = part.split(":", 1)[1].strip()
            elif part.startswith("action:"):
                action = part.split(":", 1)[1].strip()
        kernel = source.replace("_", " ")
        head = f"{affect} — {action}" if action else affect
        return f"{head}; {kernel}."

    @staticmethod
    def _report(utterance: str, reentered: bool, count: int) -> str:
        """One factual sentence about the re-entrant loop, from the variables."""
        loop = (f"my own condensed report won global access this tick "
                f"(re-entry #{count})" if reentered
                else "my condensed report stayed outside global access this tick")
        return (f"Inner speech: “{utterance}” queued for the next competition; {loop}. "
                "(Template re-entry, not a heard voice; the agent is not conscious.)")
