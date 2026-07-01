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
