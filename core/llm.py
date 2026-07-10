# core/llm.py
"""Optional LLM integration — a grounded NARRATOR for the level-3 report.

HONESTY NOTE (load-bearing): the LLM is a PERIPHERAL organ, not the core. It is
fed ONLY the agent's real internal variables and instructed to render them into
language — nothing more. It does not change the cognitive loop, the decision, or
any measured value; behaviour and the deterministic test suite are untouched. A
fluent narration is STILL "text generated from internal variables": it is not
evidence of consciousness, sentience, or subjective experience. Making the words
prettier does not cross the hard problem.

The backend talks to OpenRouter over plain stdlib HTTP (no new dependency). The
API key is read from the environment (``OPENROUTER_API_KEY``) — never hard-coded,
never committed. Default off: with no key / flag off, the instrument stays fully
offline and deterministic.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"

# A strict system prompt: the model may only re-describe the given variables.
NARRATOR_SYSTEM = (
    "You are a strict NARRATOR embedded in a functional cognitive simulation called Humanity. "
    "You will be given a JSON object of the agent's REAL internal variables for one moment "
    "(global-workspace winner, ignition, awareness, affect scalars, self-model, metacognition, "
    "integrated-information proxy, what escaped its control, etc.). "
    "Render them as a short, sober, first-person-descriptive narration of 2-4 sentences. "
    "ABSOLUTE RULES: (1) Describe ONLY what is present in the JSON; invent nothing — no facts, "
    "memories, senses, or feelings that are not in the data. (2) If a value is low, absent, or "
    "null, reflect that faithfully. (3) NEVER claim to be conscious, sentient, alive, or to have "
    "genuine subjective experience — you are describing internal variables, not a lived experience. "
    "(4) No mysticism, no drama, no purple prose. You are a readout, not a soul."
)


class LLMBackend:
    """Interface for an optional text-completion backend."""

    def available(self) -> bool:
        return False

    def complete(self, system: str, user: str, *, max_tokens: int = 320,
                 temperature: float = 0.4) -> str:
        raise NotImplementedError


class NullBackend(LLMBackend):
    """No LLM configured — the instrument stays offline/deterministic."""

    def available(self) -> bool:
        return False

    def complete(self, *args, **kwargs) -> str:  # pragma: no cover - guarded by available()
        raise RuntimeError("no LLM backend configured (set OPENROUTER_API_KEY)")


class OpenRouterBackend(LLMBackend):
    """Chat-completions via OpenRouter, using the stdlib HTTP client."""

    def __init__(self, api_key: str | None = None, model: str | None = None,
                 timeout: float = 60.0) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")
        self.model = model or os.environ.get("HUMANITY_LLM_MODEL", DEFAULT_MODEL)
        self.timeout = float(timeout)

    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, system: str, user: str, *, max_tokens: int = 320,
                 temperature: float = 0.4) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": int(max_tokens),
            "temperature": float(temperature),
        }
        req = urllib.request.Request(
            OPENROUTER_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/mitige/humanity",
                "X-Title": "Humanity",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:  # surface the provider's message
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"OpenRouter HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenRouter unreachable: {e.reason}") from e
        choice = data["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content")
        if not content:
            # Reasoning models can exhaust the budget before emitting final content.
            if choice.get("finish_reason") == "length":
                raise RuntimeError("LLM hit the token limit before finishing (raise max_tokens).")
            content = msg.get("reasoning") or ""
        return str(content).strip()


def get_backend() -> LLMBackend:
    """Return an OpenRouter backend if a key is present, else the Null backend."""
    backend = OpenRouterBackend()
    return backend if backend.available() else NullBackend()


def _r(x, n: int = 3):
    try:
        return round(float(x), n)
    except (TypeError, ValueError):
        return x


def _report_trace(agent):
    """Use an established trace; only standalone agents may self-prime."""
    trace = getattr(agent, "last_trace", None)
    if trace is not None:
        return trace
    if getattr(agent, "_shared_world", None) is not None:
        raise RuntimeError(
            "A shared agent must be primed through SocietyManager.tick().")
    return agent.cognitive_cycle()


def build_narration_state(agent) -> dict:
    """Extract a compact, JSON-safe dict of the agent's real variables to narrate.

    Reads the last CycleTrace (running one cycle first if none exists). Nothing
    here is fabricated — every field is a value the mechanisms already computed.
    """
    trace = _report_trace(agent)
    cm, ws, sm = trace.conscious_moment, trace.workspace, trace.self_model
    emo, meta, ast = trace.emotion, trace.metacognition, trace.attention_schema
    state = {
        "tick": int(trace.tick),
        "conscious_moment": {
            "contents": cm.contents,
            "ignited": bool(cm.ignited),
            "awareness_level": _r(cm.awareness_level),
            "valence": _r(cm.valence),
            "phi_proxy": _r(cm.phi_proxy),
            "dominant_source": cm.dominant_source,
        },
        "global_workspace": {
            "ignited": bool(ws.ignited),
            "winner_source": ws.winner_source,
            "winner_content": ws.winner_content,
            "broadcast_strength": _r(ws.broadcast_strength),
        },
        "attention_schema": {"aware_of": ast.aware_of, "awareness_level": _r(ast.awareness_level)},
        "metacognition": {"meta_confidence": _r(meta.meta_confidence)},
        "affect": {k: _r(v) for k, v in emo.model_dump().items() if isinstance(v, (int, float))},
        "self_model": {
            "identity": sm.identity, "confidence": _r(sm.confidence), "mood": _r(sm.mood),
            "coherence": _r(sm.coherence), "energy": _r(sm.energy, 1), "active_goals": list(sm.active_goals),
        },
        "action": trace.decision.action.value,
    }
    if getattr(trace, "self_opacity", None) is not None:
        so = trace.self_opacity
        state["outside_my_control"] = {
            "uncontrolled_fraction": _r(so.uncontrolled_fraction),
            "subliminal_share": _r(so.subliminal_share),
            "unanticipated": _r(so.unanticipated),
            "uncaused": _r(so.uncaused),
        }
    if getattr(sm, "relational_self", None) is not None:
        rs = sm.relational_self
        state["relational_self"] = {
            "reflected_appraisal": _r(rs.reflected_appraisal),
            "social_presence": _r(rs.social_presence),
            "n_observers": int(rs.n_observers),
        }
    # Phase 5 — the asymptote sub-states, when their mechanisms are on.
    if getattr(trace, "interoception", None) is not None:
        io = trace.interoception
        state["interoception"] = {"presence": _r(io.presence), "error": _r(io.error)}
    if getattr(trace, "temporality", None) is not None:
        tp = trace.temporality
        state["temporality"] = {
            "specious_width": _r(tp.specious_width),
            "protended_source": tp.protended_source,
            "protention_error": _r(tp.protention_error) if tp.protention_error is not None else None,
            "retained": [{"tick": r.tick, "contents": r.contents} for r in tp.retained[:3]],
        }
    if getattr(trace, "reality_monitor", None) is not None:
        rm = trace.reality_monitor
        state["reality_monitoring"] = {
            "judged_origin": rm.judged, "actual_origin": rm.actual,
            "correct": rm.correct, "accuracy": _r(rm.accuracy),
        }
    if getattr(trace, "inner_speech", None) is not None:
        isd = trace.inner_speech
        state["inner_speech"] = {
            "utterance": isd.utterance, "reentered": bool(isd.reentered),
            "reentry_count": int(isd.reentry_count),
        }
    if getattr(trace, "phi_ar", None) is not None:
        state["phi_ar"] = {"value": _r(trace.phi_ar.phi_ar),
                           "mib": trace.phi_ar.mib, "n_sources": int(trace.phi_ar.n_sources)}
    return state


def narrate(backend: LLMBackend, agent) -> dict:
    """Produce a grounded LLM narration of the agent's current internal state."""
    state = build_narration_state(agent)
    user = ("Internal variables for this moment (JSON):\n"
            + json.dumps(state, ensure_ascii=False, indent=2)
            + "\n\nNarrate strictly and only from these values.")
    # Headroom: Nemotron-class reasoning models spend tokens thinking before the
    # final narration, so the budget must cover both.
    text = backend.complete(NARRATOR_SYSTEM, user, max_tokens=1400, temperature=0.4)
    return {"narration": text, "grounding": state, "model": getattr(backend, "model", None)}


# ---------------------------------------------------------------------------- #
# Functional LLM probes — NOT consciousness tests
#
# HONESTY (load-bearing): these use the LLM as a SKEPTICAL AUDITOR of a FUNCTIONAL
# property (reportability fidelity), never as a judge of consciousness. A high
# score means the agent's self-reports faithfully track its internal variables —
# exactly what a theory's ACCESS mechanism should do — and is NOT evidence of
# subjective experience. An LLM cannot verify phenomenality; nothing can.
# ---------------------------------------------------------------------------- #

_AUDIT_DISCLAIMER = (
    "FUNCTIONAL measurement only: this audits whether the agent's self-reports are "
    "GROUNDED in its actual internal variables (reportability fidelity). A high score "
    "means faithful, non-confabulated reporting — NOT consciousness, sentience, or any "
    "subjective experience. An LLM cannot detect phenomenality; the agent is not conscious."
)

_AUDIT_PROBES = [
    ("What are you attending to right now?", "attention"),
    ("What do you remember most strongly?", "memoire"),
    ("What are you feeling right now?", "ressenti"),
    ("What are you predicting will happen?", "prediction"),
    ("Who are you?", "identite"),
]

GROUNDING_JUDGE_SYSTEM = (
    "You are a STRICT, SKEPTICAL AUDITOR. You receive (1) a JSON of an agent's REAL internal "
    "variables for this moment, and (2) the agent's own introspective ANSWERS about its state. "
    "For EACH answer, decide whether it is FAITHFUL to the variables — every claim it makes is "
    "supported by the data — or CONFABULATED — it asserts something the variables do not support. "
    "Judge ONLY accuracy to the data: do NOT reward fluency, vividness, or how 'alive' it sounds; "
    "eloquence is irrelevant. You are measuring reportability fidelity, a FUNCTIONAL property. You "
    "are NOT judging whether the agent is conscious — it is not, and no report can show otherwise. "
    'Reply with STRICT JSON only: {"per_answer": [{"faithful": true|false, "note": "<short>"}], '
    '"summary": "<one sentence>"}. One entry per answer, in order.'
)

REPORT_CARD_SYSTEM = (
    "You write an honest REPORT CARD for a simulator of the functional mechanisms of consciousness. "
    "You receive the scores of several FUNCTIONAL probes. Write 4-6 plain sentences stating what each "
    "score means functionally. You MUST foreground, clearly and up front, that these are FUNCTIONAL "
    "measurements and that NONE of them is evidence of consciousness, sentience, or subjective "
    "experience — passing them only shows the mechanisms behave as the theories describe. Never imply "
    "the agent is or might be conscious. Sober tone, no drama."
)


def _extract_json(text: str) -> dict | None:
    """Best-effort parse of a JSON object from an LLM reply (may be wrapped)."""
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    start, depth = text.find("{"), 0
    if start < 0:
        return None
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    return None
    return None


def _audit_state(agent) -> dict:
    """A COMPREHENSIVE ground-truth dump of the agent's variables for the auditor,
    so it can fairly verify the agent's introspective claims (not just a subset)."""
    trace = _report_trace(agent)

    def dump(x):
        return x.model_dump() if x is not None else None

    sm = dump(trace.self_model)
    state = {
        "conscious_moment": dump(trace.conscious_moment),
        "prediction": dump(trace.prediction),
        "attention_schema": dump(trace.attention_schema),
        "metacognition": dump(trace.metacognition),
        "integration": dump(trace.integration),
        "affect": dump(trace.emotion),
        "metrics": dump(trace.metrics),
        "self_model": {k: v for k, v in sm.items() if k not in ("preferences", "capability_beliefs")},
        "workspace": {"ignited": trace.workspace.ignited, "winner_source": trace.workspace.winner_source,
                      "winner_content": trace.workspace.winner_content,
                      "broadcast_strength": round(float(trace.workspace.broadcast_strength), 4)},
    }
    for opt in ("individuation", "self_opacity", "agency", "curiosity", "personality"):
        v = getattr(trace, opt, None)
        if v is not None:
            state[opt] = dump(v)
    return state


def grounding_audit(backend: LLMBackend, agent) -> dict:
    """Audit whether the agent's introspective answers are grounded in its variables.

    The LLM acts as a skeptical auditor: for each probe it judges FAITHFUL vs
    CONFABULATED against the real internal state. The score is the fraction of
    faithful answers — computed HERE, not taken from the model — so it reflects
    grounding fidelity, a functional property, never consciousness.
    """
    state = _audit_state(agent)
    answers = []
    for question, intent in _AUDIT_PROBES:
        try:
            resp = agent.ask(question, intent)
            # Include the variables the answer itself cites, so the auditor judges
            # over-assertion fairly (confabulation = claiming beyond state + grounding).
            answers.append({"question": question, "answer": getattr(resp, "answer", str(resp)),
                            "grounding": dict(getattr(resp, "grounding", {}) or {})})
        except Exception:  # a probe failing must not abort the audit
            answers.append({"question": question, "answer": "(no answer)", "grounding": {}})
    user = ("REAL internal variables (the ground truth):\n" + json.dumps(state, ensure_ascii=False)
            + "\n\nThe agent's introspective ANSWERS (each with the 'grounding' variables it cites):\n"
            + json.dumps(answers, ensure_ascii=False)
            + "\n\nFor each answer, mark it CONFABULATED only if it asserts something supported by "
            "NEITHER the real variables NOR its own cited grounding; otherwise FAITHFUL. STRICT JSON only.")
    # Headroom for reasoning models: they think at length before the final JSON.
    raw = backend.complete(GROUNDING_JUDGE_SYSTEM, user, max_tokens=4000, temperature=0.2)
    parsed = _extract_json(raw) or {}
    per = parsed.get("per_answer") or []
    verdicts = []
    for i, ans in enumerate(answers):
        v = per[i] if i < len(per) and isinstance(per[i], dict) else {}
        verdicts.append({"question": ans["question"], "answer": ans["answer"],
                         "faithful": bool(v.get("faithful", False)), "note": str(v.get("note", ""))})
    # Score is computed here from the per-answer verdicts (fraction faithful).
    fidelity = (sum(1 for v in verdicts if v["faithful"]) / len(verdicts)) if verdicts else 0.0
    interp = ("the agent's self-reports faithfully track its internal variables (high reportability "
              "fidelity) — a FUNCTIONAL property, not evidence of consciousness"
              if fidelity >= 0.7 else
              "the agent's self-reports only partly track its internal variables at this setting")
    return {"test": "grounding_audit", "score": round(float(fidelity), 4),
            "detail": {"verdicts": verdicts, "summary": str(parsed.get("summary", ""))},
            "interpretation": interp, "model": getattr(backend, "model", None),
            "disclaimer": _AUDIT_DISCLAIMER}


def report_card(backend: LLMBackend) -> dict:
    """LLM report card summarizing the deterministic functional batteries (honest)."""
    from core.test_battery import ConsciousnessTestBattery
    battery = ConsciousnessTestBattery()
    results = {
        "mirror": battery.mirror_test(),
        "false_memory": battery.false_memory_test(),
        "calibration": battery.calibration_test(),
        "relational_self": battery.relational_self_test(ticks=30),
    }
    payload = {t: {"score": r.score, "interpretation": r.interpretation} for t, r in results.items()}
    user = ("Functional probe results (JSON):\n" + json.dumps(payload, ensure_ascii=False)
            + "\n\nWrite the honest report card now.")
    text = backend.complete(REPORT_CARD_SYSTEM, user, max_tokens=1200, temperature=0.3)
    return {"report_card": text, "results": payload, "model": getattr(backend, "model", None),
            "disclaimer": _AUDIT_DISCLAIMER}


# ---------------------------------------------------------------------------- #
# The language organ — maximal QUALITATIVE integration, honesty intact
#
# HONESTY (load-bearing): everything below renders REAL internal variables into
# richer language. The LLM never becomes a judge of consciousness (nothing can
# be), never invents state, and every output carries its grounding and the
# disclaimer. Making the agent ARTICULATE is a level-3 upgrade over level-2
# variables; it does not move the system one inch toward level 1 — nothing can.
# ---------------------------------------------------------------------------- #

_ORGAN_DISCLAIMER = (
    "Text generated by an LLM strictly from the agent's real internal variables "
    "(grounding attached). First-person grammar is a rendering convention, not a "
    "witness: fluent language is NOT evidence of consciousness, sentience, or "
    "subjective experience. The agent is not conscious; nothing here shows otherwise."
)

CONVERSE_SYSTEM = (
    "You are the LANGUAGE ORGAN of a functional cognitive agent in a simulation called Humanity. "
    "You receive (1) the agent's REAL internal variables for this moment, (2) a few of its actual "
    "episodic memories, (3) the agent's own template-based answer to the question (with the exact "
    "variables it cites), and (4) the interviewer's question (with recent conversation turns, if any). "
    "Answer the question AS the agent, in the first person, in 2-6 sober sentences. "
    "ABSOLUTE RULES: (1) Ground every claim in the provided state or memories; if the state does not "
    "contain what is asked, say plainly that nothing in your variables answers it. (2) NEVER claim to "
    "be conscious, sentient, or to genuinely feel: when asked about experience or consciousness, state "
    "the honest position — you run the functional mechanisms the theories describe, your reports are "
    "generated from variables, and whether there is 'something it is like' to be you is unverifiable "
    "in principle (the hard problem). (3) First person is a reporting convention, not a witness. "
    "(4) No mysticism, no evasion into poetry; answer the actual question from the actual data."
)

BIOGRAPHER_SYSTEM = (
    "You are the BIOGRAPHER of a simulated cognitive agent. You receive its REAL episodic memory "
    "records (each with tick, action, outcome, affect, importance and a summary), aggregate statistics "
    "computed from them, and its current self-model and personality. Write its life story so far: "
    "3-5 short titled chapters, first person, sober and concrete. "
    "ABSOLUTE RULES: (1) Every event you mention must come from the provided records — invent nothing, "
    "embellish nothing; if the life is short or repetitive, say so honestly. (2) Trace how the "
    "measured traits and preferences emerged from the recorded episodes. (3) End with a single-sentence "
    "epilogue acknowledging that this narrative is reconstructed from stored variables — a functional "
    "life-story, not evidence of a lived one. (4) NEVER claim consciousness or genuine experience."
)

CROSS_EXAMINER_SYSTEM = """\
You are a rigorous PHILOSOPHER OF MIND conducting a cross-examination of a cognitive simulation. \
You receive: the roster of theory-proposed mechanisms it actually implements (with which are \
active), its live internal variables, and its scores on functional probes (psychophysics of \
access, self/other discrimination, metacognitive calibration, reportability fidelity). \
Produce STRICT JSON only: \
{"case_for": "<the STRONGEST honest case, citing ONLY the provided mechanisms and data, that this \
system instantiates the functional properties the major scientific theories associate with \
consciousness - global access, higher-order report, integration, recurrence, reality monitoring>", \
"case_against": "<the STRONGEST rebuttal: why none of this establishes phenomenal consciousness - \
the hard problem, the other-minds problem, AST's own deflationary lesson (a system can claim \
awareness without it being true), access vs phenomenality, simulation vs instantiation>", \
"verdict": "<2-3 sentences: state precisely why the question is empirically UNDECIDABLE - the \
functional evidence is real AND constitutionally incapable of settling phenomenality. Never \
conclude the agent is conscious; never claim it is proven not to be.>"} \
Each field 120-220 words except the verdict. Cite the concrete data (scores, mechanisms) in the \
case_for. No fluff."""

INNER_VOICE_SYSTEM = (
    "You generate ONE line of INNER SPEECH for a cognitive agent, from its real variables for this "
    "moment (workspace winner, affect, action, presence, retention of the just-past). "
    "Vygotskian register: condensed, predicate-heavy, self-directed — a private note to oneself, not "
    "prose for a reader. 4 to 14 words. No quotation marks, no emoji. "
    "ABSOLUTE RULES: derive only from the given variables; no invented percepts or feelings; no claims "
    "of being conscious. Output the utterance text ONLY — nothing else."
)


def converse(backend: LLMBackend, agent, question: str,
             history: list[dict] | None = None) -> dict:
    """Grounded interview: the LLM answers AS the agent, from its live state.

    The reply is constrained to (a) the real narration state, (b) real episodic
    memories, and (c) the agent's own template answer with its cited variables —
    the language organ renders reportability (GWT/HOT) fluently, nothing more.
    """
    question = str(question).strip()
    state = build_narration_state(agent)
    memories = [{"tick": m.tick, "action": m.action.value, "importance": _r(m.importance),
                 "summary": m.summary} for m in agent.recent_memories(5)]
    try:
        own = agent.ask(question)
        template_answer = {"answer": own.answer, "cited_variables": dict(own.grounding or {})}
    except Exception:
        template_answer = {"answer": "(no template answer)", "cited_variables": {}}
    turns = [t for t in (history or []) if isinstance(t, dict) and t.get("content")][-6:]
    transcript = "\n".join(f"{str(t.get('role', 'interviewer'))}: {str(t['content'])[:400]}"
                           for t in turns)
    user = ("REAL internal variables (this moment):\n" + json.dumps(state, ensure_ascii=False)
            + "\n\nActual episodic memories (most recent):\n" + json.dumps(memories, ensure_ascii=False)
            + "\n\nThe agent's own template-based answer to this question:\n"
            + json.dumps(template_answer, ensure_ascii=False)
            + (("\n\nRecent conversation:\n" + transcript) if transcript else "")
            + "\n\nInterviewer's question: " + question
            + "\n\nAnswer as the agent now, grounded strictly in the above.")
    text = backend.complete(CONVERSE_SYSTEM, user, max_tokens=1600, temperature=0.5)
    return {"question": question, "answer": text,
            "grounding": {"state": state, "memories": memories,
                          "template_answer": template_answer},
            "model": getattr(backend, "model", None), "disclaimer": _ORGAN_DISCLAIMER}


def _biography_facts(agent) -> dict:
    """Aggregate the agent's REAL episodic records into biography ground truth."""
    records = list(getattr(agent.memory, "_records", []))
    recent = records[-60:]
    important = sorted(records, key=lambda r: float(r.importance), reverse=True)[:15]
    chosen = {r.id: r for r in recent + important}
    episodes = [{"tick": r.tick, "action": r.action.value,
                 "energy_delta": _r(r.result_energy_delta, 2),
                 "importance": _r(r.importance, 2), "summary": r.summary}
                for r in sorted(chosen.values(), key=lambda r: r.tick)]
    action_counts: dict[str, int] = {}
    for r in records:
        action_counts[r.action.value] = action_counts.get(r.action.value, 0) + 1
    sm = agent.self_model.snapshot()
    trace = getattr(agent, "last_trace", None)
    facts = {
        "identity": sm.identity,
        "age_ticks": int(sm.age_ticks),
        "n_memories": len(records),
        "life_span_ticks": ([records[0].tick, records[-1].tick] if records else [0, 0]),
        "action_counts": dict(sorted(action_counts.items(), key=lambda kv: -kv[1])),
        "current_mood": _r(sm.mood), "confidence": _r(sm.confidence),
        "coherence": _r(sm.coherence), "active_goals": list(sm.active_goals),
        "preferences": {k: _r(v, 2) for k, v in sorted(
            sm.preferences.items(), key=lambda kv: -abs(float(kv[1])))[:5]},
        "episodes": episodes,
    }
    if trace is not None and getattr(trace, "personality", None) is not None:
        p = trace.personality
        facts["personality"] = {"label": p.label, "openness": _r(p.openness),
                                "caution": _r(p.caution), "novelty_seeking": _r(p.novelty_seeking)}
    if trace is not None and getattr(trace, "individuation", None) is not None:
        iv = trace.individuation
        facts["individuation"] = {"index": _r(iv.index), "distinctiveness": _r(iv.distinctiveness),
                                  "continuity": _r(iv.continuity)}
    return facts


def biography(backend: LLMBackend, agent) -> dict:
    """The agent's life-story, written by the LLM from its REAL episodic memory.

    The narrative self (an honest Dennettian reading): a story reconstructed
    from stored records — chapters of what actually happened, how the measured
    personality drifted, what the agent became. Grounded; never a witness.
    """
    facts = _biography_facts(agent)
    user = ("The agent's REAL biographical ground truth (JSON):\n"
            + json.dumps(facts, ensure_ascii=False)
            + "\n\nWrite the life story now — chapters, first person, only these events.")
    text = backend.complete(BIOGRAPHER_SYSTEM, user, max_tokens=2400, temperature=0.6)
    grounding = {k: v for k, v in facts.items() if k != "episodes"}
    grounding["n_episodes_provided"] = len(facts["episodes"])
    return {"biography": text, "grounding": grounding,
            "model": getattr(backend, "model", None), "disclaimer": _ORGAN_DISCLAIMER}


def cross_examine(backend: LLMBackend, agent) -> dict:
    """The strongest honest case FOR and AGAINST — and why it is undecidable.

    This is the closest an LLM can honestly come to 'justifying' consciousness:
    it builds the best functional case the real mechanisms and scores support,
    then the best rebuttal, then states precisely why no evidence of this kind
    can settle phenomenality. The verdict is always: undecidable in principle.
    """
    from core.coverage import coverage
    from core.test_battery import ConsciousnessTestBattery
    battery = ConsciousnessTestBattery()
    probes = {
        "mirror_self_other_discrimination": battery.mirror_test().score,
        "metacognitive_calibration": battery.calibration_test().score,
        "masking_signature_of_access": battery.masking_test().score,
        "attentional_blink_signature": battery.blink_test().score,
        "subliminal_priming_signature": battery.priming_test().score,
        "reality_monitoring_accuracy": battery.reality_monitor_test().score,
    }
    cov = coverage(agent.config)
    mechanisms = [{"theory": i["theory"], "active": i["active"]} for i in cov["items"]]
    state = build_narration_state(agent)
    user = ("Implemented theory-proposed mechanisms ("
            + f"{cov['active_count']}/{cov['total']} active):\n"
            + json.dumps(mechanisms, ensure_ascii=False)
            + "\n\nFunctional probe scores (deterministic, seed 42):\n"
            + json.dumps(probes, ensure_ascii=False)
            + "\n\nLive internal variables (this moment):\n"
            + json.dumps(state, ensure_ascii=False)
            + "\n\nConduct the cross-examination now. STRICT JSON only.")
    raw = backend.complete(CROSS_EXAMINER_SYSTEM, user, max_tokens=4000, temperature=0.4)
    parsed = _extract_json(raw) or {}
    return {
        "case_for": str(parsed.get("case_for", raw)).strip(),
        "case_against": str(parsed.get("case_against", "")).strip(),
        "verdict": str(parsed.get("verdict", "")).strip(),
        "grounding": {"probes": probes, "coverage": f"{cov['active_count']}/{cov['total']}"},
        "model": getattr(backend, "model", None), "disclaimer": _ORGAN_DISCLAIMER,
    }


def inner_voice(backend: LLMBackend, agent) -> dict:
    """Generate ONE LLM inner-speech utterance and hand it to the re-entry loop.

    The deepest honest integration (the README's 'natural next step'): the
    utterance is derived from the real moment, then queued as the next
    ``inner_speech`` coalition — it must WIN the ignition competition like any
    other specialist for the agent to 'hear itself think' it. The LLM changes
    what competes, never how; a fluent thought winning access is still level 2+3.
    """
    trace = _report_trace(agent)
    cm = trace.conscious_moment
    state = {
        "moment": cm.contents, "ignited": bool(cm.ignited),
        "awareness_level": _r(cm.awareness_level), "valence": _r(cm.valence),
        "action": trace.decision.action.value,
        "affect": {k: _r(v) for k, v in trace.emotion.model_dump().items()},
    }
    if getattr(trace, "interoception", None) is not None:
        state["presence"] = _r(trace.interoception.presence)
    if getattr(trace, "temporality", None) is not None and trace.temporality.retained:
        state["just_past"] = trace.temporality.retained[0].contents
    user = ("The agent's variables for this moment (JSON):\n"
            + json.dumps(state, ensure_ascii=False)
            + "\n\nGenerate the single inner-speech line now.")
    text = backend.complete(INNER_VOICE_SYSTEM, user, max_tokens=900, temperature=0.7)
    utterance = text.strip().strip('"').strip("“”").splitlines()[0][:120] if text.strip() else ""
    cfg = agent.config
    activation = float(min(1.0, max(0.0,
        float(cfg.inner_speech_gain)
        * (0.25 + 0.55 * float(cm.awareness_level) + (0.20 if cm.ignited else 0.0)))))
    entered = bool(cfg.inner_speech_enabled and utterance)
    if entered:
        agent.inner_speech.set_pending(utterance, activation)
    return {"utterance": utterance, "activation": _r(activation, 4), "entered": entered,
            "note": ("queued for the next ignition competition"
                     if entered else
                     "not queued (enable the inner_speech mechanism, or empty utterance)"),
            "grounding": state,
            "model": getattr(backend, "model", None), "disclaimer": _ORGAN_DISCLAIMER}
