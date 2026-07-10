"""Tests for the grounded INTERACTION layer of Humanity.

These exercise the five interaction modalities wired into
``core.agent.CognitiveAgent`` (and surfaced over HTTP in ``app.api.routes``):

* dialogue  -- ``ask()`` -> grounded French :class:`AskResponse` (GWT/HOT reportability).
* injection -> ignition -- ``inject()`` queues a workspace coalition (GWT ignition threshold).
* attention steering -- ``attend()`` biases top-down saliency (AST).
* perturbation -- ``perturb()`` applies choc / surprise / apaisement to internal state.
* world stimulus -- ``world_stimulus()`` injects a real bottom-up :class:`WorldObject`.

Plus a TestClient pass over the documented interaction endpoints.

Everything is DETERMINISTIC: fixed ``random_seed`` and ``world_noise=0.0`` (no
stochastic world events), and there are no sleeps. The API portion follows the
existing suite convention of skipping gracefully when the web stack is absent,
so it never breaks the rest of the suite.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.agent import CognitiveAgent
from schemas.models import (
    AskResponse,
    AttendRequest,
    CognitiveInjection,
    PerturbRequest,
    SimConfig,
    WorldObject,
    WorldStimulus,
)
from storage.persistence import MemoryStore
from storage.trace_logger import TraceLogger


# --------------------------------------------------------------------------- #
# Helpers / fixtures
# --------------------------------------------------------------------------- #
def _make_agent(tmp_path, **overrides) -> CognitiveAgent:
    """Build a deterministic CognitiveAgent with persistence redirected to tmp.

    Seed is fixed and ``world_noise`` is 0.0 so observations carry no jitter and
    no stochastic world events fire -- every assertion below is reproducible.
    """
    cfg = SimConfig(random_seed=42, world_noise=0.0, stream_length=5, **overrides)
    ag = CognitiveAgent(cfg)
    ag.memory_store = MemoryStore(tmp_path / "memory.json")
    ag.memory._store = ag.memory_store
    ag.trace_logger = TraceLogger(tmp_path / "traces.jsonl")
    return ag


@pytest.fixture()
def agent(tmp_path) -> CognitiveAgent:
    """A default deterministic agent for the in-process interaction tests."""
    return _make_agent(tmp_path)


# Each question maps to a specific detected intent (see core.dialogue).
_INTENT_QUESTIONS = [
    ("What are you attending to?", "attention"),
    ("Why did you do that?", "reason"),
    ("What do you remember?", "memory"),
    ("How do you feel?", "feeling"),
    ("Who are you?", "identity"),
    ("What do you predict?", "prediction"),
    ("Are you conscious?", "consciousness"),
]


# --------------------------------------------------------------------------- #
# 1) Dialogue: ask() returns a grounded AskResponse
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("question, expected_intent", _INTENT_QUESTIONS)
def test_ask_returns_grounded_response_per_intent(
    agent: CognitiveAgent, question: str, expected_intent: str
) -> None:
    """ask() returns an AskResponse with a non-empty FR answer + disclaimer.

    The detected intent must be the sensible one for the question, the answer is
    explicitly framed as generated from internal variables, and the grounding
    dict names the variables that were read.
    """
    agent.cognitive_cycle()
    resp = agent.ask(question)

    assert isinstance(resp, AskResponse)
    assert resp.question == question
    # Detected intent is sensible (no explicit override was passed).
    assert resp.intent == expected_intent
    # Non-empty English answer, framed as a report from internal variables.
    assert isinstance(resp.answer, str)
    assert len(resp.answer.strip()) > 20
    assert resp.answer.startswith("Based on my internal variables,")
    # The canonical functional-simulation disclaimer accompanies every answer.
    assert isinstance(resp.disclaimer, str)
    assert resp.disclaimer.strip()
    # Grounding names which internal variables were read.
    assert isinstance(resp.grounding, dict)
    assert len(resp.grounding) >= 1


def test_ask_runs_a_cycle_when_none_has_happened(tmp_path) -> None:
    """ask() before any tick first runs one cycle so there is real state."""
    ag = _make_agent(tmp_path)
    assert ag.last_trace is None
    resp = ag.ask("Who are you?")
    assert ag.last_trace is not None
    assert resp.intent == "identity"
    assert resp.answer.strip()


def test_ask_respects_explicit_intent_override(agent: CognitiveAgent) -> None:
    """An explicit intent argument overrides keyword detection."""
    agent.cognitive_cycle()
    # The question reads like 'attention', but we force the 'prediction' intent.
    resp = agent.ask("What are you attending to?", intent="prediction")
    assert resp.intent == "prediction"
    assert resp.answer.strip()


# --------------------------------------------------------------------------- #
# 2) Injection -> ignition (GWT ignition threshold: conscious vs subliminal)
# --------------------------------------------------------------------------- #
def test_strong_injection_adds_coalition_and_ignites(tmp_path) -> None:
    """A strong injection adds a coalition AND ignites with the injected source.

    Ignition depends on the winner's absolute drive AND its dominance, gated by
    an arousal-modulated threshold. At the nominal ignition threshold the
    activation=0.99/precision=0.99 injection wins the workspace, crosses the
    threshold, and becomes the broadcast source.
    """
    ag = _make_agent(tmp_path, workspace_temp=0.2, ignition_threshold=0.30)
    ag.cognitive_cycle()
    n_before = len(ag.last_trace.workspace.competition)

    accepted = ag.inject(
        CognitiveInjection(
            content="strong injected signal",
            source="injection",
            activation=0.99,
            precision=0.99,
            ttl=1,
        )
    )
    assert accepted["accepted"] is True
    assert accepted["pending"] == 1

    trace = ag.cognitive_cycle()
    ws = trace.workspace

    # An extra coalition entered the competition on the next cycle.
    assert len(ws.competition) > n_before
    assert any(c.source == "injection" for c in ws.competition)
    # The injected content crossed the ignition threshold and won global access.
    assert ws.ignited is True
    assert ws.winner_source == "injection"


def test_weak_injection_does_not_force_ignition(tmp_path) -> None:
    """A weak (low-activation) injection does NOT force ignition / does not win.

    The same machinery with a near-zero activation injection leaves the workspace
    un-ignited and the injection is not the broadcast winner -- it stays a
    subliminal bid.
    """
    ag = _make_agent(tmp_path, workspace_temp=0.2, ignition_threshold=0.55)
    ag.cognitive_cycle()

    ag.inject(
        CognitiveInjection(
            content="weak injected signal",
            source="injection",
            activation=0.05,
            precision=0.10,
            ttl=1,
        )
    )
    trace = ag.cognitive_cycle()
    ws = trace.workspace

    # The weak injection did NOT force ignition through the injected source.
    assert not (ws.ignited and ws.winner_source == "injection")
    assert ws.winner_source != "injection"


def test_injection_ttl_expires_after_its_cycles(tmp_path) -> None:
    """A ttl=1 injection competes for exactly one cycle, then is dropped."""
    ag = _make_agent(tmp_path, workspace_temp=0.2, ignition_threshold=0.55)
    ag.cognitive_cycle()

    ag.inject(CognitiveInjection(content="ephemeral", activation=0.99, precision=0.99, ttl=1))
    assert len(ag._pending_injections) == 1

    # First post-injection cycle: it competes (and the ttl ticks to 0 -> dropped).
    trace1 = ag.cognitive_cycle()
    assert any(c.source == "injection" for c in trace1.workspace.competition)
    assert len(ag._pending_injections) == 0

    # Next cycle: no injected coalition remains.
    trace2 = ag.cognitive_cycle()
    assert not any(c.source == "injection" for c in trace2.workspace.competition)


# --------------------------------------------------------------------------- #
# 3) Attention steering (AST: top-down saliency bias)
# --------------------------------------------------------------------------- #
def test_attend_boosts_target_saliency_versus_no_bias(tmp_path) -> None:
    """attend() raises the targeted object's saliency vs an unbiased run.

    Two identically-seeded agents run the same two cycles; the only difference is
    that one issues an attend-bias toward the top object before the second cycle.
    The biased agent's saliency for that target must be strictly higher.
    """
    # Identify the salient target after the first cycle (identical for both runs).
    probe = _make_agent(tmp_path / "probe")
    first = probe.cognitive_cycle()
    target_id = first.salient[0].percept.object_id

    # Control run: no bias.
    control = _make_agent(tmp_path / "control")
    control.cognitive_cycle()
    control_trace = control.cognitive_cycle()
    control_sal = {s.percept.object_id: s.saliency for s in control_trace.salient}

    # Biased run: steer attention toward the target before the second cycle.
    biased = _make_agent(tmp_path / "biased")
    biased.cognitive_cycle()
    ack = biased.attend(AttendRequest(target_id=target_id, strength=2.0, ttl=3))
    assert ack["ok"] is True
    assert ack["target_id"] == target_id
    biased_trace = biased.cognitive_cycle()
    biased_sal = {s.percept.object_id: s.saliency for s in biased_trace.salient}

    # The target is still attended in both runs, and its saliency increased.
    assert target_id in control_sal
    assert target_id in biased_sal
    assert biased_sal[target_id] > control_sal[target_id]
    # The boosted target is at least as competitive: it leads the salient list.
    assert biased_trace.salient[0].percept.object_id == target_id


def test_attend_bias_ttl_decrements_each_cycle(tmp_path) -> None:
    """The attend bias ttl ticks down each cycle and the bias drops at zero."""
    ag = _make_agent(tmp_path)
    first = ag.cognitive_cycle()
    target_id = first.salient[0].percept.object_id

    ag.attend(AttendRequest(target_id=target_id, strength=1.0, ttl=2))
    assert ag._attend_bias is not None and ag._attend_bias.ttl == 2

    ag.cognitive_cycle()
    # ttl decremented (still > 0 so the bias is retained).
    assert ag._attend_bias is not None and ag._attend_bias.ttl == 1

    ag.cognitive_cycle()
    # ttl hit zero -> the bias is dropped.
    assert ag._attend_bias is None


# --------------------------------------------------------------------------- #
# 4) Perturbation (choc / surprise / apaisement)
# --------------------------------------------------------------------------- #
def test_perturb_choc_lowers_energy(agent: CognitiveAgent) -> None:
    """perturb(choc) drains world energy (and syncs the self-model's view)."""
    agent.cognitive_cycle()
    energy_before = float(agent.world.agent_energy)

    effect = agent.perturb(PerturbRequest(type="choc", magnitude=2.0))

    assert effect["type"] == "choc"
    energy_after = float(agent.world.agent_energy)
    assert energy_after < energy_before
    # The reported energy and the synced self-model energy match the world.
    assert effect["energy"] == pytest.approx(energy_after, abs=1e-4)
    assert float(agent.self_model._state.energy) == pytest.approx(energy_after, abs=1e-4)


def test_perturb_choc_reports_actual_clamped_energy_loss(tmp_path) -> None:
    agent = _make_agent(tmp_path, initial_energy=5.0)
    before = float(agent.world.agent_energy)

    effect = agent.perturb(PerturbRequest(type="shock", magnitude=1.0))

    assert before == pytest.approx(5.0)
    assert effect["energy"] == 0.0
    assert effect["drained"] == pytest.approx(before)


def test_perturb_surprise_raises_next_cycle_error_and_confusion(tmp_path) -> None:
    """perturb(surprise) raises the NEXT cycle's prediction_error + confusion.

    Compared against an identically-seeded control agent that received no
    surprise, the perturbed agent's next-cycle prediction error and confusion are
    both strictly higher (active-inference: forced surprise feeds the error
    monitor and the confusion affect).
    """
    control = _make_agent(tmp_path / "control")
    control.cognitive_cycle()
    control_next = control.cognitive_cycle()

    perturbed = _make_agent(tmp_path / "perturbed")
    perturbed.cognitive_cycle()
    effect = perturbed.perturb(PerturbRequest(type="surprise", magnitude=0.9))
    assert effect["type"] == "surprise"
    assert effect["pending_prediction_error"] == pytest.approx(0.9, abs=1e-4)
    perturbed_next = perturbed.cognitive_cycle()

    assert perturbed_next.metrics.prediction_error > control_next.metrics.prediction_error
    assert perturbed_next.emotion.confusion > control_next.emotion.confusion
    # The pending surprise is consumed (one-shot).
    assert perturbed._pending_surprise == 0.0


def test_perturb_apaisement_lowers_fear_and_raises_mood(agent: CognitiveAgent) -> None:
    """perturb(apaisement) reduces the fear scalar and raises self-model mood."""
    agent.cognitive_cycle()
    # Seed a non-trivial fear so the reduction is observable.
    agent.last_emotion.fear = 0.8
    mood_before = float(agent.self_model._state.mood)

    effect = agent.perturb(PerturbRequest(type="apaisement", magnitude=1.0))

    assert effect["type"] == "apaisement"
    assert float(agent.last_emotion.fear) < 0.8
    assert float(agent.self_model._state.mood) > mood_before
    assert effect["fear"] == pytest.approx(float(agent.last_emotion.fear), abs=1e-4)
    assert effect["mood"] == pytest.approx(float(agent.self_model._state.mood), abs=1e-4)


def test_perturb_unknown_type_is_rejected() -> None:
    """Unknown public perturbation types cannot become silent no-ops."""
    with pytest.raises(ValidationError):
        PerturbRequest(type="inconnu", magnitude=1.0)


# --------------------------------------------------------------------------- #
# 5) World stimulus (bottom-up: inject a real object into the world)
# --------------------------------------------------------------------------- #
def test_world_stimulus_adds_object_with_scaled_props(agent: CognitiveAgent) -> None:
    """world_stimulus() adds a WorldObject (count++) with intensity-scaled props."""
    count_before = len(agent.world.objects)

    obj = agent.world_stimulus(WorldStimulus(kind="hazard", intensity=3.0))

    assert isinstance(obj, WorldObject)
    assert len(agent.world.objects) == count_before + 1
    # The new object is registered and surfaced for perception.
    assert obj.id in agent.world.objects
    assert obj.id in agent.world.seen_counts
    assert obj.kind == "hazard"
    # A high-intensity hazard is dangerous (scaled into its valid band).
    assert obj.danger > 0.0


def test_world_stimulus_intensity_scales_food_energy(agent: CognitiveAgent) -> None:
    """Higher intensity yields a higher (scaled) energy_value for food."""
    low = agent.world_stimulus(WorldStimulus(kind="food", intensity=0.1))
    high = agent.world_stimulus(WorldStimulus(kind="food", intensity=2.0))
    assert high.energy_value > low.energy_value


def test_world_inject_object_directly_increases_count(agent: CognitiveAgent) -> None:
    """world.inject_object adds an object at clamped coordinates (count++)."""
    count_before = len(agent.world.objects)
    obj = agent.world.inject_object(kind="curio", x=0, y=0, intensity=1.0)
    assert len(agent.world.objects) == count_before + 1
    assert (obj.x, obj.y) == (0, 0)
    assert obj.novelty > 0.0


# --------------------------------------------------------------------------- #
# 6) HTTP interaction endpoints (TestClient) -- skipped if web stack absent
# --------------------------------------------------------------------------- #
# Probe the optional web stack once; skip the whole API section if unavailable
# (mirrors the existing test_api / test_consciousness_api convention).
_HAS_WEB = True
try:  # pragma: no cover - import guard
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
except Exception:  # pragma: no cover - missing optional deps
    _HAS_WEB = False

if _HAS_WEB:
    from fastapi.testclient import TestClient

    from app.main import app

    @pytest.fixture()
    def client(tmp_path):
        """TestClient over a fresh manager with persistence redirected to tmp."""
        import core.agent as agent_module
        from storage.persistence import MemoryStore as _MemoryStore
        from storage.trace_logger import TraceLogger as _TraceLogger

        agent_module._MANAGER = None
        manager = agent_module.get_manager()
        manager.agent(0).memory_store = _MemoryStore(tmp_path / "memory.json")
        manager.agent(0).memory._store = manager.agent(0).memory_store
        manager.agent(0).trace_logger = _TraceLogger(tmp_path / "traces.jsonl")

        with TestClient(app) as c:
            yield c

        agent_module._MANAGER = None


@pytest.mark.skipif(not _HAS_WEB, reason="fastapi/httpx not installed")
def test_api_ask_endpoint(client) -> None:
    """POST /agent/ask returns 200 with the documented AskResponse shape."""
    resp = client.post(
        "/agent/ask", json={"question": "What are you attending to?"}
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in ("question", "intent", "answer", "grounding", "disclaimer"):
        assert key in body
    assert body["intent"] == "attention"
    assert body["answer"].strip()
    assert body["disclaimer"].strip()
    assert isinstance(body["grounding"], dict)


@pytest.mark.skipif(not _HAS_WEB, reason="fastapi/httpx not installed")
def test_api_world_stimulus_endpoint(client) -> None:
    """POST /world/stimulus returns 200 with the injected object + state."""
    resp = client.post("/world/stimulus", json={"kind": "hazard", "intensity": 3.0})
    assert resp.status_code == 200
    body = resp.json()
    assert "object" in body and "state" in body
    obj = body["object"]
    assert obj["kind"] == "hazard"
    for key in ("id", "x", "y", "danger", "novelty"):
        assert key in obj


@pytest.mark.skipif(not _HAS_WEB, reason="fastapi/httpx not installed")
def test_api_inject_endpoint(client) -> None:
    """POST /agent/inject returns 200 acknowledging a queued coalition."""
    resp = client.post(
        "/agent/inject",
        json={"content": "signal", "activation": 0.99, "precision": 0.99, "ttl": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["accepted"] is True
    assert body["pending"] >= 1


@pytest.mark.skipif(not _HAS_WEB, reason="fastapi/httpx not installed")
def test_api_attend_endpoint(client) -> None:
    """POST /agent/attend returns 200 acknowledging the steering target."""
    resp = client.post("/agent/attend", json={"target_id": 0, "strength": 1.0, "ttl": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["target_id"] == 0


@pytest.mark.skipif(not _HAS_WEB, reason="fastapi/httpx not installed")
def test_api_perturb_endpoint(client) -> None:
    """POST /agent/perturb returns 200 with the applied effect + state."""
    client.post("/tick")
    resp = client.post("/agent/perturb", json={"type": "choc", "magnitude": 2.0})
    assert resp.status_code == 200
    body = resp.json()
    assert "effect" in body and "state" in body
    assert body["effect"]["type"] == "choc"
    assert "energy" in body["effect"]


@pytest.mark.skipif(not _HAS_WEB, reason="fastapi/httpx not installed")
def test_api_existing_endpoints_still_ok(client) -> None:
    """The pre-existing endpoints continue to return 200 alongside the new ones."""
    assert client.get("/state").status_code == 200
    assert client.post("/tick").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/agent/self-model").status_code == 200
    assert client.get("/agent/workspace").status_code == 200
