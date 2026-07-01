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


def build_narration_state(agent) -> dict:
    """Extract a compact, JSON-safe dict of the agent's real variables to narrate.

    Reads the last CycleTrace (running one cycle first if none exists). Nothing
    here is fabricated — every field is a value the mechanisms already computed.
    """
    trace = agent.last_trace if getattr(agent, "last_trace", None) is not None else agent.cognitive_cycle()
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
    trace = agent.last_trace if getattr(agent, "last_trace", None) is not None else agent.cognitive_cycle()

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
