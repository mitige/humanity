# core/scenario.py
"""Reproducible scripted scenarios (Phase 4).

FUNCTIONAL NOTE: a ScenarioRunner drives a fresh SocietyManager deterministically,
applying scripted interventions at their tick and recording per-agent metrics. It
orchestrates the existing interaction modalities; it does not change the cycle.
"""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from core.introspection import DISCLAIMER_EN
from core.society import SocietyManager
from schemas.models import (
    AttendRequest, CognitiveInjection, Intervention, PerturbRequest, Scenario,
    ScenarioResult, WorldStimulus,
)
from storage.persistence import MemoryStore


class ScenarioRunner:
    """Runs a declarative Scenario on a fresh society and returns its time series."""

    def run(self, scenario: Scenario) -> ScenarioResult:
        patch = scenario.config
        if scenario.seed is not None:
            patch = patch.model_copy(update={"random_seed": int(scenario.seed)})
        mgr = SocietyManager()
        mgr.reset(patch)
        mgr.recorder.clear()
        self._isolate_persistence(mgr)

        by_tick: dict[int, list[Intervention]] = {}
        for iv in scenario.interventions:
            by_tick.setdefault(int(iv.at_tick), []).append(iv)

        for t in range(int(scenario.ticks)):
            for iv in by_tick.get(t, []):
                self._apply(mgr, iv)
            mgr.tick()

        summary = {
            str(aid): {
                "energy": round(float(ag.metrics().energy), 4),
                "identity": ag.self_model_state().identity,
            }
            for aid, ag in mgr.agents.items()
        }
        return ScenarioResult(name=scenario.name, ticks=int(scenario.ticks),
                              series=mgr.recorder.series(), summary=summary,
                              disclaimer=DISCLAIMER_EN)

    @staticmethod
    def _isolate_persistence(mgr: SocietyManager) -> None:
        """Make the run hermetic: redirect every agent's autobiographical-memory
        store to a unique, ephemeral temp file and drop any records the default
        store loaded from the shared on-disk ``memory.json``.

        Without this a scenario would read and write the global memory file, so
        successive runs would start from accumulated records and diverge -- the
        runner is meant to be reproducible, so it must never touch persisted state.
        """
        base = Path(tempfile.gettempdir()) / "humanity_scenario"
        for ag in mgr.agents.values():
            store = MemoryStore(base / f"{uuid.uuid4().hex}.json")
            ag.memory_store = store
            ag.memory._store = store
            ag.memory._records = []
            ag.memory._next_id = 1

    @staticmethod
    def _apply(mgr: SocietyManager, iv: Intervention) -> None:
        ag = mgr.agents.get(int(iv.agent_id))
        if ag is None:
            return
        p = dict(iv.params or {})
        kind = str(iv.type)
        if kind == "stimulus":
            ag.world_stimulus(WorldStimulus(
                kind=str(p.get("kind", "curio")), x=p.get("x"), y=p.get("y"),
                intensity=float(p.get("intensity", 1.0))))
        elif kind == "perturb":
            ag.perturb(PerturbRequest(type=str(p.get("ptype", p.get("type", "surprise"))),
                                      magnitude=float(p.get("magnitude", 1.0))))
        elif kind == "goal":
            ag.set_goal(str(p.get("goal", "")))
        elif kind == "inject":
            ag.inject(CognitiveInjection(
                content=str(p.get("content", "signal")),
                activation=float(p.get("activation", 0.85)),
                precision=float(p.get("precision", 0.9)), ttl=int(p.get("ttl", 1))))
        elif kind == "attend":
            ag.attend(AttendRequest(target_id=int(p.get("target_id", 0)),
                                    strength=float(p.get("strength", 1.0)),
                                    ttl=int(p.get("ttl", 3))))
