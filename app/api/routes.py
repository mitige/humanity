"""HTTP API for Humanity.

FUNCTIONAL NOTE
---------------
These endpoints expose the simulation's internal variables. The legacy
``/agent/*`` and ``/state`` endpoints target agent 0 of the society façade so the
single-agent instrument keeps working; ``/society/*`` exposes the multi-agent
view. All responses describe a FUNCTIONAL simulation; the agent is not conscious,
sentient, or alive.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from core.agent import get_manager
from core.society import SocietyManager
from core.constants import THEORY_FRAMING_EN, THEORY_FRAMING_FR
from core.scenario import ScenarioRunner
from core.test_battery import ConsciousnessTestBattery
from schemas.models import Scenario, ScenarioResult, BatteryResult
from schemas.models import (
    AskRequest,
    AskResponse,
    AttendRequest,
    CognitiveInjection,
    ConfigPatch,
    ConsciousMoment,
    CycleTrace,
    GoalRequest,
    IntrospectionReport,
    MemoryRecord,
    Metrics,
    PerturbRequest,
    RunRequest,
    SelfModelState,
    WorldStimulus,
    WorkspaceState,
)

DISCLAIMER_FR = (
    "Simulation fonctionnelle de processus associes a la conscience. "
    "L'agent n'est ni conscient, ni sentient, ni vivant. Les rapports "
    "introspectifs sont des textes generes a partir de variables internes et "
    "ne constituent pas une preuve d'experience subjective."
)
DISCLAIMER_EN = (
    "Functional simulation of processes associated with consciousness. The "
    "agent is not conscious, sentient, or alive. Introspective reports are text "
    "generated from internal variables and are not evidence of subjective "
    "experience."
)

router = APIRouter()


def _manager() -> SocietyManager:
    """Lazily obtain the process-wide society manager."""
    return get_manager()


def _agent0():
    """Legacy single-agent accessor: agent 0 of the society façade."""
    return _manager().agent(0)


def _legacy_world_snapshot() -> dict:
    """Solo-shaped world snapshot (singular ``agent``) for agent 0 of the society."""
    w = _manager().world
    a0 = w.agents[0]
    return {
        "grid_size": int(w.config.grid_size),
        "tick": int(w.tick),
        "agent": {"x": int(a0.x), "y": int(a0.y), "energy": round(float(a0.energy), 4)},
        "objects": [o.model_dump() for o in w.objects.values()],
    }


def _society_state_legacy() -> dict:
    """Legacy ``/state`` shape, sourced from agent 0 of the society."""
    mgr = _manager()
    ag = mgr.agent(0)
    metrics = ag.metrics()
    intro = ag._last_introspection
    ws = ag.workspace_state()
    return {
        "world": _legacy_world_snapshot(),
        "metrics": metrics.model_dump(),
        "running": bool(mgr.running),
        "introspection_summary": (
            intro.self_state if intro is not None else "No introspective report generated yet."
        ),
        "self_model": ag.self_model_state().model_dump(),
        "working_memory_load": float(ag.working_memory.load()),
        "phi_proxy": float(metrics.phi_proxy),
        "free_energy": float(metrics.free_energy),
        "awareness_level": float(metrics.awareness_level),
        "ignition": bool(metrics.ignition),
        "broadcast_strength": float(metrics.broadcast_strength),
        "winner_source": ws.winner_source,
        "arousal": float(metrics.arousal),
    }


# --------------------------------------------------------------------------- #
# Legacy single-agent endpoints (agent 0 of the society façade)
# --------------------------------------------------------------------------- #
@router.get("/state")
async def get_state() -> dict:
    """Return agent 0's state plus the functional disclaimer."""
    state = _society_state_legacy()
    state["disclaimer"] = DISCLAIMER_EN
    state["disclaimer_en"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.post("/tick", response_model=CycleTrace)
async def post_tick() -> CycleTrace:
    """Advance the society one tick and return agent 0's trace."""
    traces = await _manager().async_tick()
    return traces[0]


@router.post("/reset")
async def post_reset(patch: ConfigPatch | None = None) -> dict:
    """Reset the society (optionally applying a config patch); return agent 0 state."""
    mgr = _manager()
    mgr.reset(patch)
    state = _society_state_legacy()
    state["disclaimer"] = DISCLAIMER_EN
    return state


@router.post("/run")
async def post_run(req: RunRequest) -> dict:
    """Start the background tick loop at ``req.tps`` (until paused/max_ticks)."""
    await _manager().run(req)
    return {"running": True}


@router.post("/pause")
async def post_pause() -> dict:
    """Pause the background tick loop."""
    _manager().pause()
    return {"running": False}


@router.get("/agent/self-model", response_model=SelfModelState)
async def get_self_model() -> SelfModelState:
    """Return agent 0's current self-model state."""
    return _agent0().self_model_state()


@router.get("/agent/memory", response_model=list[MemoryRecord])
async def get_memory(limit: int = Query(default=20, ge=1, le=1000)) -> list[MemoryRecord]:
    """Return agent 0's most recent autobiographical memory records."""
    return _agent0().recent_memories(limit)


@router.get("/agent/introspection", response_model=IntrospectionReport)
async def get_introspection() -> IntrospectionReport:
    """Return a freshly generated introspection report for agent 0."""
    return _agent0().introspect()


@router.get("/agent/consciousness")
async def get_consciousness() -> dict:
    """Return agent 0's bound v2 consciousness sub-states (GWT/AST/HOT/IIT proxy)."""
    state = _agent0().consciousness_state()
    state["disclaimer"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.get("/agent/workspace", response_model=WorkspaceState)
async def get_workspace() -> WorkspaceState:
    """Return agent 0's latest global-workspace competition outcome (GWT)."""
    return _agent0().workspace_state()


@router.get("/agent/stream", response_model=list[ConsciousMoment])
async def get_stream(limit: int = Query(default=20, ge=1, le=1000)) -> list[ConsciousMoment]:
    """Return up to ``limit`` of agent 0's most recent ConsciousMoments."""
    return _agent0().stream(limit)


@router.post("/agent/goal", response_model=SelfModelState)
async def post_goal(req: GoalRequest) -> SelfModelState:
    """Register an explicit goal on agent 0 and return the updated self-model."""
    ag = _agent0()
    ag.set_goal(req.goal)
    return ag.self_model_state()


@router.post("/agent/ask", response_model=AskResponse)
async def post_ask(req: AskRequest) -> AskResponse:
    """Introspective-dialogue probe on agent 0 (grounded report from variables)."""
    return _agent0().ask(req.question, req.intent)


@router.post("/agent/narrate")
async def post_narrate() -> dict:
    """(Optional LLM) Render agent 0's REAL internal variables into a grounded
    narration via the configured LLM backend (OpenRouter). The LLM is fed only the
    variables and forbidden to invent or to claim experience; it changes nothing in
    the cognitive loop. Returns 503 when no LLM key is configured.

    HONESTY: a fluent narration is still text generated from internal variables —
    NOT evidence of consciousness or subjective experience.
    """
    from core.llm import get_backend, narrate
    backend = get_backend()
    if not backend.available():
        raise HTTPException(status_code=503,
                            detail="No LLM backend configured. Set OPENROUTER_API_KEY to enable /agent/narrate.")
    try:
        result = narrate(backend, _agent0())
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    result["disclaimer"] = DISCLAIMER_EN
    result["framing"] = THEORY_FRAMING_EN
    return result


@router.post("/world/stimulus")
async def post_world_stimulus(stim: WorldStimulus) -> dict:
    """World stimulus: inject a real object into the shared world near agent 0."""
    obj = _agent0().world_stimulus(stim)
    return {"object": obj.model_dump(), "state": _society_state_legacy()}


@router.post("/agent/inject")
async def post_inject(injection: CognitiveInjection) -> dict:
    """Cognitive injection: force a coalition into agent 0's next workspace round."""
    return _agent0().inject(injection)


@router.post("/agent/attend")
async def post_attend(req: AttendRequest) -> dict:
    """Attention steering: bias agent 0's top-down attention toward a target (AST)."""
    return _agent0().attend(req)


@router.post("/agent/perturb")
async def post_perturb(req: PerturbRequest) -> dict:
    """Perturbation: apply a choc / surprise / apaisement to agent 0."""
    effect = _agent0().perturb(req)
    return {"effect": effect, "state": _society_state_legacy()}


@router.post("/config")
async def post_config(patch: ConfigPatch) -> dict:
    """Apply a partial config patch (rebuilds the society) and return config + state."""
    mgr = _manager()
    mgr.reset(patch)
    state = _society_state_legacy()
    state["disclaimer"] = DISCLAIMER_EN
    return {"config": mgr.config.model_dump(), "state": state}


@router.get("/metrics", response_model=Metrics)
async def get_metrics() -> Metrics:
    """Return agent 0's latest metrics."""
    return _agent0().metrics()


@router.get("/trace")
async def get_trace(limit: int = Query(default=50, ge=1, le=1000)) -> list[dict]:
    """Return agent 0's most recent cognitive traces from the JSONL export."""
    path = Path(_agent0().trace_logger.path())
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return []
    tail = lines[-limit:]
    traces: list[dict] = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            traces.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return traces


# --------------------------------------------------------------------------- #
# Society (multi-agent) endpoints
# --------------------------------------------------------------------------- #
@router.get("/society")
async def get_society() -> dict:
    """Return the whole-society state (per-agent summaries + relations graph)."""
    state = _manager().state()
    state["disclaimer"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.post("/society/tick")
async def post_society_tick() -> dict:
    """Run one collective society tick; return one trace per agent."""
    traces = await _manager().async_tick()
    return {"traces": [t.model_dump() for t in traces]}


@router.post("/society/run")
async def post_society_run(req: RunRequest) -> dict:
    """Start the society background loop at ``req.tps``."""
    await _manager().run(req)
    return {"running": True}


@router.post("/society/pause")
async def post_society_pause() -> dict:
    """Pause the society background loop."""
    _manager().pause()
    return {"running": False}


@router.post("/society/config")
async def post_society_config(patch: ConfigPatch) -> dict:
    """Apply a config patch (e.g. n_agents) and rebuild the society; return state."""
    mgr = _manager()
    mgr.reset(patch)
    state = mgr.state()
    state["disclaimer"] = DISCLAIMER_EN
    return state


@router.get("/society/relations")
async def get_society_relations() -> dict:
    """Return the trust / theory-of-mind relations graph."""
    return _manager().relations()


@router.get("/society/messages")
async def get_society_messages() -> dict:
    """Return the messages currently alive in the shared world."""
    return {"messages": [m.model_dump() for m in _manager().world.messages]}


def _require_agent(agent_id: int):
    """Return the society agent or raise 404 if it does not exist."""
    mgr = _manager()
    if agent_id not in mgr.agents:
        raise HTTPException(status_code=404, detail=f"agent {agent_id} not found")
    return mgr.agent(agent_id)


@router.get("/society/agent/{agent_id}/consciousness")
async def get_society_agent_consciousness(agent_id: int) -> dict:
    """Return one agent's bound consciousness sub-states."""
    state = _require_agent(agent_id).consciousness_state()
    state["disclaimer"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.get("/society/agent/{agent_id}/self-model", response_model=SelfModelState)
async def get_society_agent_self_model(agent_id: int) -> SelfModelState:
    """Return one agent's self-model state."""
    return _require_agent(agent_id).self_model_state()


@router.get("/society/agent/{agent_id}/introspection", response_model=IntrospectionReport)
async def get_society_agent_introspection(agent_id: int) -> IntrospectionReport:
    """Return one agent's introspection report."""
    return _require_agent(agent_id).introspect()


@router.get("/society/agent/{agent_id}/workspace", response_model=WorkspaceState)
async def get_society_agent_workspace(agent_id: int) -> WorkspaceState:
    """Return one agent's latest workspace competition outcome."""
    return _require_agent(agent_id).workspace_state()


# --------------------------------------------------------------------------- #
# Scientific-instrument endpoints (Phase 4)
# --------------------------------------------------------------------------- #
class _BatteryReq(BaseModel):
    seed: int = 42
    ticks: int = 12


class _TrainReq(BaseModel):
    ticks: int = 200


@router.post("/train")
async def post_train(req: _TrainReq) -> dict:
    """Fast headless training: run N ticks back-to-back on the live society at
    maximum speed (no inter-tick sleep), advancing/accumulating its learned state.

    For maximum throughput first disable per-tick disk I/O via
    ``POST /config {"persist_memory": false, "trace_logging": false}``.
    """
    mgr = _manager()
    async with mgr._lock:
        result = mgr.train(req.ticks)
    result["disclaimer"] = DISCLAIMER_EN
    return result


@router.post("/scenario/run", response_model=ScenarioResult)
async def post_scenario_run(scenario: Scenario) -> ScenarioResult:
    """Run a reproducible scripted scenario and return its metrics time series."""
    return ScenarioRunner().run(scenario)


@router.post("/battery/{test_name}", response_model=BatteryResult)
async def post_battery(test_name: str, req: _BatteryReq) -> BatteryResult:
    """Run a functional probe (mirror | false_memory | calibration | relational_self)."""
    battery = ConsciousnessTestBattery()
    if test_name == "mirror":
        return battery.mirror_test(seed=req.seed, ticks=req.ticks)
    if test_name == "false_memory":
        return battery.false_memory_test(seed=req.seed, ticks=req.ticks)
    if test_name == "calibration":
        return battery.calibration_test(seed=req.seed, ticks=req.ticks)
    if test_name == "relational_self":
        # this probe runs isolated-vs-society and needs enough ticks for the
        # agents to come into mutual view.
        return battery.relational_self_test(seed=req.seed, ticks=max(int(req.ticks), 30))
    raise HTTPException(status_code=404, detail=f"unknown test '{test_name}'")


@router.get("/metrics/history")
async def get_metrics_history(limit: int = Query(default=500, ge=1, le=100000)) -> dict:
    """Return the live society's recorded metrics time series."""
    series = _manager().recorder.series(limit)
    return {"series": series.model_dump(), "disclaimer": DISCLAIMER_EN}


@router.get("/export.csv")
async def get_export_csv() -> Response:
    """Download the live society's recorded metrics as CSV."""
    csv_text = _manager().recorder.to_csv()
    return Response(content=csv_text, media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=humanity_metrics.csv"})


@router.get("/export.json")
async def get_export_json() -> Response:
    """Download the live society's recorded metrics as JSON."""
    return Response(content=_manager().recorder.to_json(), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=humanity_metrics.json"})


@router.websocket("/ws/society")
async def ws_society(ws: WebSocket) -> None:
    """Push the society state roughly every 250ms until the client disconnects."""
    await ws.accept()
    mgr = _manager()
    try:
        while True:
            async with mgr._lock:
                payload = mgr.state()
            await ws.send_json(payload)
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return
