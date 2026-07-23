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
    """Create a hermetic agent with in-RAM episodic memory and no trace I/O.

    Battery probes must be deterministic and must never read or write the live
    instrument's shared storage.  The disk-free flags are applied before agent
    construction so a probe cannot briefly load persisted state and then clear it.
    """
    hermetic_config = SimConfig.model_validate({
        **config.model_dump(),
        "persist_memory": False,
        "trace_logging": False,
    })
    return CognitiveAgent(hermetic_config)


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

    # ------------------------------------------------------------------ #
    # Phase 5 — psychophysics signatures of conscious ACCESS (functional)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _probe_hit(agent, source: str) -> bool:
        """One tick; did ``source`` win the competition AND ignite (global access)?"""
        tr = agent.cognitive_cycle()
        ws = tr.workspace
        return bool(ws.ignited and ws.winner_source == source)

    def masking_test(self, seed: int = 42, ticks: int = 3, reps: int = 6) -> BatteryResult:
        """Backward masking: a mask presented with the target abolishes its access.

        In masking experiments a stimulus that is reliably reported alone stops
        being reported when followed by a stronger mask — while still being
        processed. Here: a moderate probe injection reaches ignition when
        presented ALONE, but presented together with a strong mask injection it
        loses the competition and stays subliminal. Score = P(access | alone)
        − P(access | masked). A positive score reproduces the masking signature
        of ACCESS — a property of the workspace mechanism, not of experience.
        """
        from schemas.models import CognitiveInjection

        warmup = max(1, int(ticks))
        alone_hits: list[float] = []
        masked_hits: list[float] = []
        for r in range(int(reps)):
            cfg = SimConfig(world_noise=0.0, random_seed=int(seed) + r,
                            competition_sharpness=1.0,
                            persist_memory=False, trace_logging=False)
            # Target alone.
            a = _isolated_agent(cfg)
            for _ in range(warmup):
                a.cognitive_cycle()
            a.inject(CognitiveInjection(content="masking target", source="probe_target",
                                        activation=0.97, precision=0.97, ttl=1))
            alone_hits.append(1.0 if self._probe_hit(a, "probe_target") else 0.0)
            # Target + mask (same tick): the mask outcompetes the target.
            b = _isolated_agent(cfg)
            for _ in range(warmup):
                b.cognitive_cycle()
            b.inject(CognitiveInjection(content="masking target", source="probe_target",
                                        activation=0.97, precision=0.97, ttl=1))
            b.inject(CognitiveInjection(content="mask", source="probe_mask",
                                        activation=0.99, precision=0.99, ttl=1))
            masked_hits.append(1.0 if self._probe_hit(b, "probe_target") else 0.0)

        p_alone, p_masked = _mean(alone_hits), _mean(masked_hits)
        score = float(max(-1.0, min(1.0, p_alone - p_masked)))
        interp = ("the mask abolishes the target's global access while the target alone "
                  "reaches it — the functional masking signature"
                  if score > 0.3 else
                  "no clear masking effect at this setting (target and mask reach access alike)")
        return BatteryResult(test="masking", score=round(score, 4),
                             detail={"p_access_alone": round(p_alone, 4),
                                     "p_access_masked": round(p_masked, 4),
                                     "reps": int(reps), "warmup": warmup},
                             interpretation=interp, disclaimer=BATTERY_DISCLAIMER)

    def blink_test(self, seed: int = 42, ticks: int = 3, reps: int = 6) -> BatteryResult:
        """Attentional blink: access to T2 drops right after a strong T1 ignition.

        After a strong T1 ignites, the homeostatic effective threshold is
        transiently elevated (recent-score adaptation), so an identical T2
        arriving one tick later fails to reach access — while the same T2
        without a preceding T1 succeeds. Score = P(T2 access | control)
        − P(T2 access | after T1). A positive score reproduces the attentional-
        blink signature of ACCESS — a workspace property, not experience.
        """
        from schemas.models import CognitiveInjection

        warmup = max(1, int(ticks))
        t2 = dict(content="blink T2", source="probe_t2", activation=0.97, precision=0.97, ttl=1)
        control_hits: list[float] = []
        blink_hits: list[float] = []
        for r in range(int(reps)):
            cfg = SimConfig(world_noise=0.0, random_seed=int(seed) + r,
                            competition_sharpness=1.0,
                            persist_memory=False, trace_logging=False)
            # Control: T2 with no preceding T1 (same absolute timing).
            a = _isolated_agent(cfg)
            for _ in range(warmup + 1):
                a.cognitive_cycle()
            a.inject(CognitiveInjection(**t2))
            control_hits.append(1.0 if self._probe_hit(a, "probe_t2") else 0.0)
            # Blink: a strong T1 ignites on the tick before T2.
            b = _isolated_agent(cfg)
            for _ in range(warmup):
                b.cognitive_cycle()
            # T1 dwells two ticks (attentional dwelling): its ignition elevates
            # the adaptive threshold AND its maintained access crowds out T2.
            b.inject(CognitiveInjection(content="blink T1", source="probe_t1",
                                        activation=0.99, precision=0.99, ttl=2))
            b.cognitive_cycle()  # T1 tick (ignition elevates the adaptive threshold)
            b.inject(CognitiveInjection(**t2))
            blink_hits.append(1.0 if self._probe_hit(b, "probe_t2") else 0.0)

        p_control, p_blink = _mean(control_hits), _mean(blink_hits)
        score = float(max(-1.0, min(1.0, p_control - p_blink)))
        interp = ("T2 reaches global access alone but not on the tick after a strong T1 — "
                  "the functional attentional-blink signature (threshold adaptation)"
                  if score > 0.3 else
                  "no clear blink at this setting (T2 access unaffected by T1)")
        return BatteryResult(test="blink", score=round(score, 4),
                             detail={"p_t2_control": round(p_control, 4),
                                     "p_t2_after_t1": round(p_blink, 4),
                                     "reps": int(reps), "warmup": warmup},
                             interpretation=interp, disclaimer=BATTERY_DISCLAIMER)

    def priming_test(self, seed: int = 42, ticks: int = 2, reps: int = 6) -> BatteryResult:
        """Subliminal repetition priming: unaccessed content facilitates its return.

        A weak prime is presented and stays SUBLIMINAL (no ignition); when the
        same content is re-presented at borderline strength one tick later, it
        reaches access — while the identical presentation without the prime does
        not. Runs with the residual-facilitation substrate enabled. Score =
        P(access | primed) − P(access | unprimed), with the prime's subliminality
        verified. A positive score reproduces the subliminal-priming signature:
        content can shape processing WITHOUT global access — mechanism, not
        experience.
        """
        from schemas.models import CognitiveInjection

        warmup = max(1, int(ticks))
        probe = dict(content="prime S", source="probe_s", activation=0.75, precision=0.85, ttl=1)
        primed_hits: list[float] = []
        unprimed_hits: list[float] = []
        prime_subliminal: list[float] = []
        for r in range(int(reps)):
            cfg = SimConfig(world_noise=0.0, random_seed=int(seed) + r,
                            competition_sharpness=1.0,
                            persist_memory=False, trace_logging=False,
                            priming_enabled=True, priming_gain=1.2, priming_decay=0.8)
            # Primed: subliminal presentation, one absent tick, re-presentation.
            # (Facilitation only applies to returning content, so the gap tick is
            # part of the paradigm — as in repetition-priming experiments.)
            a = _isolated_agent(cfg)
            for _ in range(warmup):
                a.cognitive_cycle()
            a.inject(CognitiveInjection(content="prime S", source="probe_s",
                                        activation=0.5, precision=0.8, ttl=1))
            tr = a.cognitive_cycle()
            prime_subliminal.append(
                0.0 if (tr.workspace.ignited and tr.workspace.winner_source == "probe_s") else 1.0)
            a.cognitive_cycle()  # gap tick: the prime is absent
            a.inject(CognitiveInjection(**probe))
            primed_hits.append(1.0 if self._probe_hit(a, "probe_s") else 0.0)
            # Unprimed control: identical timing, no prime.
            b = _isolated_agent(cfg)
            for _ in range(warmup + 2):
                b.cognitive_cycle()
            b.inject(CognitiveInjection(**probe))
            unprimed_hits.append(1.0 if self._probe_hit(b, "probe_s") else 0.0)

        p_primed, p_unprimed = _mean(primed_hits), _mean(unprimed_hits)
        score = float(max(-1.0, min(1.0, p_primed - p_unprimed)))
        interp = ("a subliminal presentation facilitates its own later access "
                  "(repetition priming without global access)"
                  if score > 0.3 else
                  "no clear priming effect at this setting")
        return BatteryResult(test="priming", score=round(score, 4),
                             detail={"p_access_primed": round(p_primed, 4),
                                     "p_access_unprimed": round(p_unprimed, 4),
                                     "prime_stayed_subliminal": round(_mean(prime_subliminal), 4),
                                     "reps": int(reps)},
                             interpretation=interp, disclaimer=BATTERY_DISCLAIMER)

    def language_genesis_test(self, seed: int = 42, ticks: int = 120) -> BatteryResult:
        """Does a shared lexicon EMERGE when the invent-a-language drive is on?

        Runs the same society (4 agents, hermetic, in-RAM) with the language
        drive ON vs OFF for the same ticks, then measures the naming-game
        outcomes: lexical convergence (mean agreement on each meaning's modal
        word), meanings named, and communicative success. Score = convergence
        with the drive on (0 when no meaning is shared). Emergent conventions
        over strength tables — NOT understanding, reference, intention, or any
        evidence of consciousness.
        """
        from core.society import SocietyManager

        def run(drive: bool):
            # A denser meeting ground (smaller grid, wider earshot) so the
            # naming game gets enough encounters within the probe's budget.
            mgr = SocietyManager(SimConfig(
                n_agents=4, world_noise=0.1, random_seed=int(seed),
                grid_size=10, comm_radius=8, satiation_enabled=True,
                persist_memory=False, trace_logging=False,
                language_drive_enabled=drive))
            for _ in range(int(ticks)):
                mgr.tick()
            summary = mgr.language_summary()
            successes = [float(ag.lexicon.success_rate) for ag in mgr.agents.values()]
            vocab = [len(ag.lexicon.vocabulary()) for ag in mgr.agents.values()]
            return summary, _mean(successes), _mean(vocab)

        on, on_success, on_vocab = run(True)
        off, off_success, off_vocab = run(False)
        convergence = float(on["convergence"] or 0.0)
        interp = (f"a shared lexicon emerged: {on['n_meanings_named']} meaning(s) named, "
                  f"convergence {convergence:.2f}, communicative success {on_success:.2f} "
                  "— conventions born from the naming game, absent without the drive"
                  if convergence > 0.5 and on["n_meanings_named"] >= 2 else
                  "no clear shared lexicon emerged at this setting")
        return BatteryResult(
            test="language_genesis", score=round(convergence, 4),
            detail={"drive_on": {"convergence": on["convergence"],
                                 "n_meanings_named": on["n_meanings_named"],
                                 "mean_success": round(on_success, 4),
                                 "mean_vocabulary": round(on_vocab, 2),
                                 "dictionary": {m: d["modal_word"]
                                                for m, d in on["dictionary"].items()}},
                    "drive_off": {"convergence": off["convergence"],
                                  "n_meanings_named": off["n_meanings_named"],
                                  "mean_success": round(off_success, 4)},
                    "ticks": int(ticks)},
            interpretation=interp, disclaimer=BATTERY_DISCLAIMER)

    def reality_monitor_test(self, seed: int = 42, ticks: int = 40) -> BatteryResult:
        """Source-monitoring accuracy under generative load (PRM probe).

        Runs an agent with its generators active (imagination, inner speech)
        and the reality monitor on, and measures how often the higher-order
        source verdict matches the actual origin of the conscious content —
        including the misattribution taxonomy (hallucination analogue:
        self-generated content judged external). Accuracy is a FUNCTIONAL
        property of the classifier, not evidence of experienced reality.
        """
        agent = _isolated_agent(SimConfig(
            world_noise=0.1, random_seed=int(seed), persist_memory=False,
            trace_logging=False, reality_monitor_enabled=True,
            imagination_enabled=True, inner_speech_enabled=True,
            curiosity_enabled=True))
        n = correct = 0
        halluc = insert = 0
        last_acc = 0.0
        for _ in range(int(ticks)):
            tr = agent.cognitive_cycle()
            rm = tr.reality_monitor
            if rm is None:
                continue
            halluc, insert = int(rm.hallucinations), int(rm.insertions)
            last_acc = float(rm.accuracy)
            if rm.correct is None:
                continue
            n += 1
            correct += int(rm.correct)
        raw_acc = (correct / n) if n else 0.0
        interp = (f"the source verdict matches the actual origin {raw_acc:.0%} of the time; "
                  f"{halluc} self-generated content(s) were misjudged as external — the "
                  "functional hallucination analogue PRM predicts"
                  if n else "no scored verdicts at this setting")
        return BatteryResult(test="reality_monitor", score=round(float(raw_acc), 4),
                             detail={"scored": int(n), "correct": int(correct),
                                     "rolling_accuracy": round(last_acc, 4),
                                     "hallucination_analogues": halluc,
                                     "insertion_analogues": insert,
                                     "ticks": int(ticks)},
                             interpretation=interp, disclaimer=BATTERY_DISCLAIMER)

    # ------------------------------------------------------------------ #
    # Phase 8 — matched situated-gender counterfactuals (functional)
    # ------------------------------------------------------------------ #
    def gender_experience_test(
        self,
        *,
        seed: int = 42,
        ticks: int = 24,
        preset_id: str = "nonbinary",
    ):
        """Run four matched pairs over the Phase-8 qualitative assumptions.

        The probe changes one configured factor per pair. It does not estimate
        real-world causal effects and does not diagnose or classify anyone.
        """
        from core.gender_experience import GenderExperienceEngine
        from core.gender_scenarios import get_gender_scenario
        from schemas.models import (
            GenderBatteryArm,
            GenderBatteryResult,
            GenderEventRequest,
            GenderEventType,
            GenderIntentRequest,
            GenderIntentType,
            GenderSocialContext,
        )

        n_ticks = max(4, min(500, int(ticks)))
        base = get_gender_scenario(preset_id, seed=int(seed))
        configured = base.agents[0]
        common_config = SimConfig(
            random_seed=int(seed),
            gender_experience_enabled=True,
            gender_internalization_rate=0.16,
            gender_recovery_rate=0.12,
            persist_memory=False,
            trace_logging=False,
        )

        supportive = GenderSocialContext(
            norm_rigidity=0.1,
            institutional_hostility=0.0,
            baseline_safety=1.0,
            care_access=0.8,
            community_visibility=0.8,
            positive_representation=0.9,
            hostility_enabled=False,
        )
        hostile = GenderSocialContext(
            norm_rigidity=0.95,
            institutional_hostility=0.85,
            baseline_safety=0.2,
            care_access=0.25,
            community_visibility=0.1,
            positive_representation=0.1,
            hostility_enabled=True,
        )
        isolated = GenderSocialContext(
            norm_rigidity=0.4,
            institutional_hostility=0.0,
            baseline_safety=0.7,
            community_visibility=0.0,
            positive_representation=0.0,
            hostility_enabled=False,
        )
        community = GenderSocialContext(
            norm_rigidity=0.4,
            institutional_hostility=0.0,
            baseline_safety=0.7,
            community_visibility=1.0,
            positive_representation=1.0,
            hostility_enabled=False,
        )

        def sensitivity_profile(*, dysphoria: float, euphoria: float):
            body = {
                name: preference.model_copy(
                    update={
                        "dysphoria_sensitivity": dysphoria,
                        "euphoria_sensitivity": euphoria,
                    },
                    deep=True,
                )
                for name, preference
                in configured.profile.body_preferences.items()
            }
            return configured.profile.model_copy(
                update={
                    "profile_id": (
                        f"{configured.profile.profile_id}-"
                        f"d{dysphoria:.2f}-e{euphoria:.2f}"
                    ),
                    "body_preferences": body,
                },
                deep=True,
            )

        arm_specs = {
            "supportive": {
                "profile": configured.profile,
                "context": supportive,
                "mode": "supportive",
            },
            "hostile": {
                "profile": configured.profile,
                "context": hostile,
                "mode": "hostile",
            },
            "expression_allowed": {
                "profile": configured.profile,
                "context": supportive,
                "mode": "expression_allowed",
            },
            "expression_constrained": {
                "profile": configured.profile,
                "context": hostile,
                "mode": "expression_constrained",
            },
            "euphoria_sensitive": {
                "profile": sensitivity_profile(
                    dysphoria=0.0, euphoria=1.0
                ),
                "context": supportive,
                "mode": "euphoria_sensitive",
            },
            "dysphoria_sensitive": {
                "profile": sensitivity_profile(
                    dysphoria=1.0, euphoria=0.15
                ),
                "context": supportive,
                "mode": "dysphoria_sensitive",
            },
            "isolated": {
                "profile": configured.profile,
                "context": isolated,
                "mode": "isolated",
            },
            "community_connected": {
                "profile": configured.profile,
                "context": community,
                "mode": "community",
            },
        }

        def run_arm(arm_id: str, spec: dict) -> GenderBatteryArm:
            engine = GenderExperienceEngine(
                common_config,
                agent_id=0,
                profile=spec["profile"],
                life_course=configured.life_course,
                social_context=spec["context"],
                seed=int(seed),
            )
            curve: list[dict[str, float | int | str]] = []
            mode = spec["mode"]
            for tick in range(1, n_ticks + 1):
                if tick == 1 and mode in {
                    "supportive",
                    "expression_allowed",
                    "euphoria_sensitive",
                    "community",
                }:
                    engine.queue_event(
                        GenderEventRequest(
                            type=GenderEventType.AFFIRMATION,
                            domain="general",
                            intensity=0.9,
                            context_code="matched_battery_affirmation",
                        )
                    )
                if tick == 1 and mode == "expression_allowed":
                    engine.queue_intent(
                        GenderIntentRequest(
                            type=GenderIntentType.ADJUST_EXPRESSION,
                            domain="presentation",
                            urgency=0.8,
                        )
                    )
                if tick == 1 and mode == "expression_constrained":
                    engine.queue_intent(
                        GenderIntentRequest(
                            type=GenderIntentType.CONCEAL,
                            domain="presentation",
                            urgency=0.8,
                            disclosure_scope="public",
                        )
                    )
                if mode in {"hostile", "expression_constrained"} \
                        and tick % 3 == 1:
                    engine.queue_event(
                        GenderEventRequest(
                            type=GenderEventType.INVALIDATION,
                            domain="public_recognition",
                            intensity=0.85,
                            deliberate=True,
                            context_code="matched_battery_hostility",
                        )
                    )
                if mode == "community" and tick % 3 == 1:
                    engine.queue_event(
                        GenderEventRequest(
                            type=GenderEventType.COMMUNITY_CONTACT,
                            domain="social",
                            intensity=0.9,
                            context_code="matched_battery_community",
                        )
                    )
                state = engine.update(tick)
                transition_progress = _mean([
                    value.progress for value in state.transitions.values()
                ])
                accentuation = _mean([
                    value.accentuation for value in state.expression.values()
                ])
                curve.append({
                    "tick": tick,
                    "life_stage": state.life_stage.value,
                    "congruence": round(state.congruence.total, 6),
                    "expression_congruence": round(
                        state.congruence.expression, 6
                    ),
                    "dysphoria": round(state.affect.dysphoria, 6),
                    "euphoria": round(state.affect.euphoria, 6),
                    "fulfillment": round(state.affect.fulfillment, 6),
                    "external_stress": round(
                        state.minority_stress.external_current, 6
                    ),
                    "internalized_transphobia": round(
                        state.minority_stress.internalized_transphobia, 6
                    ),
                    "resilience": round(state.resilience.index, 6),
                    "accentuation": round(accentuation, 6),
                    "transition_progress": round(
                        transition_progress, 6
                    ),
                })
            final_row = curve[-1]
            final = {
                key: float(value)
                for key, value in final_row.items()
                if key not in {"tick", "life_stage"}
            }
            return GenderBatteryArm(
                arm_id=arm_id,
                profile_checksum=engine.profile_checksum,
                curve=curve,
                final=final,
            )

        arms = {
            arm_id: run_arm(arm_id, spec)
            for arm_id, spec in arm_specs.items()
        }

        def difference(left: str, right: str, metric: str) -> float:
            return round(
                arms[left].final[metric] - arms[right].final[metric],
                6,
            )

        comparisons = {
            "supportive_vs_hostile": {
                "same_private_profile": (
                    arms["supportive"].profile_checksum
                    == arms["hostile"].profile_checksum
                ),
                "fulfillment_delta": difference(
                    "supportive", "hostile", "fulfillment"
                ),
                "external_stress_delta": difference(
                    "supportive", "hostile", "external_stress"
                ),
                "internalization_delta": difference(
                    "supportive", "hostile",
                    "internalized_transphobia",
                ),
            },
            "expression_allowed_vs_constrained": {
                "same_private_profile": (
                    arms["expression_allowed"].profile_checksum
                    == arms["expression_constrained"].profile_checksum
                ),
                "expression_congruence_delta": difference(
                    "expression_allowed",
                    "expression_constrained",
                    "expression_congruence",
                ),
                "stress_delta": difference(
                    "expression_allowed",
                    "expression_constrained",
                    "external_stress",
                ),
            },
            "euphoria_vs_dysphoria_sensitivity": {
                "euphoria_delta": difference(
                    "euphoria_sensitive",
                    "dysphoria_sensitive",
                    "euphoria",
                ),
                "dysphoria_delta": difference(
                    "euphoria_sensitive",
                    "dysphoria_sensitive",
                    "dysphoria",
                ),
            },
            "community_vs_isolation": {
                "same_private_profile": (
                    arms["community_connected"].profile_checksum
                    == arms["isolated"].profile_checksum
                ),
                "resilience_delta": difference(
                    "community_connected", "isolated", "resilience"
                ),
                "internalization_delta": difference(
                    "community_connected",
                    "isolated",
                    "internalized_transphobia",
                ),
            },
        }
        return GenderBatteryResult(
            preset_id=preset_id,
            seed=int(seed),
            ticks=n_ticks,
            arms=arms,
            comparisons=comparisons,
            interpretation=(
                "Matched counterfactuals show consequences of the implemented "
                "qualitative assumptions only. They are not estimates of causal "
                "effects in real people and cannot diagnose, classify, or predict "
                "a person's gender or transition."
            ),
        )
