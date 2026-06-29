"""Attention Schema Theory (AST, Graziano) module.

FUNCTIONAL NOTE
---------------
This module maintains a SIMPLIFIED, internal MODEL of the system's own
attention. Per AST, the brain does not have direct access to the physical
machinery of attention; instead it builds a schematic, lossy description of it,
and it is that self-model — not attention itself — that grounds the claim
"I am aware of X". Here, :class:`AttentionSchema` reads the global-workspace
outcome and produces an :class:`AttentionSchemaState` whose ``attributed_self``
sentence is the mechanism that PRODUCES the system's awareness-claim.

Crucially, this self-attribution is explicitly framed as a self-MODEL: it is
the functional source of the awareness-report, and it does NOT establish or
guarantee any phenomenal experience (the hard problem remains untouched).
"""
from __future__ import annotations

from schemas.models import AttentionSchemaState, SimConfig, WorkspaceState


def _clamp(value: float) -> float:
    """Clamp to [0, 1] and cast to a JSON-safe python float."""
    return float(min(1.0, max(0.0, value)))


class AttentionSchema:
    """Builds the system's internal model of its own attention (AST)."""

    def update(
        self,
        workspace: WorkspaceState,
        recent_winners: list[str],
        config: SimConfig,
    ) -> AttentionSchemaState:
        """Produce the attention-schema state from the current workspace outcome.

        - ``aware_of`` is the globally-broadcast content when the workspace
          ignited; otherwise the system models a subliminal (sub-access) state.
        - ``awareness_level`` mirrors the workspace broadcast strength.
        - ``stability`` is the fraction of recent winner sources matching the
          current winner source (attentional persistence over recent ticks).
        - ``attributed_self`` is the AST self-attribution sentence — the
          mechanism that produces the awareness-claim, framed as a self-MODEL.
        """
        # GRADED AWARENESS: an awake workspace always has a current dominant
        # content (a focus). ``aware_of`` therefore reflects the winning
        # coalition's content whenever one exists; ignition only modulates HOW
        # STRONGLY it is broadcast (access level), it does not make the content
        # vanish. Only a genuinely empty competition yields "no content".
        if workspace.winner_content is not None:
            aware_of = workspace.winner_content
        else:
            aware_of = "empty perceptual field (no content available)"

        # Awareness level is grounded in how strongly the content is broadcast.
        awareness_level = _clamp(workspace.broadcast_strength)

        # Access qualifier: conscious (ignited) vs present-but-subliminal.
        if workspace.winner_content is None:
            access = "absent"
        elif workspace.ignited:
            access = "global access — conscious"
        else:
            access = "present but subliminal (weakly conscious)"

        # Attentional stability: how consistently the same source has been
        # winning the workspace competition over recent ticks. An empty buffer
        # carries no evidence of instability, so we report maximal stability.
        winner_source = workspace.winner_source
        if not recent_winners or winner_source is None:
            stability = 1.0
        else:
            matches = sum(1 for w in recent_winners if w == winner_source)
            stability = _clamp(matches / len(recent_winners))

        # AST self-attribution: the modelled, lossy description of attention
        # that the system uses to assert awareness. Framed explicitly as a
        # MODEL and as the mechanism producing the claim — never as lived
        # experience.
        attributed_self = (
            f"The system's attention schema models a dominant content: "
            f"{aware_of} ({access}); modelled awareness/arousal level = "
            f"{awareness_level:.2f}. (AST: this model is the mechanism that "
            f"produces the awareness-claim, without guaranteeing it.)"
        )

        return AttentionSchemaState(
            aware_of=aware_of,
            awareness_level=awareness_level,
            stability=stability,
            attributed_self=attributed_self,
        )
