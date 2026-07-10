# core/scenario.py
"""Reproducible scripted scenarios (Phase 4).

FUNCTIONAL NOTE: a ScenarioRunner drives a fresh SocietyManager deterministically,
applying scripted interventions at their tick and recording per-agent metrics. It
orchestrates the existing interaction modalities; it does not change the cycle.
"""
from __future__ import annotations

from core.introspection import DISCLAIMER_EN
from core.society import SocietyManager
from schemas.models import (
    AttendRequest, CognitiveInjection, Intervention, PerturbRequest, Scenario,
    ScenarioResult, SimConfig, WorldStimulus,
)


class ScenarioRunner:
    """Runs a declarative Scenario on a fresh society and returns its time series."""

    def run(self, scenario: Scenario) -> ScenarioResult:
        config_values = scenario.config.model_dump(exclude_none=True)
        if scenario.seed is not None:
            config_values["random_seed"] = int(scenario.seed)
        # Scientific probes are hermetic regardless of a caller's persistence
        # preferences.  Apply this before construction so no live memory is read
        # and no trace or memory write can occur during the run.
        config_values.update(persist_memory=False, trace_logging=False)
        mgr = SocietyManager(SimConfig.model_validate(config_values))

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
    def _apply(mgr: SocietyManager, iv: Intervention) -> None:
        ag = mgr.agents.get(int(iv.agent_id))
        if ag is None:
            raise ValueError(f"scenario agent {iv.agent_id} does not exist")
        p = dict(iv.params or {})
        kind = str(iv.type)
        if kind == "stimulus":
            ag.world_stimulus(WorldStimulus.model_validate(p))
        elif kind == "perturb":
            ag.perturb(PerturbRequest.model_validate(p))
        elif kind == "goal":
            ag.set_goal(str(p["goal"]))
        elif kind == "inject":
            ag.inject(CognitiveInjection.model_validate(p))
        elif kind == "attend":
            ag.attend(AttendRequest.model_validate(p))
        else:  # defensive for model_construct()/version-skewed checkpoints
            raise ValueError(f"unknown scenario intervention type {kind!r}")
