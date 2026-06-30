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
        self.world.advance_tick()
        return traces

    async def async_tick(self) -> list[CycleTrace]:
        async with self._lock:
            return self.tick()

    async def run(self, req: RunRequest) -> None:
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
            self.running = False

    def pause(self) -> None:
        self.running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

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
