# core/society.py
"""Society orchestration: owns the SharedWorld and N CognitiveAgents.

FUNCTIONAL NOTE: ticks every agent once per society tick in deterministic id
order against a shared world, collecting one CycleTrace per agent. A society of 1
reproduces the single-agent instrument. Nothing here is conscious.
"""
from __future__ import annotations

import asyncio

from core.agent import CognitiveAgent
from core.metrics_recorder import MetricsRecorder
from core.shared_world import SharedWorld
from schemas.models import ConfigPatch, CycleTrace, RunRequest, SimConfig


class SocietyManager:
    """Owns one SharedWorld and N agents; runs deterministic round-robin ticks."""

    def __init__(self, config: SimConfig | None = None) -> None:
        self.config = config or SimConfig()
        self._build()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.running: bool = False
        # Last run request, so a config patch applied mid-run can resume the
        # loop at the same pace instead of silently pausing the instrument.
        self.last_run_request: RunRequest | None = None

    def _build(self) -> None:
        self.world = SharedWorld(self.config)
        self.agents: dict[int, CognitiveAgent] = {
            i: CognitiveAgent(self.config, agent_id=i, shared_world=self.world)
            for i in self.world.agents
        }
        self.recorder = MetricsRecorder(int(self.config.metrics_history_max))

    # ------------------------------------------------------------- ticking
    def tick(self) -> list[CycleTrace]:
        """Run one society tick: each agent cycles once, in ascending id order."""
        traces: list[CycleTrace] = []
        for aid in sorted(self.agents):
            trace = self.agents[aid].cognitive_cycle()
            self.recorder.record(aid, trace.metrics)
            traces.append(trace)
        # Relational self: from this tick's theory-of-mind state, compute how each
        # agent is regarded by the others and hand it back for the NEXT tick
        # (one-tick deferred => order-independent => deterministic).
        if self.config.social_mirror_enabled:
            self._update_reflected_appraisals()
        self.world.advance_tick()
        return traces

    def _models_of(self, aid: int) -> list:
        """The OtherMind records the *other* agents currently hold about ``aid``."""
        out = []
        for bid, ag in self.agents.items():
            if bid == aid:
                continue
            for m in ag.theory_of_mind.all_models():
                if m.agent_id == aid:
                    out.append(m)
        return out

    def _update_reflected_appraisals(self) -> None:
        """Set each agent's ``incoming_appraisal`` from how the others regard it."""
        from core.social_self import reflected_appraisal
        now = int(self.world.tick)
        n_others = max(0, len(self.agents) - 1)
        for aid in self.agents:
            self.agents[aid].incoming_appraisal = reflected_appraisal(
                self._models_of(aid), n_others, now_tick=now)

    async def async_tick(self) -> list[CycleTrace]:
        async with self._lock:
            return self.tick()

    def train(self, ticks: int) -> dict:
        """Run ``ticks`` society ticks back-to-back as fast as possible (no
        inter-tick sleep) — a fast headless training primitive that advances and
        accumulates the live society's learned state. Pair with
        ``persist_memory=False`` + ``trace_logging=False`` for maximum throughput.
        """
        n = max(0, int(ticks))
        for _ in range(n):
            self.tick()
        return {"ticks_run": n, "tick": int(self.world.tick), "n_agents": len(self.agents)}

    async def run(self, req: RunRequest) -> None:
        self.last_run_request = req
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop(req))

    async def _run_loop(self, req: RunRequest) -> None:
        tps = req.tps if req.tps and req.tps > 0 else 1.0
        delay = 1.0 / tps
        done = 0
        try:
            while self.running:
                async with self._lock:
                    self.tick()
                done += 1
                if req.max_ticks is not None and done >= req.max_ticks:
                    break
                await asyncio.sleep(delay)
        finally:
            # Only the CURRENT loop owns the running flag: a cancelled, already
            # replaced loop (e.g. a config patch that resumed a fresh run) must
            # not clobber its successor's state when its cancellation lands.
            if self._task is asyncio.current_task():
                self.running = False

    def pause(self) -> None:
        self.running = False
        if self._task is not None:
            # Detach BEFORE cancelling so the dying loop's finally-guard sees it
            # is no longer the current task and leaves the flag alone.
            task, self._task = self._task, None
            task.cancel()

    # ------------------------------------------------------------- lifecycle
    def reset(self, patch: dict | ConfigPatch | None = None) -> None:
        self.pause()
        if patch is not None:
            updates = (patch.model_dump(exclude_none=True)
                       if isinstance(patch, ConfigPatch)
                       else {k: v for k, v in dict(patch).items() if v is not None})
            self.config = self.config.model_copy(update=updates)
        self._build()

    # ------------------------------------------------------------- accessors
    def agent(self, agent_id: int) -> CognitiveAgent:
        return self.agents[int(agent_id)]

    def language_summary(self) -> dict:
        """The society's emergent dictionary + lexical convergence (Phase 6)."""
        from core.language import society_language_summary
        return society_language_summary({aid: ag.lexicon for aid, ag in self.agents.items()})

    def relations(self) -> dict:
        """Trust/ToM graph: nodes = agents, edges = (observer -> other, trust)."""
        edges = []
        for aid, ag in self.agents.items():
            for m in ag.theory_of_mind.all_models():
                if m.agent_id == aid:
                    continue
                edges.append({"from": aid, "to": m.agent_id,
                              "trust": round(float(m.trust), 4),
                              "familiarity": round(float(m.familiarity), 4),
                              "affect": m.inferred_affect})
        return {"nodes": sorted(self.agents), "edges": edges}

    def state(self) -> dict:
        """JSON-serialisable society summary."""
        per_agent = {}
        for aid, ag in self.agents.items():
            m = ag.metrics()
            per_agent[aid] = {
                "metrics": m.model_dump(),
                "self_model": ag.self_model_state().model_dump(),
                "social": ag._last_social.model_dump() if ag._last_social else None,
            }
        return {
            "world": self.world.snapshot(),
            "running": bool(self.running),
            "n_agents": len(self.agents),
            "agents": per_agent,
            "relations": self.relations(),
        }
