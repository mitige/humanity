"""HTTP API for Humanity.

FUNCTIONAL NOTE
---------------
These endpoints expose the simulation's internal variables (world state,
metrics, self-model, episodic memory, introspection text, cognitive traces).
All responses describe a FUNCTIONAL simulation; the agent is not conscious,
sentient, or alive. ``GET /state`` and other relevant responses carry the
canonical disclaimer.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Query

from core.agent import SimulationManager, get_manager
from core.constants import THEORY_FRAMING_EN, THEORY_FRAMING_FR
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

# Canonical disclaimers (verbatim per the project contract).
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


def _manager() -> SimulationManager:
    """Lazily obtain the process-wide simulation manager."""
    return get_manager()


@router.get("/state")
async def get_state() -> dict:
    """Return the current simulation state plus the functional disclaimer."""
    state = _manager().state()
    state["disclaimer"] = DISCLAIMER_EN
    state["disclaimer_en"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.post("/tick", response_model=CycleTrace)
async def post_tick() -> CycleTrace:
    """Advance the simulation by one cognitive cycle and return the trace."""
    return await _manager().async_tick()


@router.post("/reset")
async def post_reset(patch: ConfigPatch | None = None) -> dict:
    """Reset the simulation (optionally applying a config patch); return state."""
    mgr = _manager()
    mgr.reset(patch)
    state = mgr.state()
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
    """Return the agent's current self-model state."""
    return _manager().agent.self_model_state()


@router.get("/agent/memory", response_model=list[MemoryRecord])
async def get_memory(limit: int = Query(default=20, ge=1, le=1000)) -> list[MemoryRecord]:
    """Return the most recent autobiographical memory records."""
    return _manager().agent.recent_memories(limit)


@router.get("/agent/introspection", response_model=IntrospectionReport)
async def get_introspection() -> IntrospectionReport:
    """Return a freshly generated introspection report (text from variables)."""
    return _manager().agent.introspect()


@router.get("/agent/consciousness")
async def get_consciousness() -> dict:
    """Return the bound v2 consciousness sub-states (GWT/AST/HOT/IIT proxy).

    Carries the functional disclaimer and the good-faith theory framing.
    """
    state = _manager().agent.consciousness_state()
    state["disclaimer"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.get("/agent/workspace", response_model=WorkspaceState)
async def get_workspace() -> WorkspaceState:
    """Return the latest global-workspace competition outcome (GWT)."""
    return _manager().agent.workspace_state()


@router.get("/agent/stream", response_model=list[ConsciousMoment])
async def get_stream(limit: int = Query(default=20, ge=1, le=1000)) -> list[ConsciousMoment]:
    """Return up to ``limit`` most recent ConsciousMoments (stream of consciousness)."""
    return _manager().agent.stream(limit)


@router.post("/agent/goal", response_model=SelfModelState)
async def post_goal(req: GoalRequest) -> SelfModelState:
    """Register an explicit goal and return the updated self-model."""
    mgr = _manager()
    mgr.agent.set_goal(req.goal)
    return mgr.agent.self_model_state()


@router.post("/agent/ask", response_model=AskResponse)
async def post_ask(req: AskRequest) -> AskResponse:
    """Introspective-dialogue probe: a grounded report from internal variables.

    Reads the live workspace / attention-schema / metacognition / decision /
    prediction / emotion / self-model state to answer; the text is explicitly
    framed as generated from internal variables (GWT/HOT reportability).
    """
    return await _manager().ask(req.question, req.intent)


@router.post("/world/stimulus")
async def post_world_stimulus(stim: WorldStimulus) -> dict:
    """World stimulus: inject a real object into the world (bottom-up capture)."""
    mgr = _manager()
    obj = await mgr.world_stimulus(stim)
    return {"object": obj.model_dump(), "state": mgr.state()}


@router.post("/agent/inject")
async def post_inject(injection: CognitiveInjection) -> dict:
    """Cognitive injection: force a coalition into the next workspace round."""
    return await _manager().inject(injection)


@router.post("/agent/attend")
async def post_attend(req: AttendRequest) -> dict:
    """Attention steering: bias top-down attention toward a target (AST)."""
    return await _manager().attend(req)


@router.post("/agent/perturb")
async def post_perturb(req: PerturbRequest) -> dict:
    """Perturbation: apply a choc / surprise / apaisement to internal state."""
    mgr = _manager()
    effect = await mgr.perturb(req)
    return {"effect": effect, "state": mgr.state()}


@router.post("/config")
async def post_config(patch: ConfigPatch) -> dict:
    """Apply a partial config patch and return the applied config plus state."""
    mgr = _manager()
    config = mgr.agent.apply_config(patch)
    mgr.config = config
    state = mgr.state()
    state["disclaimer"] = DISCLAIMER_EN
    return {"config": config.model_dump(), "state": state}


@router.get("/metrics", response_model=Metrics)
async def get_metrics() -> Metrics:
    """Return the latest metrics for the simulation."""
    return _manager().agent.metrics()


@router.get("/trace")
async def get_trace(limit: int = Query(default=50, ge=1, le=1000)) -> list[dict]:
    """Return the most recent cognitive traces from the JSONL export."""
    path = Path(_manager().agent.trace_logger.path())
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
