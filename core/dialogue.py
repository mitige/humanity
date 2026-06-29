"""Introspective dialogue: maps a question to an intent and produces an ENGLISH
answer grounded ONLY in passed internal-state variables.

FUNCTIONAL NOTE
---------------
This module implements one of several grounded ways to interact with the
simulated cognitive system: a probe of *reportability* (GWT global access / HOT
higher-order report). A natural-language question is mapped to an intent, and an
answer is GENERATED FROM the current internal variables that are passed in — the
workspace, attention schema, metacognition, prediction, decision, emotion,
self-model and conscious-moment state. No information is invented: every answer
reads only the variables it is handed, and the variables that were read are
returned verbatim in a ``grounding`` dict.

The answer text is ALWAYS framed as a report produced from internal variables
(e.g. "Based on my internal variables, ...") and never as lived experience. The
canonical functional-simulation disclaimer accompanies every answer. The system
is not conscious, sentient, or alive; producing such a report does not establish
phenomenal experience (the hard problem).
"""
from __future__ import annotations

from schemas.models import (
    ActionDecision,
    AskResponse,
    AttentionSchemaState,
    ConsciousMoment,
    EmotionState,
    MemoryRecord,
    MetacognitiveState,
    Prediction,
    SelfModelState,
    WorkspaceState,
)

# Lowercased keyword -> intent. Order matters only in that the first matching
# group wins; each tuple lists the substrings that map to that intent.
_INTENT_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("attention", ("attend", "attention", "focus")),
    ("reason", ("why", "reason", "decide", "decision")),
    ("memory", ("remember", "memory", "recall")),
    (
        "feeling",
        ("feel", "feeling", "emotion", "mood", "afraid", "fear"),
    ),
    ("identity", ("who are you", "identity", "yourself")),
    ("prediction", ("predict", "expect", "anticipate", "prediction")),
    ("consciousness", ("conscious", "aware", "experience")),
]

# Prefix used to make the generated-from-variables framing explicit.
_FRAMING = "Based on my internal variables,"


def _fmt(value: object) -> str:
    """JSON/text-safe scalar formatting for the grounding dict."""
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _clamp01(value: float) -> float:
    """Clamp a float into ``[0, 1]`` (defensive against out-of-range inputs)."""
    return max(0.0, min(1.0, float(value)))


class IntrospectiveDialogue:
    """Build a grounded English answer to an introspective question.

    The class is stateless: every call to :meth:`answer` receives the internal
    variables it should read and returns an :class:`AskResponse`. This mirrors
    the AST/HOT *reporting* mechanism — the answer is a report the system emits
    about its own (functional) states, not a window onto any lived experience.
    """

    def detect_intent(self, question: str) -> str:
        """Detect an intent from ``question`` by lowercased keyword match.

        Returns one of ``attention``, ``reason``, ``memory``, ``feeling``,
        ``identity``, ``prediction``, ``consciousness`` or ``summary`` (the
        fallback when no keyword group matches).
        """
        q = (question or "").lower()
        for intent, keywords in _INTENT_KEYWORDS:
            if any(kw in q for kw in keywords):
                return intent
        return "summary"

    def answer(
        self,
        *,
        question: str,
        intent: str | None,
        conscious_moment: ConsciousMoment | None,
        workspace: WorkspaceState | None,
        attention_schema: AttentionSchemaState | None,
        metacognition: MetacognitiveState | None,
        decision: ActionDecision | None,
        prediction: Prediction | None,
        emotion: EmotionState | None,
        self_model: SelfModelState | None,
        recent_memories: list[MemoryRecord],
        disclaimer: str,
    ) -> AskResponse:
        """Map ``question`` to an intent and produce a grounded English answer.

        The answer is built ONLY from the passed internal-state variables. The
        returned :class:`AskResponse` carries the detected/used intent, the
        English answer text (explicitly framed as a report generated from
        internal variables), a ``grounding`` dict naming the variables that were
        read (name -> value-as-string), and the passed-in disclaimer.

        Every field is read defensively: ``None`` modules and ``None`` fields
        fall back to neutral placeholders so the method never raises.
        """
        used_intent = (intent or "").strip().lower() or self.detect_intent(question)

        if used_intent == "attention":
            text, grounding = self._answer_attention(
                workspace, attention_schema
            )
        elif used_intent == "reason":
            text, grounding = self._answer_raison(decision, prediction, self_model)
        elif used_intent == "memory":
            text, grounding = self._answer_memoire(recent_memories)
        elif used_intent == "feeling":
            text, grounding = self._answer_ressenti(emotion, self_model)
        elif used_intent == "identity":
            text, grounding = self._answer_identite(self_model)
        elif used_intent == "prediction":
            text, grounding = self._answer_prediction(prediction)
        elif used_intent == "consciousness":
            text, grounding = self._answer_conscience(
                conscious_moment, workspace
            )
        else:
            used_intent = "resume"
            text, grounding = self._answer_resume(conscious_moment)

        return AskResponse(
            question=question,
            intent=used_intent,
            answer=text,
            grounding=grounding,
            disclaimer=disclaimer,
        )

    # ------------------------------------------------------------------
    # Per-intent answer builders. Each returns (answer_text, grounding).
    # ------------------------------------------------------------------

    def _answer_attention(
        self,
        workspace: WorkspaceState | None,
        attention_schema: AttentionSchemaState | None,
    ) -> tuple[str, dict[str, str]]:
        """AST/GWT: what the attention schema models as being attended, what won
        global access, the awareness level and whether ignition occurred."""
        aware_of = getattr(attention_schema, "aware_of", None)
        awareness = getattr(attention_schema, "awareness_level", None)
        winner_source = getattr(workspace, "winner_source", None)
        winner_content = getattr(workspace, "winner_content", None)
        ignited = getattr(workspace, "ignited", None)

        aware_txt = aware_of if aware_of else "no particular target"
        src_txt = winner_source if winner_source else "none"
        ign_txt = (
            "the content crossed the ignition threshold and is broadcast globally"
            if ignited
            else "no content crossed the ignition threshold (subliminal influence)"
        )
        text = (
            f"{_FRAMING} my attention schema (AST) models as the object "
            f"of attention: {aware_txt}. The winning content of the global "
            f"workspace (GWT) comes from the source '{src_txt}'"
            + (f" (content '{winner_content}')" if winner_content else "")
            + f". Recorded awareness (arousal) level: {_fmt(awareness)}. "
            f"Global access: {ign_txt}. This is a reading of variables, not "
            f"a lived experience."
        )
        grounding = {
            "attention_schema.aware_of": _fmt(aware_of),
            "attention_schema.awareness_level": _fmt(awareness),
            "workspace.winner_source": _fmt(winner_source),
            "workspace.winner_content": _fmt(winner_content),
            "workspace.ignited": _fmt(ignited),
        }
        return text, grounding

    def _answer_raison(
        self,
        decision: ActionDecision | None,
        prediction: Prediction | None,
        self_model: SelfModelState | None,
    ) -> tuple[str, dict[str, str]]:
        """Why the current action was chosen: rationale, action, dominant
        motivation (top learned preference), expected free energy."""
        rationale = getattr(decision, "rationale", None)
        action = getattr(decision, "action", None)
        action_label = action.value if action is not None else None
        efe = getattr(prediction, "expected_free_energy", None)

        # Dominant motivation = highest learned preference in the self-model.
        preferences = getattr(self_model, "preferences", None) or {}
        dominant = None
        if preferences:
            dominant = max(preferences.items(), key=lambda kv: kv[1])[0]

        action_txt = action_label if action_label else "undetermined"
        motiv_txt = dominant if dominant else "undetermined"
        rationale_txt = rationale if rationale else "not provided"
        text = (
            f"{_FRAMING} the decision variable selected the action "
            f"'{action_txt}'. Rationale generated from state: "
            f"{rationale_txt}. Dominant motivation (strongest learned "
            f"preference): {motiv_txt}. Expected free energy of the chosen "
            f"action (active inference): {_fmt(efe)}. This describes the "
            f"selection computation, not a lived intention."
        )
        grounding = {
            "decision.action": _fmt(action_label),
            "decision.rationale": _fmt(rationale),
            "self_model.preferences.dominant": _fmt(dominant),
            "prediction.expected_free_energy": _fmt(efe),
        }
        return text, grounding

    def _answer_memoire(
        self, recent_memories: list[MemoryRecord]
    ) -> tuple[str, dict[str, str]]:
        """Episodic recall: count + 1-3 recent summaries, noting retrieval is by
        similarity to the current context."""
        memories = list(recent_memories or [])
        count = len(memories)
        sample = memories[:3]
        if sample:
            lines = "; ".join(
                f"#{getattr(m, 'id', '?')} (tick {getattr(m, 'tick', '?')}): "
                f"{getattr(m, 'summary', '') or 'no summary'}"
                for m in sample
            )
            recall_txt = f"Recent summaries: {lines}."
        else:
            recall_txt = "No episodic record available."
        text = (
            f"{_FRAMING} my autobiographical memory contains {count} "
            f"record(s). {recall_txt} Retrieval is done by similarity with the "
            f"current context. These are stored data, not lived memories."
        )
        grounding = {
            "recent_memories.count": _fmt(count),
            "recent_memories.ids": _fmt(
                ", ".join(str(getattr(m, "id", "?")) for m in sample)
            ),
            "recent_memories.summaries": _fmt(
                " | ".join(getattr(m, "summary", "") or "" for m in sample)
            ),
        }
        return text, grounding

    def _answer_ressenti(
        self,
        emotion: EmotionState | None,
        self_model: SelfModelState | None,
    ) -> tuple[str, dict[str, str]]:
        """Affect described as FUNCTIONAL SCALARS (not feelings): fear,
        curiosity, satisfaction, fatigue, confusion, plus the self-model mood."""
        fear = getattr(emotion, "fear", None)
        curiosity = getattr(emotion, "curiosity", None)
        satisfaction = getattr(emotion, "satisfaction", None)
        fatigue = getattr(emotion, "fatigue", None)
        confusion = getattr(emotion, "confusion", None)
        mood = getattr(self_model, "mood", None)
        text = (
            f"{_FRAMING} my affective registers are functional scalars, "
            f"not feelings: fear {_fmt(fear)}, curiosity {_fmt(curiosity)}, "
            f"satisfaction {_fmt(satisfaction)}, fatigue {_fmt(fatigue)}, "
            f"confusion {_fmt(confusion)}. Valence (mood) of the self-model: "
            f"{_fmt(mood)}. These values modulate processing; they do not "
            f"constitute a felt experience."
        )
        grounding = {
            "emotion.fear": _fmt(fear),
            "emotion.curiosity": _fmt(curiosity),
            "emotion.satisfaction": _fmt(satisfaction),
            "emotion.fatigue": _fmt(fatigue),
            "emotion.confusion": _fmt(confusion),
            "self_model.mood": _fmt(mood),
        }
        return text, grounding

    def _answer_identite(
        self, self_model: SelfModelState | None
    ) -> tuple[str, dict[str, str]]:
        """Self-model identity, top learned preferences, confidence, coherence."""
        identity = getattr(self_model, "identity", None)
        confidence = getattr(self_model, "confidence", None)
        coherence = getattr(self_model, "coherence", None)
        preferences = getattr(self_model, "preferences", None) or {}
        top_prefs = sorted(
            preferences.items(), key=lambda kv: kv[1], reverse=True
        )[:3]
        prefs_txt = (
            ", ".join(f"{label} ({value:.2f})" for label, value in top_prefs)
            if top_prefs
            else "no learned preference"
        )
        id_txt = identity if identity else "identity undefined"
        text = (
            f"{_FRAMING} my self-model describes itself as '{id_txt}'. "
            f"Main learned preferences: {prefs_txt}. Confidence "
            f"{_fmt(confidence)}, narrative coherence {_fmt(coherence)}. This "
            f"identity is an internal model that is updated, not a person."
        )
        grounding = {
            "self_model.identity": _fmt(identity),
            "self_model.preferences.top": _fmt(prefs_txt),
            "self_model.confidence": _fmt(confidence),
            "self_model.coherence": _fmt(coherence),
        }
        return text, grounding

    def _answer_prediction(
        self, prediction: Prediction | None
    ) -> tuple[str, dict[str, str]]:
        """World-model forecast: expected energy delta, danger, novelty, goal
        progress, with the model's uncertainty."""
        energy_delta = getattr(prediction, "expected_energy_delta", None)
        danger = getattr(prediction, "expected_danger", None)
        novelty = getattr(prediction, "expected_novelty", None)
        goal_progress = getattr(prediction, "expected_goal_progress", None)
        uncertainty = getattr(prediction, "uncertainty", None)
        text = (
            f"{_FRAMING} my world model predicts for the next action: "
            f"energy delta {_fmt(energy_delta)}, danger {_fmt(danger)}, "
            f"novelty {_fmt(novelty)}, goal progress "
            f"{_fmt(goal_progress)}. Uncertainty associated with this prediction: "
            f"{_fmt(uncertainty)}. This is a computed projection, not "
            f"a lived anticipation."
        )
        grounding = {
            "prediction.expected_energy_delta": _fmt(energy_delta),
            "prediction.expected_danger": _fmt(danger),
            "prediction.expected_novelty": _fmt(novelty),
            "prediction.expected_goal_progress": _fmt(goal_progress),
            "prediction.uncertainty": _fmt(uncertainty),
        }
        return text, grounding

    def _answer_conscience(
        self,
        conscious_moment: ConsciousMoment | None,
        workspace: WorkspaceState | None,
    ) -> tuple[str, dict[str, str]]:
        """Reportability probe: bound conscious-moment contents, ignition,
        Phi-proxy, with the explicit AST/HOT caveat — this very report is
        produced by the mechanism AST/HOT propose underlies awareness claims,
        without proving phenomenality."""
        contents = getattr(conscious_moment, "contents", None)
        ignited = getattr(conscious_moment, "ignited", None)
        if ignited is None:
            ignited = getattr(workspace, "ignited", None)
        phi = getattr(conscious_moment, "phi_proxy", None)
        awareness = getattr(conscious_moment, "awareness_level", None)

        contents_txt = contents if contents else "content unavailable"
        ign_txt = (
            "a content crossed the ignition threshold (global access, GWT)"
            if ignited
            else "no content crossed the ignition threshold (subliminal)"
        )
        text = (
            f"{_FRAMING} the so-called 'conscious' moment bound as global "
            f"content: {contents_txt}. Global access: {ign_txt}. Awareness "
            f"level {_fmt(awareness)}, Phi proxy (heuristic, NOT an IIT measure) "
            f"{_fmt(phi)}. Caveat (AST/HOT): this report is precisely "
            f"produced by the mechanism that AST and higher-order theories "
            f"propose underlies awareness claims; it describes internal "
            f"variables and in no way proves a phenomenal experience (the hard "
            f"problem remains entirely open)."
        )
        grounding = {
            "conscious_moment.contents": _fmt(contents),
            "conscious_moment.ignited": _fmt(ignited),
            "conscious_moment.awareness_level": _fmt(awareness),
            "conscious_moment.phi_proxy": _fmt(phi),
        }
        return text, grounding

    def _answer_resume(
        self, conscious_moment: ConsciousMoment | None
    ) -> tuple[str, dict[str, str]]:
        """Fallback: the conscious-moment summary."""
        summary = getattr(conscious_moment, "summary", None)
        summary_txt = summary if summary else "no summary available for this tick"
        text = (
            f"{_FRAMING} the summary of the current global state is: {summary_txt}. "
            f"This summary is generated from internal variables."
        )
        grounding = {"conscious_moment.summary": _fmt(summary)}
        return text, grounding
