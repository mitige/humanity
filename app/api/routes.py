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

from fastapi import APIRouter, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.agent import get_manager
from core.gender_scenarios import (
    get_gender_scenario,
    list_gender_scenarios,
)
from core.society import ConfigRequiresReset, SocietyManager
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
    GenderBatteryRequest,
    GenderBatteryResult,
    GENDER_EXPERIENCE_DISCLAIMER,
    GenderEventRequest,
    GenderExperienceState,
    GenderIntentRequest,
    GenderScenarioSelection,
    GenderSocietyState,
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
    manager = get_manager()
    if manager._exclusive_worker:
        raise HTTPException(
            status_code=503,
            detail="Live society is busy; retry after the atomic job completes.",
            headers={"Retry-After": "1"},
        )
    return manager


def _agent0():
    """Legacy single-agent accessor: agent 0 of the society façade."""
    return _manager().agent(0)


async def _run_live_agent_job(operation, *, require_trace: bool = True):
    """Run one exclusive reporting/LLM job off-loop on coherent live state."""
    mgr = _manager()
    async with mgr._lock:
        mgr._exclusive_worker = True
        try:
            def invoke():
                agent = mgr.agent(0)
                if require_trace and agent.last_trace is None:
                    mgr.tick()
                return operation(agent)

            return await _run_cpu_bound(invoke)
        finally:
            mgr._exclusive_worker = False


def _legacy_world_snapshot() -> dict:
    """Solo-shaped world snapshot (singular ``agent``) for agent 0 of the society."""
    w = _manager().world
    shared = w.snapshot()
    a0 = next(agent for agent in shared["agents"] if agent["id"] == 0)
    snapshot = {
        "grid_size": int(w.config.grid_size),
        "tick": int(w.tick),
        "agent": {
            "x": int(a0["x"]),
            "y": int(a0["y"]),
            "energy": round(float(a0["energy"]), 4),
        },
        "objects": shared["objects"],
    }
    for optional in ("season", "task"):
        if optional in shared:
            snapshot[optional] = shared[optional]
    return snapshot


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
        "working_memory": [item.model_dump()
                           for item in ag.working_memory.contents()],
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
    try:
        mgr.reset(patch)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state = _society_state_legacy()
    state["mode"] = "reset"
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


# --------------------------------------------------------------------------- #
# Phase 8 — situated gendered self
# --------------------------------------------------------------------------- #
def _gender_payload(agent) -> dict:
    state = agent.gender_state()
    return {
        "enabled": bool(agent.config.gender_experience_enabled),
        "configured": agent.gender_experience._profile is not None,
        "state": state.model_dump(mode="json") if state is not None else None,
        "disclaimer": GENDER_EXPERIENCE_DISCLAIMER,
    }


def _require_gender_configured(agent):
    if agent.gender_experience._profile is None:
        raise HTTPException(
            status_code=409,
            detail={
                "accepted": False,
                "reason": "No gender-life scenario profile is installed for this agent.",
            },
        )
    return agent


@router.get("/gender/scenarios")
async def get_gender_scenarios(
    seed: int = Query(default=42, ge=0, le=2**32 - 1),
) -> dict:
    """List complete, reproducible example manifests (never hidden defaults)."""
    return {
        "scenarios": list_gender_scenarios(seed=seed),
        "note": (
            "Presets are examples, not archetypes. Applying one performs a full reset."
        ),
        "disclaimer": GENDER_EXPERIENCE_DISCLAIMER,
    }


@router.post("/gender/scenario")
async def post_gender_scenario(selection: GenderScenarioSelection) -> dict:
    """Apply one preset/custom scenario through a full transactional reset."""
    try:
        manifest = (
            selection.scenario.model_copy(deep=True)
            if selection.scenario is not None
            else get_gender_scenario(
                str(selection.preset_id), seed=selection.seed
            )
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    mgr = _manager()
    async with mgr._lock:
        mgr._exclusive_worker = True
        try:
            mgr.install_gender_scenario(manifest)
            traces = mgr.tick() if manifest.enable else []
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            mgr._exclusive_worker = False
    return {
        "mode": "full_reset",
        "reset": True,
        "scenario_id": manifest.scenario_id,
        "preset_id": manifest.preset_id,
        "initialized_tick": int(mgr.world.tick),
        "agents": {
            agent_id: _gender_payload(mgr.agents[agent_id])
            for agent_id in sorted(mgr.agents)
        },
        "public_society": mgr.gender_society_state().model_dump(mode="json"),
        "trace_count": len(traces),
        "disclaimer": GENDER_EXPERIENCE_DISCLAIMER,
    }


@router.get("/agent/gender")
async def get_agent_gender() -> dict:
    """Return agent-readable Phase-8 state; never the private profile."""
    return _gender_payload(_agent0())


@router.get("/agent/gender/debug")
async def get_agent_gender_debug() -> dict:
    """Explicit private experiment/debug view."""
    agent = _require_gender_configured(_agent0())
    if agent.gender_state() is None:
        raise HTTPException(
            status_code=409,
            detail="The installed scenario has not produced a gender state yet.",
        )
    return agent.gender_debug_state().model_dump(mode="json")


@router.post("/agent/gender/event")
async def post_agent_gender_event(request: GenderEventRequest) -> dict:
    """Queue a validated, template-safe event for agent 0's next tick."""
    if request.target_id != 0:
        raise HTTPException(
            status_code=422,
            detail="Use /society/agent/{agent_id}/gender/event for another target.",
        )
    mgr = _manager()
    async with mgr._lock:
        event = _require_gender_configured(
            mgr.agent(0)
        ).queue_gender_event(request)
    return {
        "accepted": True,
        "scheduled_tick": event.tick,
        "event": event.model_dump(mode="json"),
    }


@router.post("/agent/gender/intent")
async def post_agent_gender_intent(request: GenderIntentRequest) -> dict:
    """Queue one explicit user-probe intent for the next tick."""
    mgr = _manager()
    async with mgr._lock:
        intent = _require_gender_configured(
            mgr.agent(0)
        ).queue_gender_intent(request)
    return {
        "accepted": True,
        "scheduled_tick": intent.tick,
        "intent": intent.model_dump(mode="json"),
    }


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
    return await _run_live_agent_job(
        lambda agent: agent.ask(req.question, req.intent))


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
        result = await _run_live_agent_job(
            lambda agent: narrate(backend, agent))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    result["disclaimer"] = DISCLAIMER_EN
    result["framing"] = THEORY_FRAMING_EN
    return result


@router.post("/agent/audit")
async def post_grounding_audit() -> dict:
    """(Optional LLM) FUNCTIONAL probe — NOT a consciousness test. The LLM acts as a
    skeptical auditor and scores whether agent 0's introspective answers are GROUNDED
    in its real internal variables (reportability fidelity). A high score means
    faithful, non-confabulated reporting — never evidence of consciousness. 503 if no
    LLM key is configured."""
    from core.llm import get_backend, grounding_audit
    backend = get_backend()
    if not backend.available():
        raise HTTPException(status_code=503,
                            detail="No LLM backend configured. Set OPENROUTER_API_KEY to enable /agent/audit.")
    try:
        return await _run_live_agent_job(
            lambda agent: grounding_audit(backend, agent))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/agent/report-card")
async def post_report_card() -> dict:
    """(Optional LLM) An honest plain-language summary of the FUNCTIONAL test
    batteries, with the disclaimers foregrounded. Measures nothing new; it does not
    assess consciousness. 503 if no LLM key is configured."""
    from core.llm import get_backend, report_card
    backend = get_backend()
    if not backend.available():
        raise HTTPException(status_code=503,
                            detail="No LLM backend configured. Set OPENROUTER_API_KEY to enable /agent/report-card.")
    try:
        return await _run_cpu_bound(report_card, backend)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


class _ConverseTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1, max_length=4000)


class _ConverseReq(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2000)
    history: list[_ConverseTurn] = Field(default_factory=list, max_length=6)


def _llm_backend_or_503(feature: str):
    """Shared guard for the optional language-organ endpoints."""
    from core.llm import get_backend
    backend = get_backend()
    if not backend.available():
        raise HTTPException(status_code=503,
                            detail=f"No LLM backend configured. Set OPENROUTER_API_KEY to enable {feature}.")
    return backend


@router.post("/agent/converse")
async def post_converse(req: _ConverseReq) -> dict:
    """(Optional LLM) Grounded interview: the LLM answers AS agent 0, constrained
    to its live variables, real memories and its own template answer. Reportability
    (GWT/HOT) rendered fluently — first person is a convention, never a witness, and
    no answer is evidence of consciousness. 503 if no LLM key is configured."""
    from core.llm import converse
    backend = _llm_backend_or_503("/agent/converse")
    try:
        return await _run_live_agent_job(
            lambda agent: converse(
                backend, agent, req.question,
                [turn.model_dump() for turn in req.history]))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/agent/biography")
async def post_biography() -> dict:
    """(Optional LLM) The agent's life story, written strictly from its REAL
    episodic memory records and measured trait trajectory (the narrative self,
    honestly read). A reconstructed story is not a lived one; not evidence of
    consciousness. 503 if no LLM key is configured."""
    from core.llm import biography
    backend = _llm_backend_or_503("/agent/biography")
    try:
        return await _run_live_agent_job(
            lambda agent: biography(backend, agent))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/agent/cross-examine")
async def post_cross_examine() -> dict:
    """(Optional LLM) The philosopher's cross-examination: the STRONGEST honest case
    that the system instantiates the functional properties the theories describe,
    the strongest rebuttal, and the reason the question is undecidable in principle.
    It never concludes the agent is conscious — nothing can establish that. 503 if
    no LLM key is configured."""
    from core.llm import cross_examine
    backend = _llm_backend_or_503("/agent/cross-examine")
    try:
        return await _run_live_agent_job(
            lambda agent: cross_examine(backend, agent))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/agent/inner-voice")
async def post_inner_voice() -> dict:
    """(Optional LLM) Generate one condensed inner-speech line from agent 0's real
    moment and queue it as the next ``inner_speech`` coalition: the LLM's words must
    WIN the ignition competition to become the agent's conscious content — re-entry
    through the real mechanism, not narration from outside. Requires the
    inner_speech mechanism to be enabled to actually compete. 503 if no LLM key."""
    from core.llm import inner_voice
    backend = _llm_backend_or_503("/agent/inner-voice")
    try:
        return await _run_live_agent_job(
            lambda agent: inner_voice(backend, agent))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


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


@router.get("/config")
async def get_config() -> dict:
    """Return the live SimConfig (lets the UI diff before posting a patch)."""
    return {"config": _manager().config.model_dump()}


@router.post("/config")
async def post_config(patch: ConfigPatch) -> dict:
    """Hot-apply a validated, non-structural patch without rebuilding society."""
    mgr = _manager()
    try:
        changed_fields = await mgr.apply_config(patch)
    except ConfigRequiresReset as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "fields": exc.fields,
                "instruction": "Use POST /reset for structural changes.",
            },
        ) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state = _society_state_legacy()
    state["disclaimer"] = DISCLAIMER_EN
    return {
        "mode": "hot",
        "changed_fields": changed_fields,
        "config": mgr.config.model_dump(),
        "state": state,
        "disclaimer": DISCLAIMER_EN,
    }


@router.get("/metrics", response_model=Metrics)
async def get_metrics() -> Metrics:
    """Return agent 0's latest metrics."""
    return _agent0().metrics()


@router.get("/trace")
async def get_trace(limit: int = Query(default=50, ge=1, le=1000)) -> list[dict]:
    """Return agent 0's most recent cognitive traces from the JSONL export."""
    from storage.trace_export import tail_traces

    path = _agent0().trace_logger.path()
    return await _run_cpu_bound(tail_traces, path, limit=limit)


# --------------------------------------------------------------------------- #
# Phase 7 — semantic memory search / graph + richer trace export
# --------------------------------------------------------------------------- #
@router.get("/agent/memory/search")
async def get_memory_search(q: str = Query(min_length=1, max_length=200),
                            limit: int = Query(default=8, ge=1, le=50)) -> dict:
    """Free-text semantic search over agent 0's autobiographical memory.

    Deterministic hashed-n-gram embeddings + cosine ranking (Phase 7). Works
    whatever the vector_memory flag says — the index is synced on demand.
    Distributional similarity of records, NOT remembering as an experience.
    """
    def search(agent):
        records = agent.memory._records
        agent.vector_index.sync(records)
        hits = agent.vector_index.search_text(records, q, limit)
        return {
            "query": q,
            "results": [
                {"similarity": round(float(score), 4), **record.model_dump()}
                for record, score in hits
            ],
            "disclaimer": DISCLAIMER_EN,
        }

    return await _run_live_agent_job(search, require_trace=False)


@router.get("/agent/memory/graph")
async def get_memory_graph(limit: int = Query(default=60, ge=2, le=200),
                           edges: int = Query(default=3, ge=1, le=8)) -> dict:
    """Similarity graph over agent 0's recent autobiographical memory (Phase 7).

    Nodes are episodes; edges link each episode to its nearest neighbours by
    embedding cosine. A visualization of stored variables — not a mind map.
    """
    def graph(agent):
        records = agent.memory._records
        agent.vector_index.sync(records)
        payload = agent.vector_index.graph(
            records, limit=limit, top_edges=edges)
        payload["disclaimer"] = DISCLAIMER_EN
        return payload

    return await _run_live_agent_job(graph, require_trace=False)


@router.get("/export/traces")
async def get_export_traces(
    from_tick: int | None = Query(default=None, ge=0),
    to_tick: int | None = Query(default=None, ge=0),
    ignited_only: bool = Query(default=False),
    fields: str | None = Query(default=None, description="comma-separated top-level fields"),
    format_: str | None = Query(
        default=None, alias="format", pattern="^(jsonl|json|csv)$",
        description="Canonical output format.",
    ),
    fmt: str | None = Query(
        default=None, pattern="^(jsonl|json|csv)$", deprecated=True,
        description="Legacy alias for format.",
    ),
    limit: int = Query(default=1000, ge=1, le=20000),
) -> Response:
    """Filtered, projected, multi-format export of the JSONL cognitive traces (Phase 7)."""
    from storage.trace_export import format_rows, iter_traces
    path = _agent0().trace_logger.path()
    field_list = [f.strip() for f in fields.split(",") if f.strip()] if fields else None

    def build_export() -> tuple[str, str]:
        rows = list(iter_traces(
            path,
            from_tick=from_tick,
            to_tick=to_tick,
            ignited_only=ignited_only,
            fields=field_list,
            limit=limit,
        ))
        return format_rows(rows, format_ or fmt or "jsonl")

    payload, media_type = await _run_cpu_bound(build_export)
    return Response(content=payload, media_type=media_type)


@router.get("/export/analysis")
async def get_export_analysis(window: int = Query(default=50, ge=1, le=1000)) -> dict:
    """Aggregate analysis of the full trace file: ignition rate, Φ statistics,
    windowed error curve, action histogram, sleep fraction (Phase 7)."""
    from storage.trace_export import analysis
    path = _agent0().trace_logger.path()
    return await _run_cpu_bound(analysis, path, window=window)


@router.get("/export/gender-scenario")
async def get_export_gender_scenario(
    include_private: bool = Query(
        default=False,
        description="Explicit opt-in to configured private experiment inputs.",
    ),
) -> dict:
    """Export public projections by default; private profiles only by opt-in."""
    from storage.trace_export import gender_scenario_export
    try:
        return gender_scenario_export(
            _manager(), include_private=include_private
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail={"accepted": False, "reason": str(exc)},
        ) from exc


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
    """Apply a config patch (e.g. n_agents) and rebuild the society; return state.

    Like ``POST /config``, resumes the background loop if it was running.
    """
    mgr = _manager()
    was_running = bool(mgr.running)
    resume = mgr.last_run_request
    try:
        mgr.reset(patch)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if was_running:
        await mgr.run(resume or RunRequest())
    state = mgr.state()
    state["mode"] = "reset"
    state["disclaimer"] = DISCLAIMER_EN
    return state


@router.get("/society/relations")
async def get_society_relations() -> dict:
    """Return the trust / theory-of-mind relations graph."""
    return _manager().relations()


@router.get("/society/language")
async def get_society_language() -> dict:
    """(Phase 6) The society's emergent dictionary: each meaning's invented word
    variants, the majority convention, and the lexical convergence — the
    naming-game measure of a language being born. Emergent conventions over
    strength tables; NOT understanding, and not evidence of consciousness."""
    payload = _manager().language_summary()
    payload["disclaimer"] = DISCLAIMER_EN
    return payload


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


@router.get("/society/gender", response_model=GenderSocietyState)
async def get_society_gender() -> GenderSocietyState:
    """Return public projections and observer-local recognition only."""
    return _manager().gender_society_state()


@router.get("/society/agent/{agent_id}/gender")
async def get_society_agent_gender(agent_id: int) -> dict:
    return _gender_payload(_require_agent(agent_id))


@router.get("/society/agent/{agent_id}/gender/debug")
async def get_society_agent_gender_debug(agent_id: int) -> dict:
    agent = _require_gender_configured(_require_agent(agent_id))
    if agent.gender_state() is None:
        raise HTTPException(
            status_code=409,
            detail="The installed scenario has not produced a gender state yet.",
        )
    return agent.gender_debug_state().model_dump(mode="json")


@router.post("/society/agent/{agent_id}/gender/event")
async def post_society_agent_gender_event(
    agent_id: int,
    request: GenderEventRequest,
) -> dict:
    if request.target_id != agent_id:
        raise HTTPException(
            status_code=422,
            detail="Body target_id must match the path agent_id.",
        )
    mgr = _manager()
    async with mgr._lock:
        event = _require_gender_configured(
            _require_agent(agent_id)
        ).queue_gender_event(request)
    return {
        "accepted": True,
        "scheduled_tick": event.tick,
        "event": event.model_dump(mode="json"),
    }


@router.post("/society/agent/{agent_id}/gender/intent")
async def post_society_agent_gender_intent(
    agent_id: int,
    request: GenderIntentRequest,
) -> dict:
    mgr = _manager()
    async with mgr._lock:
        intent = _require_gender_configured(
            _require_agent(agent_id)
        ).queue_gender_intent(request)
    return {
        "accepted": True,
        "scheduled_tick": intent.tick,
        "intent": intent.model_dump(mode="json"),
    }


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
    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    ticks: int = Field(default=12, ge=1, le=100_000)


class _TrainReq(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticks: int = Field(default=200, ge=0, le=100_000)


async def _run_cpu_bound(func, /, *args, **kwargs):
    """Run sync CPU work off-loop and wait it out before propagating cancel."""
    worker = asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancelled:
        try:
            await worker
        except Exception:
            pass
        raise cancelled


@router.post("/train")
async def post_train(req: _TrainReq) -> dict:
    """Fast headless training: run N ticks back-to-back on the live society at
    maximum speed (no inter-tick sleep), advancing/accumulating its learned state.

    For maximum throughput first disable per-tick disk I/O via
    ``POST /config {"persist_memory": false, "trace_logging": false}``.
    """
    mgr = _manager()
    async with mgr._lock:
        mgr._exclusive_worker = True
        try:
            result = await _run_cpu_bound(mgr.train, req.ticks)
        finally:
            mgr._exclusive_worker = False
    result["disclaimer"] = DISCLAIMER_EN
    return result


class _CheckpointReq(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(default="run", min_length=1, max_length=100)


@router.post("/checkpoint/save")
async def post_checkpoint_save(req: _CheckpointReq) -> dict:
    """Save the full live society (world, agents, learned state, memory, RNG) to a
    named checkpoint, so the run can be resumed later."""
    from core import checkpoint
    mgr = _manager()
    async with mgr._lock:
        mgr._exclusive_worker = True
        try:
            return await _run_cpu_bound(checkpoint.save, mgr, req.name)
        finally:
            mgr._exclusive_worker = False


@router.get("/checkpoint/list")
async def get_checkpoint_list() -> dict:
    """List the saved checkpoints (name, tick, agent count, timestamp)."""
    from core import checkpoint
    return {"checkpoints": await _run_cpu_bound(checkpoint.listing)}


@router.post("/checkpoint/load")
async def post_checkpoint_load(req: _CheckpointReq) -> dict:
    """Resume a run: restore the live society from a saved checkpoint in place."""
    from core import checkpoint
    mgr = _manager()
    try:
        async with mgr._lock:
            mgr._exclusive_worker = True
            try:
                info = await _run_cpu_bound(
                    checkpoint.load, mgr, req.name)
            finally:
                mgr._exclusive_worker = False
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except checkpoint.InvalidCheckpointError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return info


@router.post("/checkpoint/delete")
async def post_checkpoint_delete(req: _CheckpointReq) -> dict:
    """Delete a saved checkpoint."""
    from core import checkpoint
    if not await _run_cpu_bound(checkpoint.delete, req.name):
        raise HTTPException(status_code=404, detail=f"checkpoint '{req.name}' not found")
    return {"deleted": checkpoint._safe(req.name)}


@router.post("/scenario/run", response_model=ScenarioResult)
async def post_scenario_run(scenario: Scenario) -> ScenarioResult:
    """Run a reproducible scripted scenario and return its metrics time series."""
    return await _run_cpu_bound(ScenarioRunner().run, scenario)


@router.post(
    "/battery/gender-experience",
    response_model=GenderBatteryResult,
)
async def post_gender_experience_battery(
    request: GenderBatteryRequest,
) -> GenderBatteryResult:
    """Run matched Phase-8 counterfactuals without touching the live society."""
    battery = ConsciousnessTestBattery()
    try:
        return await _run_cpu_bound(
            battery.gender_experience_test,
            seed=request.seed,
            ticks=request.ticks,
            preset_id=request.preset_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/battery/{test_name}", response_model=BatteryResult)
async def post_battery(test_name: str, req: _BatteryReq) -> BatteryResult:
    """Run a functional probe (mirror | false_memory | calibration | relational_self
    | masking | blink | priming | reality_monitor)."""
    battery = ConsciousnessTestBattery()
    if test_name == "mirror":
        return await _run_cpu_bound(
            battery.mirror_test, seed=req.seed, ticks=req.ticks)
    if test_name == "false_memory":
        return await _run_cpu_bound(
            battery.false_memory_test, seed=req.seed, ticks=req.ticks)
    if test_name == "calibration":
        return await _run_cpu_bound(
            battery.calibration_test, seed=req.seed, ticks=req.ticks)
    if test_name == "relational_self":
        # this probe runs isolated-vs-society and needs enough ticks for the
        # agents to come into mutual view.
        return await _run_cpu_bound(
            battery.relational_self_test,
            seed=req.seed,
            ticks=max(int(req.ticks), 30),
        )
    # Phase 5 — psychophysics signatures of conscious ACCESS (functional). The
    # ``ticks`` body field is the pre-stimulus warmup; it is clamped so the
    # probes stay in the stimulus regime they were calibrated for.
    if test_name == "masking":
        return await _run_cpu_bound(
            battery.masking_test, seed=req.seed,
            ticks=min(int(req.ticks), 4))
    if test_name == "blink":
        return await _run_cpu_bound(
            battery.blink_test, seed=req.seed,
            ticks=min(int(req.ticks), 4))
    if test_name == "priming":
        return await _run_cpu_bound(
            battery.priming_test, seed=req.seed,
            ticks=min(int(req.ticks), 4))
    if test_name == "reality_monitor":
        return await _run_cpu_bound(
            battery.reality_monitor_test, seed=req.seed,
            ticks=max(int(req.ticks), 30))
    # Phase 6 — does a shared lexicon emerge under the invent-a-language drive?
    if test_name == "language_genesis":
        return await _run_cpu_bound(
            battery.language_genesis_test, seed=req.seed,
            ticks=max(int(req.ticks), 80))
    raise HTTPException(status_code=404, detail=f"unknown test '{test_name}'")


@router.get("/agent/coverage")
async def get_coverage() -> dict:
    """The asymptote panel: which theory-proposed mechanisms are implemented and
    active. A coverage CHECKLIST over level-2 mechanisms — explicitly NOT a
    consciousness score and NOT a distance to level 1 (nothing measures that)."""
    from core.coverage import coverage
    payload = coverage(_manager().config)
    payload["framing"] = THEORY_FRAMING_EN
    return payload


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
    # A socket accepted during /train waits on the society lock instead of
    # invoking the HTTP fail-fast gate.
    mgr = get_manager()
    try:
        while True:
            async with mgr._lock:
                payload = mgr.state()
            await ws.send_json(payload)
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return
