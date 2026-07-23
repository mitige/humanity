# core/society.py
"""Society orchestration: owns the SharedWorld and N CognitiveAgents.

FUNCTIONAL NOTE: ticks every agent once per society tick in deterministic id
order against a shared world, collecting one CycleTrace per agent. A society of 1
reproduces the single-agent instrument. Nothing here is conscious.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy

from core.agent import CognitiveAgent
from core.gender_society import GenderSociety
from core.individuation import compute_individuation
from core.metrics_recorder import MetricsRecorder
from core.shared_world import SharedWorld
from core.world_tasks import TaskManager
from schemas.models import (
    ConfigPatch,
    CycleTrace,
    GenderScenario,
    GenderSocietyState,
    RunRequest,
    SimConfig,
)
from storage.persistence import MemoryStore, atomic_save_batch


RESET_REQUIRED_FIELDS = frozenset({
    "grid_size",
    "n_objects",
    "random_seed",
    "n_agents",
    "stream_length",
    "metrics_history_max",
    "phi_ar_window",
    "phi_causal_window",
    "n_concepts",
})


async def _run_cancellation_safe_worker(operation, *args):
    """Finish a started thread job before allowing task cancellation to escape.

    ``asyncio.to_thread`` itself cannot stop its worker. Shielding and draining
    it keeps the society lock/busy gate held until the worker has either
    completed or failed, so cancellation can never expose a half-migrated state.
    Returns ``(result, cancellation_was_requested)``.
    """
    worker = asyncio.create_task(asyncio.to_thread(operation, *args))
    cancelled = False
    while not worker.done():
        try:
            return await asyncio.shield(worker), cancelled
        except asyncio.CancelledError:
            cancelled = True
    return worker.result(), cancelled


class ConfigRequiresReset(ValueError):
    """Raised when a live patch changes fields that define object structure."""

    def __init__(self, fields) -> None:
        self.fields = sorted(set(fields))
        super().__init__(
            "Structural config fields require an explicit reset: "
            + ", ".join(self.fields)
        )


class SocietyManager:
    """Owns one SharedWorld and N agents; runs deterministic round-robin ticks."""

    def __init__(self, config: SimConfig | None = None) -> None:
        self.config = config or SimConfig()
        self._build()
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self.running: bool = False
        # Set while a worker thread has exclusive access to the live society
        # (headless training or an optional LLM job). HTTP readers fail fast;
        # the WebSocket waits on ``_lock`` and never observes partial mutation.
        self._exclusive_worker: bool = False
        # Last run request, so a config patch applied mid-run can resume the
        # loop at the same pace instead of silently pausing the instrument.
        self.last_run_request: RunRequest | None = None

    def _build(self) -> None:
        self.world, self.agents, self.recorder = self._build_artifacts(
            self.config)
        self.gender_society = GenderSociety(self.config)
        self.gender_scenario_manifest: GenderScenario | None = None

    @staticmethod
    def _build_artifacts(config: SimConfig) -> tuple[
        SharedWorld, dict[int, CognitiveAgent], MetricsRecorder,
    ]:
        """Construct a complete society off to the side before committing it."""
        world = SharedWorld(config)
        agents = {
            agent_id: CognitiveAgent(
                config,
                agent_id=agent_id,
                shared_world=world,
                defer_trace_logging=True,
            )
            for agent_id in world.agents
        }
        recorder = MetricsRecorder(int(config.metrics_history_max))
        return world, agents, recorder

    def _validated_merge(self, updates: dict) -> SimConfig:
        """Return a fully validated config built from the live values + patch."""
        return SimConfig.model_validate({
            **self.config.model_dump(),
            **updates,
        })

    # ------------------------------------------------------------- ticking
    def tick(self) -> list[CycleTrace]:
        """Run one society tick: each agent cycles once, in ascending id order."""
        if self.config.gender_experience_enabled:
            self.gender_society.deliver_pending(self.agents)
        else:
            self.gender_society.clear_pending()
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
        if self.config.gender_experience_enabled:
            cycle_tick = traces[0].tick if traces else int(self.world.tick) + 1
            self.gender_society.after_tick(
                self.agents, tick=int(cycle_tick)
            )
        world_events = self.world.advance_tick()
        if world_events:
            for trace in traces:
                trace.result.events.extend(world_events)
        if self.config.trace_logging:
            for agent_id, trace in zip(sorted(self.agents), traces):
                self.agents[agent_id].trace_logger.log(trace)
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
            if isinstance(task, asyncio.Task):
                loop = task.get_loop()
                try:
                    current_loop = asyncio.get_running_loop()
                except RuntimeError:
                    current_loop = None
                if current_loop is loop:
                    task.cancel()
                elif loop.is_running():
                    loop.call_soon_threadsafe(task.cancel)
                else:
                    task.cancel()
            else:
                task.cancel()

    # ------------------------------------------------------------- lifecycle
    def reset(self, patch: dict | ConfigPatch | None = None) -> None:
        updates = {}
        if patch is not None:
            updates = (patch.model_dump(exclude_none=True)
                       if isinstance(patch, ConfigPatch)
                       else {k: v for k, v in dict(patch).items() if v is not None})
        candidate = self._validated_merge(updates)
        world, agents, recorder = self._build_artifacts(candidate)
        self.pause()
        self.config = candidate
        self.world = world
        self.agents = agents
        self.recorder = recorder
        self.gender_society = GenderSociety(candidate)
        self.gender_scenario_manifest = None

    def install_gender_scenario(self, scenario: GenderScenario) -> None:
        """Apply a validated scenario through one full transactional reset."""
        manifest = scenario.model_copy(deep=True)
        n_agents = max(manifest.agents) + 1
        candidate = SimConfig.model_validate({
            **self.config.model_dump(),
            "random_seed": manifest.seed,
            "n_agents": n_agents,
            "gender_experience_enabled": bool(manifest.enable),
        })
        world, agents, recorder = self._build_artifacts(candidate)
        gender_society = GenderSociety(
            candidate,
            context=manifest.social_context,
            seed=manifest.seed,
            dispositions={
                agent_id: item.observer_disposition
                for agent_id, item in manifest.agents.items()
            },
        )
        for agent_id, item in manifest.agents.items():
            initial_events = [
                event for event in manifest.initial_events
                if event.target_id == agent_id
            ]
            agents[agent_id].install_gender_experience(
                item.profile,
                item.life_course,
                social_context=manifest.social_context,
                seed=manifest.seed,
                initial_events=initial_events,
            )

        # Commit only after every artifact and private engine validates.
        self.pause()
        self.config = candidate
        self.world = world
        self.agents = agents
        self.recorder = recorder
        self.gender_society = gender_society
        self.gender_scenario_manifest = manifest

    async def apply_config(self, patch: dict | ConfigPatch) -> list[str]:
        """Validate and apply a non-structural config patch without rebuilding.

        The shared :class:`SimConfig` instance is mutated under the society lock,
        preserving every module's reference and all accumulated simulation state.
        """
        updates = (patch.model_dump(exclude_none=True)
                   if isinstance(patch, ConfigPatch)
                   else {k: v for k, v in dict(patch).items() if v is not None})

        candidate = self._validated_merge(updates)
        changed = sorted(
            field for field in updates
            if getattr(self.config, field) != getattr(candidate, field)
        )
        structural = RESET_REQUIRED_FIELDS.intersection(changed)
        if structural:
            raise ConfigRequiresReset(structural)

        async with self._lock:
            candidate = self._validated_merge(updates)
            changed = sorted(
                field for field in updates
                if getattr(self.config, field) != getattr(candidate, field)
            )
            structural = RESET_REQUIRED_FIELDS.intersection(changed)
            if structural:
                raise ConfigRequiresReset(structural)
            if not changed:
                return []

            old_values = {
                field: getattr(self.config, field)
                for field in changed
            }
            # Index rebuilds and all-store persistence can scale with an
            # unbounded life history. Keep the event loop responsive while the
            # society lock + public busy gate preserve an atomic live view.
            self._exclusive_worker = True
            try:
                migration_plan, prepare_cancelled = (
                    await _run_cancellation_safe_worker(
                    self._prepare_hot_config_migrations,
                    old_values,
                    candidate,
                ))
                if prepare_cancelled:
                    raise asyncio.CancelledError
                rollback_state = self._snapshot_hot_config_state(
                    migration_plan)
                try:
                    for field in changed:
                        setattr(self.config, field, getattr(candidate, field))
                    _unused, commit_cancelled = (
                        await _run_cancellation_safe_worker(
                            self._commit_hot_config_migrations,
                            migration_plan,
                        ))
                except Exception:
                    self._rollback_hot_config(
                        old_values, rollback_state)
                    raise
                if commit_cancelled:
                    # The transaction is complete and internally consistent;
                    # only now may request cancellation propagate.
                    raise asyncio.CancelledError
            finally:
                self._exclusive_worker = False
            return changed

    def _prepare_hot_config_migrations(
        self, old_values: dict, candidate: SimConfig,
    ) -> dict:
        """Build every fallible migration result without touching live state."""
        plan: dict = {}

        if (old_values.get("vector_memory_enabled") is False
                and candidate.vector_memory_enabled):
            indexes = {}
            for agent_id, agent in self.agents.items():
                index = type(agent.vector_index)()
                index.rebuild(agent.memory._records)
                indexes[agent_id] = index
            plan["vector_indexes"] = indexes

        if "tasks_enabled" in old_values:
            enabled = bool(candidate.tasks_enabled)
            plan["world_task_manager"] = (
                TaskManager(candidate.grid_size) if enabled else None)
            plan["agent_task_managers"] = {
                agent_id: (
                    TaskManager(candidate.grid_size) if enabled else None)
                for agent_id in self.agents
            }

        if "persist_memory" in old_values:
            plan["memory_stores"] = {
                agent_id: (
                    MemoryStore.for_agent(agent.agent_id, candidate.n_agents)
                    if candidate.persist_memory else None
                )
                for agent_id, agent in self.agents.items()
            }

        goals_changed = (
            "language_drive_enabled" in old_values
            or "individuation_enabled" in old_values
        )
        if goals_changed:
            prepared_models = {}
            for agent_id, agent in self.agents.items():
                prepared = deepcopy(agent.self_model)
                if "language_drive_enabled" in old_values:
                    if candidate.language_drive_enabled:
                        prepared.set_goal(
                            "invent a language", source="system")
                    else:
                        prepared.remove_goal(
                            "invent a language", source="system")
                if "individuation_enabled" in old_values:
                    if candidate.individuation_enabled:
                        prepared.set_goal(
                            "become someone", source="system")
                    else:
                        prepared.remove_goal(
                            "become someone", source="system")

                prepared_state = {
                    "active_goals": list(prepared._state.active_goals),
                    "goal_sources": deepcopy(prepared._goal_sources),
                }
                if "individuation_enabled" in old_values:
                    prepared_state["last_individuation"] = (
                        compute_individuation(
                            prepared.snapshot(),
                            memory_count=len(agent.memory._records),
                        )
                        if candidate.individuation_enabled else None
                    )
                prepared_models[agent_id] = prepared_state
            plan["self_models"] = prepared_models

        return plan

    def _snapshot_hot_config_state(self, plan: dict) -> dict:
        """Capture only live references that the prepared plan may replace."""
        snapshot: dict = {}
        if "vector_indexes" in plan:
            snapshot["vector_indexes"] = {
                agent_id: self.agents[agent_id].vector_index
                for agent_id in plan["vector_indexes"]
            }
        if "world_task_manager" in plan:
            snapshot["world_task_manager"] = self.world.task_manager
            snapshot["agent_task_managers"] = {
                agent_id: self.agents[agent_id].world.task_manager
                for agent_id in plan["agent_task_managers"]
            }
        if "memory_stores" in plan:
            snapshot["memory_stores"] = {
                agent_id: (
                    self.agents[agent_id].memory_store,
                    self.agents[agent_id].memory._store,
                )
                for agent_id in plan["memory_stores"]
            }
        if "self_models" in plan:
            snapshot["self_models"] = {}
            for agent_id in plan["self_models"]:
                agent = self.agents[agent_id]
                has_sources = hasattr(agent.self_model, "_goal_sources")
                snapshot["self_models"][agent_id] = {
                    "active_goals": list(
                        agent.self_model._state.active_goals),
                    "has_goal_sources": has_sources,
                    "goal_sources": deepcopy(getattr(
                        agent.self_model, "_goal_sources", {})),
                    "last_individuation": agent._last_individuation,
                }
        return snapshot

    def _commit_hot_config_migrations(self, plan: dict) -> None:
        """Attach prepared migration objects to the live society."""
        for agent_id, index in plan.get("vector_indexes", {}).items():
            self.agents[agent_id].vector_index = index

        if "world_task_manager" in plan:
            self.world.task_manager = plan["world_task_manager"]
            for agent_id, task_manager in plan["agent_task_managers"].items():
                self.agents[agent_id].world.task_manager = task_manager

        for agent_id, prepared in plan.get("self_models", {}).items():
            agent = self.agents[agent_id]
            agent.self_model._state.active_goals[:] = prepared["active_goals"]
            agent.self_model._goal_sources = deepcopy(
                prepared["goal_sources"])
            if "last_individuation" in prepared:
                agent._last_individuation = prepared["last_individuation"]

        # Persist last: after this transaction succeeds, only infallible
        # reference assignments remain. Earlier attachment failures therefore
        # cannot leave newly written files behind a rolled-back config.
        memory_stores = plan.get("memory_stores", {})
        durable = [
            (store, self.agents[agent_id].memory._records)
            for agent_id, store in memory_stores.items()
            if store is not None
        ]
        if durable:
            atomic_save_batch(durable)
        for agent_id, store in memory_stores.items():
            agent = self.agents[agent_id]
            agent.memory_store = store
            agent.memory._store = store

    def _rollback_hot_config(
        self, old_values: dict, snapshot: dict,
    ) -> None:
        """Defensively restore config and live references after commit failure."""
        for field, value in old_values.items():
            setattr(self.config, field, value)

        for agent_id, index in snapshot.get("vector_indexes", {}).items():
            self.agents[agent_id].vector_index = index

        if "world_task_manager" in snapshot:
            self.world.task_manager = snapshot["world_task_manager"]
            for agent_id, task_manager in snapshot[
                    "agent_task_managers"].items():
                self.agents[agent_id].world.task_manager = task_manager

        for agent_id, stores in snapshot.get("memory_stores", {}).items():
            agent = self.agents[agent_id]
            agent.memory_store, agent.memory._store = stores

        for agent_id, prior in snapshot.get("self_models", {}).items():
            agent = self.agents[agent_id]
            agent.self_model._state.active_goals[:] = prior["active_goals"]
            if prior["has_goal_sources"]:
                agent.self_model._goal_sources = deepcopy(
                    prior["goal_sources"])
            elif hasattr(agent.self_model, "_goal_sources"):
                delattr(agent.self_model, "_goal_sources")
            agent._last_individuation = prior["last_individuation"]

    # ------------------------------------------------------------- accessors
    def agent(self, agent_id: int) -> CognitiveAgent:
        return self.agents[int(agent_id)]

    def language_summary(self) -> dict:
        """The society's emergent dictionary + lexical convergence (Phase 6)."""
        from core.language import society_language_summary
        return society_language_summary({aid: ag.lexicon for aid, ag in self.agents.items()})

    def gender_society_state(self) -> GenderSocietyState:
        """Return the public/observer layer; private profiles are excluded."""
        return self.gender_society.state()

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
            "gender": (
                self.gender_society.state().model_dump()
                if self.config.gender_experience_enabled
                else None
            ),
        }
