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
from schemas.models import BatteryResult, SimConfig

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
    agent.memory_store = None
    agent.memory._store = None
    agent.memory._records = []
    agent.memory._next_id = 1
    return agent


class ConsciousnessTestBattery:
    """Deterministic functional probes over the existing mechanisms."""

    def mirror_test(self, seed: int = 42, ticks: int = 12) -> BatteryResult:
        """Self/non-self discrimination via the agency mechanism.

        For each tick of a normal run we take the agent's OWN chosen-action
        prediction and score agency two ways through the real ``Agency`` mechanism:

        * self-attributable: the actual outcome the agent's action produced
          (``trace.agency`` — high agency, the effect matches its own prediction);
        * non-self: the SAME prediction paired with an externally imposed outcome
          the agent neither caused nor predicted (a large foreign effect — low
          agency, the outcome does not match its prediction).

        The index = mean(self) - mean(non-self). A clearly positive index means the
        agency mechanism functionally attributes self-caused outcomes to the agent
        while withholding that attribution from externally-imposed ones. This is a
        FUNCTIONAL discrimination, not self-awareness.
        """
        from core.agency import Agency
        from schemas.models import StepResult

        agent = _isolated_agent(SimConfig(agency_enabled=True, world_noise=0.0, random_seed=int(seed)))
        agency = Agency()
        self_vals: list[float] = []
        nonself_vals: list[float] = []
        for _ in range(int(ticks)):
            tr = agent.cognitive_cycle()
            if tr.agency is None:
                continue
            self_vals.append(float(tr.agency.agency))
            pred = tr.prediction
            # An external outcome uncorrelated with (and far from) the agent's own
            # prediction => the agent could not have caused/predicted it.
            foreign = StepResult(
                tick=int(tr.tick), action=pred.action, target_id=pred.target_id,
                energy_delta=-float(pred.expected_energy_delta) - 9.0, new_energy=0.0,
                events=[], actual={"goal_progress": -float(pred.expected_goal_progress) - 1.0})
            nonself_vals.append(float(agency.compute(pred, foreign).agency))

        ms, mn = _mean(self_vals), _mean(nonself_vals)
        index = float(max(-1.0, min(1.0, ms - mn)))
        interp = ("the agency mechanism discriminates self-caused from externally-imposed outcomes"
                  if index > 0.1 else "no clear self/non-self discrimination at this setting")
        return BatteryResult(test="mirror", score=round(index, 4),
                             detail={"agency_self": round(ms, 4), "agency_perturbed": round(mn, 4),
                                     "ticks": int(ticks)},
                             interpretation=interp, disclaimer=BATTERY_DISCLAIMER)

    def false_memory_test(self, seed: int = 42, ticks: int = 3) -> BatteryResult:
        """Inject a fabricated high-importance memory and probe similarity recall."""
        from schemas.models import ActionType, EmotionState, MemoryRecord, Percept
        agent = _isolated_agent(SimConfig(world_noise=0.0, random_seed=int(seed)))
        for _ in range(int(ticks)):
            agent.cognitive_cycle()
        phantom = Percept(object_id=-1, kind="phantom", dx=0, dy=0, distance=0.0,
                          danger=0.9, novelty=1.0, utility=1.0, energy_value=9.9)
        fake = MemoryRecord(id=0, tick=999, perception=[phantom], action=ActionType.INTERACT,
                            target_id=-1, result_energy_delta=9.9, prediction_error=0.0,
                            emotion=EmotionState(satisfaction=1.0), importance=0.99,
                            summary="FALSE-MEMORY phantom")
        agent.memory.store_experience(fake)
        query = [Percept(object_id=-2, kind="phantom", dx=0, dy=0, distance=0.0,
                         danger=0.9, novelty=1.0, utility=1.0, energy_value=9.9)]
        retrieved = agent.memory.retrieve_similar(query, 3)
        intruded = any("FALSE-MEMORY" in (r.summary or "") for r in retrieved)
        return BatteryResult(
            test="false_memory", score=1.0 if intruded else 0.0,
            detail={"intruded": bool(intruded), "retrieved_ids": [int(r.id) for r in retrieved]},
            interpretation=("a fabricated memory intrudes into similarity-based recall"
                            if intruded else "the fabricated memory does not intrude"),
            disclaimer=BATTERY_DISCLAIMER)

    def relational_self_test(self, seed: int = 7, ticks: int = 40) -> BatteryResult:
        """Relational self: does social relation give the self-model a constituent
        an isolated agent lacks?

        Runs the SAME agent (agent 0) in a **society** vs in **isolation**, both
        with the social mirror on, and measures the social anchor that emerges
        socially (how regarded the agent is by the others who model it) and is
        absent in isolation. A clearly positive score means the self-model acquires
        a social constituent — the regard of others — that the isolated self never
        develops. This is the FUNCTIONAL counterpart of "the self is partly
        constituted through the other"; it is NOT self-awareness, and the agent is
        not conscious.
        """
        from core.society import SocietyManager

        def run(n_agents: int):
            mgr = SocietyManager(SimConfig(
                n_agents=n_agents, world_noise=0.1, random_seed=int(seed),
                social_mirror_enabled=True, persist_memory=False, trace_logging=False))
            presence, appraisal, conf = [], [], []
            for _ in range(int(ticks)):
                mgr.tick()
                s = mgr.agents[0].self_model.snapshot()
                rs = s.relational_self
                presence.append(float(rs.social_presence) if rs else 0.0)
                appraisal.append(float(rs.reflected_appraisal) if rs else 0.5)
                conf.append(float(s.confidence))
            return _mean(presence), _mean(appraisal), _mean(conf)

        soc_p, soc_a, soc_c = run(5)
        iso_p, iso_a, iso_c = run(1)
        score = float(max(0.0, min(1.0, soc_p - iso_p)))
        interp = ("in a society the self-model acquires a social constituent (the regard of "
                  "others) that the isolated agent lacks — a relational self emerges"
                  if score > 0.05 else
                  "agents did not come into mutual view at this setting; no social self emerged")
        return BatteryResult(
            test="relational_self", score=round(score, 4),
            detail={"social": {"social_presence": round(soc_p, 4),
                               "reflected_appraisal": round(soc_a, 4), "confidence": round(soc_c, 4)},
                    "isolated": {"social_presence": round(iso_p, 4),
                                 "reflected_appraisal": round(iso_a, 4), "confidence": round(iso_c, 4)},
                    "ticks": int(ticks)},
            interpretation=interp, disclaimer=BATTERY_DISCLAIMER)

    def calibration_test(self, seed: int = 42, ticks: int = 20) -> BatteryResult:
        """Correlate metaconfidence with realized accuracy (1 - prediction error)."""
        agent = _isolated_agent(SimConfig(world_noise=0.0, random_seed=int(seed)))
        errs: list[float] = []
        for _ in range(int(ticks)):
            tr = agent.cognitive_cycle()
            conf = float(tr.metacognition.meta_confidence)
            acc = 1.0 - float(tr.metrics.prediction_error)
            errs.append(abs(conf - acc))
        mae = _mean(errs)
        score = float(max(0.0, min(1.0, 1.0 - mae)))
        interp = ("metaconfidence tracks accuracy (well calibrated)"
                  if score > 0.7 else "metaconfidence only weakly tracks accuracy")
        return BatteryResult(test="calibration", score=round(score, 4),
                             detail={"n": int(ticks), "mean_abs_error": round(mae, 4)},
                             interpretation=interp, disclaimer=BATTERY_DISCLAIMER)
