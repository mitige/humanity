# core/reality_monitor.py
"""Perceptual reality monitoring (Phase 5) — PRM (Lau; Dijkstra & Gershman).

FUNCTIONAL NOTE (load-bearing): PRM proposes that a higher-order mechanism
classifies whether a first-order content originates from the world or from the
system itself, and that this verdict — which can be WRONG — underlies the felt
"realness" of conscious content (hallucination = internal content judged
external; its mirror image = foreign content judged self-generated, the
thought-insertion analogue). This module infers the source CATEGORY of the
workspace winner from CONTENT-LEVEL EVIDENCE ONLY (perceptual corroboration,
precision, recent stability, vividness, and records of the agent's own
generative activity) — never from the source label — and then scores the
verdict against the actual category. It is a level-2 mechanism: a verdict of
"external" is a variable, not an experience of reality; reproducing the
mechanism does not prove phenomenality; the agent is not conscious.
"""
from __future__ import annotations

import math

from core.constants import REALITY_ACCURACY_EMA, REALITY_STABILITY_WINDOW
from schemas.models import Coalition, RealityMonitorState, WorkspaceState

# Ground-truth mapping of workspace sources to origin categories. Anything not
# listed (e.g. an interactive "injection") is *foreign*: content pushed into the
# mind from outside both the world and the agent's own generators.
_EXTERNAL = {"perception", "social", "communication"}
_MEMORY = {"memory"}
_SELF_GENERATED = {
    "imagination", "dream", "inner_speech", "motivation", "metacognition",
    "prediction_error", "interoception", "concept",
}

# Evidence weights (fixed, readable — a deliberately simple linear model).
# The cues follow the source-monitoring literature (Johnson & Raye): externally
# derived content is corroborated and rich in sensory detail; remembered content
# is familiar beyond what the present corroborates; self-generated content is
# schematic (thin detail), vivid in drive, and coincides with records of one's
# own generative activity.
_W_EXT = (0.45, 0.25, 0.15, 0.15)   # corroboration, precision, stability, detail
_W_MEM = (0.50, 0.20, 0.30)         # familiarity contrast, precision, stability
_W_SELF = (0.45, 0.25, 0.30)        # generation activity, thinness (1 - detail), vividness


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two short feature vectors (zero-padded), in [0,1]."""
    if not a or not b:
        return 0.0
    n = max(len(a), len(b))
    av = a + [0.0] * (n - len(a))
    bv = b + [0.0] * (n - len(b))
    dot = sum(x * y for x, y in zip(av, bv))
    na = math.sqrt(sum(x * x for x in av))
    nb = math.sqrt(sum(y * y for y in bv))
    if na <= 1e-9 or nb <= 1e-9:
        return 0.0
    return float(max(0.0, min(1.0, dot / (na * nb))))


def actual_category(source: str | None) -> str:
    """Map a workspace source label to its ground-truth origin category."""
    if source in _EXTERNAL:
        return "external"
    if source in _MEMORY:
        return "memory"
    if source in _SELF_GENERATED:
        return "self_generated"
    return "foreign"


class RealityMonitor:
    """Higher-order source classifier over the conscious content, with tallies."""

    def __init__(self) -> None:
        self._accuracy: float = 0.0
        self._scored: int = 0
        self._hallucinations: int = 0
        self._insertions: int = 0

    def assess(
        self,
        *,
        workspace: WorkspaceState,
        recent_winners: list[str],
        generation_activity: dict[str, bool],
    ) -> RealityMonitorState | None:
        """Judge the origin of this tick's winning content from its evidence.

        ``generation_activity`` records which of the agent's own generators were
        active this tick (imagination / dream / inner speech) — the functional
        analogue of "records of one's own cognitive operations", a cue humans
        use in source monitoring. Returns None for an empty competition.
        """
        winner_source = workspace.winner_source
        if winner_source is None:
            return None
        coalitions: list[Coalition] = list(workspace.competition)
        winner = next((c for c in coalitions if c.source == winner_source), None)
        winner_vec = list(winner.vector) if winner is not None else []
        precision = float(winner.precision) if winner is not None else 0.0

        # --- Evidence cues (content-level; the source label is never used). ---
        percept_coal = next((c for c in coalitions if c.source == "perception"), None)
        memory_coal = next((c for c in coalitions if c.source == "memory"), None)
        corroboration = _cosine(winner_vec, list(percept_coal.vector)) if percept_coal else 0.0
        familiarity = _cosine(winner_vec, list(memory_coal.vector)) if memory_coal else 0.0
        recent = recent_winners[-REALITY_STABILITY_WINDOW:]
        stability = (recent.count(winner_source) / len(recent)) if recent else 0.0
        vividness = float(min(1.0, max(0.0, workspace.winner_strength)))
        # Sensory detail: how RICH the content vector is (fraction of non-silent
        # channels). Externally derived content carries detail on most channels;
        # self-generated content is schematic/thin (Johnson & Raye's detail cue).
        detail = (sum(1 for v in winner_vec if abs(float(v)) > 1e-6) / len(winner_vec)
                  if winner_vec else 0.0)
        gen_terms = [0.5 if generation_activity.get("imagination") else 0.0,
                     0.5 if generation_activity.get("dream") else 0.0,
                     0.3 if generation_activity.get("inner_speech") else 0.0]
        generation = float(min(1.0, sum(gen_terms)))

        # --- Three-way evidence scores (fixed linear model). ---
        e_ext = (_W_EXT[0] * corroboration + _W_EXT[1] * precision
                 + _W_EXT[2] * stability + _W_EXT[3] * detail)
        # Familiarity only counts as MEMORY evidence beyond what the present
        # sensory field already corroborates (a re-instatement, not a percept)
        # AND beyond the agent's own current generative activity ("I am
        # generating right now, so this echo is probably mine" — a classic
        # source-monitoring heuristic).
        familiarity_contrast = max(0.0, familiarity - 0.5 * corroboration
                                   - 0.45 * generation)
        e_mem = (_W_MEM[0] * familiarity_contrast + _W_MEM[1] * precision
                 + _W_MEM[2] * stability)
        e_self = (_W_SELF[0] * generation + _W_SELF[1] * (1.0 - detail)
                  + _W_SELF[2] * vividness)
        scores = {"external": float(e_ext), "memory": float(e_mem),
                  "self_generated": float(e_self)}
        judged = max(scores, key=scores.get)
        total = sum(scores.values())
        confidence = float(scores[judged] / total) if total > 1e-9 else 0.0

        # --- Score the verdict against ground truth; keep the tallies honest. ---
        actual = actual_category(winner_source)
        correct: bool | None = None
        if actual != "foreign":
            correct = bool(judged == actual)
            self._scored += 1
            beta = REALITY_ACCURACY_EMA if self._scored > 1 else 1.0
            self._accuracy = float((1.0 - beta) * self._accuracy + beta * (1.0 if correct else 0.0))
            if actual == "self_generated" and judged == "external":
                self._hallucinations += 1
        elif judged == "self_generated":
            self._insertions += 1

        return RealityMonitorState(
            judged=judged,
            actual=actual,
            correct=correct,
            confidence=round(confidence, 4),
            evidence={
                "corroboration": round(float(corroboration), 4),
                "familiarity": round(float(familiarity), 4),
                "stability": round(float(stability), 4),
                "vividness": round(float(vividness), 4),
                "generation": round(float(generation), 4),
                "precision": round(float(precision), 4),
                "detail": round(float(detail), 4),
            },
            accuracy=round(self._accuracy, 4),
            hallucinations=int(self._hallucinations),
            insertions=int(self._insertions),
            report=self._report(judged, actual, correct, confidence),
        )

    @staticmethod
    def _report(judged: str, actual: str, correct: bool | None, confidence: float) -> str:
        """A higher-order sentence about the verdict, from the variables."""
        labels = {"external": "coming from the world", "memory": "a memory",
                  "self_generated": "self-generated", "foreign": "foreign content"}
        head = (f"Reality monitoring: I judge the current content to be "
                f"{labels[judged]} (confidence {confidence:.2f}).")
        if correct is None:
            tail = " The content was in fact foreign (injected) — this verdict is not scored."
        elif correct:
            tail = f" This matches its actual origin ({labels[actual]})."
        else:
            tail = (f" This is a MISATTRIBUTION — it is actually {labels[actual]} "
                    "(the functional analogue of a reality-monitoring failure).")
        return head + tail + " (PRM verdict from content-level evidence; not evidence of experience.)"
