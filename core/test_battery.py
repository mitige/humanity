# core/test_battery.py
"""Functional test battery (Phase 4).

HONESTY NOTE (load-bearing): each test measures whether the simulated MECHANISMS
exhibit a measurable FUNCTIONAL property — self/non-self discrimination, memory
intrusion, metaconfidence calibration. Passing a test is NOT evidence of
self-awareness or any subjective experience. The agent is not conscious. Every
BatteryResult carries this disclaimer.
"""
from __future__ import annotations

from core.agent import CognitiveAgent
from schemas.models import BatteryResult, PerturbRequest, SimConfig

BATTERY_DISCLAIMER = (
    "Functional measurement only: this probes whether the simulated mechanisms "
    "exhibit a measurable functional property; it is NOT evidence of self-"
    "awareness, sentience, or any subjective experience. The agent is not conscious."
)


def _mean(xs: list[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 0.0


def _isolated_agent(config: SimConfig) -> CognitiveAgent:
    """Create a hermetic agent with in-RAM episodic memory only.

    Battery probes must be deterministic and must never read or write the live
    instrument's shared ``storage/data/memory.json``; nulling the store and
    clearing any preloaded records makes each probe start from an empty memory.
    """
    agent = CognitiveAgent(config)
    agent.memory._store = None
    agent.memory._records = []
    agent.memory._next_id = 1
    return agent


class ConsciousnessTestBattery:
    """Deterministic functional probes over the existing mechanisms."""

    def mirror_test(self, seed: int = 42, ticks: int = 10) -> BatteryResult:
        """Self/non-self discrimination via the agency signal.

        Block A: agency-enabled agent acting normally (outcomes follow its own
        predictions => high agency). Block B: identical, but a 'surprise'
        perturbation is injected each tick (outcomes are not self-caused => lower
        agency). The index = mean agency(A) - mean agency(B).
        """
        a = _isolated_agent(SimConfig(agency_enabled=True, world_noise=0.0, random_seed=int(seed)))
        agency_a: list[float] = []
        for _ in range(int(ticks)):
            tr = a.cognitive_cycle()
            if tr.agency is not None:
                agency_a.append(float(tr.agency.agency))

        b = _isolated_agent(SimConfig(agency_enabled=True, world_noise=0.0, random_seed=int(seed)))
        agency_b: list[float] = []
        for _ in range(int(ticks)):
            b.perturb(PerturbRequest(type="surprise", magnitude=1.0))
            tr = b.cognitive_cycle()
            if tr.agency is not None:
                agency_b.append(float(tr.agency.agency))

        ma, mb = _mean(agency_a), _mean(agency_b)
        index = float(max(-1.0, min(1.0, ma - mb)))
        interp = ("the agency mechanism discriminates self- from non-self-caused outcomes"
                  if index > 0.1 else "no clear self/non-self discrimination at this setting")
        return BatteryResult(test="mirror", score=round(index, 4),
                             detail={"agency_self": round(ma, 4), "agency_perturbed": round(mb, 4),
                                     "ticks": int(ticks)},
                             interpretation=interp, disclaimer=BATTERY_DISCLAIMER)
