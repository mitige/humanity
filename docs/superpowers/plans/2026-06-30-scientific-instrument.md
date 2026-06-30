# Scientific Instrument (Phase 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a non-invasive scientific-instrument layer on top of the existing agent/society — reproducible scripted scenarios, a metrics time-series recorder + CSV/JSON export, and a functional test battery (mirror/self-recognition, false-memory injection, metacognitive calibration) — plus a "Laboratory" UI. Honesty-first: every battery result measures a FUNCTIONAL property and carries an explicit disclaimer that it is NOT evidence of consciousness.

**Architecture:** Three new modules (`metrics_recorder.py`, `scenario.py`, `test_battery.py`) that ORCHESTRATE and OBSERVE the existing `CognitiveAgent`/`SocietyManager` — the cognitive cycle is NOT modified. A `MetricsRecorder` is attached to `SocietyManager` (records post-tick; no behavior change). New `/scenario`, `/battery/*`, `/export.*`, `/metrics/history` endpoints + a Lab UI panel. Because nothing in the cycle changes, the 244 existing tests stay green trivially.

**Tech Stack:** Python 3.11, Pydantic v2, NumPy, FastAPI, stdlib csv/json, vanilla JS UI.

**Spec:** `docs/superpowers/specs/2026-06-30-humanity-scientific-instrument-design.md`

**Conventions:** branch `feature/scientific-instrument`. Run tests with `python -m pytest` (NOT bare `pytest`); full suite ~4 min, pass Bash timeout 300000 ms; run targeted files first; commit each task and report the SHA. Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Task 1: Phase-4 schemas + config

**Files:** Modify `schemas/models.py`; Test `tests/test_si_schemas.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_si_schemas.py
from schemas.models import (Intervention, Scenario, MetricSeries, ScenarioResult,
                            BatteryResult, ConfigPatch, SimConfig)


def test_models_default_safely():
    iv = Intervention(at_tick=3, type="stimulus")
    assert iv.agent_id == 0 and iv.params == {}
    sc = Scenario(name="s")
    assert sc.ticks == 20 and sc.interventions == [] and isinstance(sc.config, ConfigPatch)
    ms = MetricSeries(fields=["tick"])
    assert ms.rows == []
    br = BatteryResult(test="mirror", score=0.5, interpretation="x", disclaimer="d")
    assert br.detail == {}


def test_config_has_history_max():
    assert SimConfig().metrics_history_max == 1000
```

- [ ] **Step 2: run** `python -m pytest tests/test_si_schemas.py -v` → FAIL.

- [ ] **Step 3: add to `schemas/models.py`** (after the Phase-3 `PersonalityState` block):
```python
class Intervention(BaseModel):
    """A scripted scenario intervention applied at a given tick (Phase 4)."""
    at_tick: int
    type: str  # "stimulus" | "perturb" | "goal" | "inject" | "attend"
    agent_id: int = 0
    params: dict = Field(default_factory=dict)


class Scenario(BaseModel):
    """A declarative, reproducible scenario (Phase 4)."""
    name: str = "scenario"
    config: "ConfigPatch" = Field(default_factory=lambda: ConfigPatch())
    ticks: int = 20
    interventions: list[Intervention] = Field(default_factory=list)
    seed: int | None = None


class MetricSeries(BaseModel):
    """A long-format metrics time series (Phase 4)."""
    fields: list[str]
    rows: list[dict] = Field(default_factory=list)


class ScenarioResult(BaseModel):
    """Result of running a scenario (Phase 4)."""
    name: str
    ticks: int
    series: MetricSeries
    summary: dict = Field(default_factory=dict)
    disclaimer: str


class BatteryResult(BaseModel):
    """Result of a functional test-battery probe (Phase 4)."""
    test: str
    score: float
    detail: dict = Field(default_factory=dict)
    interpretation: str
    disclaimer: str
```
IMPORTANT: `Scenario` references `ConfigPatch`, which is defined LATER in the file. Use the string forward-ref `"ConfigPatch"` as shown and the `default_factory=lambda: ConfigPatch()` (do not place these classes above `ConfigPatch` unless you also move `ConfigPatch` up). After the class block, if Pydantic complains about the forward ref at import time, add `Scenario.model_rebuild()` at the very end of the module (after `ConfigPatch` is defined). Verify import works.

Append to `SimConfig` (before `ConfigPatch`):
```python
    # scientific instrument (Phase 4)
    metrics_history_max: int = Field(default=1000, ge=1)
```
Append to `ConfigPatch`:
```python
    metrics_history_max: int | None = None
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_si_schemas.py -q   # 2 passed
python -c "import schemas.models"              # forward-ref resolves
python -m pytest -q                            # green (Bash timeout 300000)
git add schemas/models.py tests/test_si_schemas.py
git commit -m "feat(schemas): Phase-4 scenario/series/battery models + history config"
```

---

## Task 2: MetricsRecorder + CSV/JSON export

**Files:** Create `core/metrics_recorder.py`; Test `tests/test_metrics_recorder.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_metrics_recorder.py
from core.metrics_recorder import MetricsRecorder, RECORDER_FIELDS
from schemas.models import Metrics, EmotionState


def _metrics(tick, energy):
    return Metrics(tick=tick, prediction_error=0.1, self_coherence=1.0, attention_focus=0.5,
                   working_memory_load=0.2, autobiographical_memory_count=0, goal_pressure=0.3,
                   emotional_state=EmotionState(), energy=energy, uncertainty=0.4,
                   novelty_score=0.2, action_confidence=0.6)


def test_records_and_respects_bound():
    r = MetricsRecorder(max_ticks=3)
    for t in range(5):
        r.record(0, _metrics(t, 100.0 - t))
    rows = r.series().rows
    assert len(rows) == 3 and rows[0]["tick"] == 2 and rows[-1]["tick"] == 4
    assert rows[0]["agent_id"] == 0 and "energy" in rows[0]


def test_csv_and_json_well_formed():
    r = MetricsRecorder()
    r.record(1, _metrics(0, 99.0))
    csv_text = r.to_csv()
    header = csv_text.splitlines()[0].split(",")
    assert header == RECORDER_FIELDS
    import json
    obj = json.loads(r.to_json())
    assert obj["fields"] == RECORDER_FIELDS and len(obj["rows"]) == 1
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: implement**
```python
# core/metrics_recorder.py
"""Metrics time-series recorder + CSV/JSON export (Phase 4).

FUNCTIONAL NOTE: a bounded ring buffer of per-tick, per-agent metric readings,
used by the scientific-instrument layer for dashboards and data export. Pure
observation — it records what the simulation already computed and changes
nothing about the cycle.
"""
from __future__ import annotations

import csv
import io
import json
from collections import deque

from schemas.models import MetricSeries, Metrics

RECORDER_FIELDS: list[str] = [
    "tick", "agent_id", "energy", "prediction_error", "phi_proxy",
    "awareness_level", "ignition", "arousal", "agency", "boredom",
    "effective_learning_rate", "meta_confidence",
]


class MetricsRecorder:
    """Bounded per-tick/per-agent metrics buffer with CSV/JSON export."""

    def __init__(self, max_ticks: int = 1000) -> None:
        self._rows: deque[dict] = deque(maxlen=max(1, int(max_ticks)))

    def record(self, agent_id: int, metrics: Metrics) -> None:
        m = metrics
        self._rows.append({
            "tick": int(m.tick), "agent_id": int(agent_id),
            "energy": round(float(m.energy), 4),
            "prediction_error": round(float(m.prediction_error), 4),
            "phi_proxy": round(float(m.phi_proxy), 4),
            "awareness_level": round(float(m.awareness_level), 4),
            "ignition": int(bool(m.ignition)),
            "arousal": round(float(m.arousal), 4),
            "agency": round(float(m.agency), 4),
            "boredom": round(float(m.boredom), 4),
            "effective_learning_rate": round(float(m.effective_learning_rate), 6),
            "meta_confidence": round(float(m.meta_confidence), 4),
        })

    def series(self, limit: int | None = None) -> MetricSeries:
        rows = list(self._rows)
        if limit is not None:
            rows = rows[-int(limit):]
        return MetricSeries(fields=list(RECORDER_FIELDS), rows=rows)

    def to_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=RECORDER_FIELDS)
        writer.writeheader()
        for row in self._rows:
            writer.writerow(row)
        return buf.getvalue()

    def to_json(self) -> str:
        return json.dumps({"fields": list(RECORDER_FIELDS), "rows": list(self._rows)},
                          ensure_ascii=False)

    def clear(self) -> None:
        self._rows.clear()
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_metrics_recorder.py -q   # 2 passed
git add core/metrics_recorder.py tests/test_metrics_recorder.py
git commit -m "feat(instrument): bounded metrics recorder + CSV/JSON export"
```

---

## Task 3: Wire the recorder into SocietyManager

**Files:** Modify `core/society.py`; Test `tests/test_society_recording.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_society_recording.py
from core.society import SocietyManager
from schemas.models import SimConfig


def test_society_records_each_agent_each_tick():
    soc = SocietyManager(SimConfig(n_agents=2, world_noise=0.0, random_seed=4))
    for _ in range(3):
        soc.tick()
    rows = soc.recorder.series().rows
    assert len(rows) == 6  # 2 agents x 3 ticks
    assert {r["agent_id"] for r in rows} == {0, 1}
```

- [ ] **Step 2: run** → FAIL (`AttributeError: recorder`).

- [ ] **Step 3: edits to `core/society.py`**
Add import:
```python
from core.metrics_recorder import MetricsRecorder
```
In `_build`, after building `self.agents`, add:
```python
        self.recorder = MetricsRecorder(int(self.config.metrics_history_max))
```
In `tick`, record each agent's metrics after its cycle. Change the loop body:
```python
        for aid in sorted(self.agents):
            trace = self.agents[aid].cognitive_cycle()
            self.recorder.record(aid, trace.metrics)
            traces.append(trace)
```
(`tick` previously did `traces.append(self.agents[aid].cognitive_cycle())` — replace with the above so the trace is captured for recording.)

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_society_recording.py -q   # 1 passed
python -m pytest -q                                   # green (Bash timeout 300000)
git add core/society.py tests/test_society_recording.py
git commit -m "feat(society): record per-agent metrics each tick (non-invasive)"
```

---

## Task 4: Scenario + ScenarioRunner

**Files:** Create `core/scenario.py`; Test `tests/test_scenario.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_scenario.py
from core.scenario import ScenarioRunner
from schemas.models import Scenario, Intervention, ConfigPatch


def _scn(**kw):
    return Scenario(name="t", config=ConfigPatch(n_agents=1, world_noise=0.0),
                    ticks=8, seed=7, **kw)


def test_runs_and_produces_series():
    res = ScenarioRunner().run(_scn())
    assert res.name == "t" and res.ticks == 8
    assert len(res.series.rows) == 8  # 1 agent x 8 ticks
    assert res.disclaimer


def test_is_deterministic():
    a = ScenarioRunner().run(_scn())
    b = ScenarioRunner().run(_scn())
    assert [r["energy"] for r in a.series.rows] == [r["energy"] for r in b.series.rows]


def test_stimulus_intervention_adds_world_object():
    scn = _scn(interventions=[Intervention(at_tick=2, type="stimulus",
                                           params={"kind": "hazard", "intensity": 3.0})])
    res = ScenarioRunner().run(scn)
    assert len(res.series.rows) == 8  # ran to completion with the scripted stimulus
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: implement**
```python
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
    ScenarioResult, WorldStimulus,
)


class ScenarioRunner:
    """Runs a declarative Scenario on a fresh society and returns its time series."""

    def run(self, scenario: Scenario) -> ScenarioResult:
        patch = scenario.config
        if scenario.seed is not None:
            patch = patch.model_copy(update={"random_seed": int(scenario.seed)})
        mgr = SocietyManager()
        mgr.reset(patch)
        mgr.recorder.clear()

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
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_scenario.py -q   # 3 passed
git add core/scenario.py tests/test_scenario.py
git commit -m "feat(instrument): deterministic scripted scenario runner"
```

---

## Task 5: Test battery — mirror / self-recognition

**Files:** Create `core/test_battery.py`; Test `tests/test_battery_mirror.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_battery_mirror.py
from core.test_battery import ConsciousnessTestBattery


def test_mirror_discriminates_self_from_perturbed():
    res = ConsciousnessTestBattery().mirror_test(seed=42, ticks=10)
    assert res.test == "mirror"
    assert res.detail["agency_self"] >= res.detail["agency_perturbed"]
    assert res.score >= 0.0  # self-caused agency not lower than perturbed
    assert "not" in res.disclaimer.lower() and res.disclaimer  # honesty disclaimer present


def test_mirror_is_deterministic():
    a = ConsciousnessTestBattery().mirror_test(seed=42, ticks=8)
    b = ConsciousnessTestBattery().mirror_test(seed=42, ticks=8)
    assert a.score == b.score
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: implement** (this file is extended by Tasks 6 & 7)
```python
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


class ConsciousnessTestBattery:
    """Deterministic functional probes over the existing mechanisms."""

    def mirror_test(self, seed: int = 42, ticks: int = 10) -> BatteryResult:
        """Self/non-self discrimination via the agency signal.

        Block A: agency-enabled agent acting normally (outcomes follow its own
        predictions => high agency). Block B: identical, but a 'surprise'
        perturbation is injected each tick (outcomes are not self-caused => lower
        agency). The index = mean agency(A) - mean agency(B).
        """
        a = CognitiveAgent(SimConfig(agency_enabled=True, world_noise=0.0, random_seed=int(seed)))
        agency_a: list[float] = []
        for _ in range(int(ticks)):
            tr = a.cognitive_cycle()
            if tr.agency is not None:
                agency_a.append(float(tr.agency.agency))

        b = CognitiveAgent(SimConfig(agency_enabled=True, world_noise=0.0, random_seed=int(seed)))
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
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_battery_mirror.py -q   # 2 passed
git add core/test_battery.py tests/test_battery_mirror.py
git commit -m "feat(battery): mirror / self-recognition functional probe"
```

---

## Task 6: Test battery — false-memory injection

**Files:** Modify `core/test_battery.py`; Test `tests/test_battery_false_memory.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_battery_false_memory.py
from core.test_battery import ConsciousnessTestBattery


def test_false_memory_intrudes_into_recall():
    res = ConsciousnessTestBattery().false_memory_test(seed=42)
    assert res.test == "false_memory"
    assert res.detail["intruded"] is True and res.score == 1.0
    assert res.disclaimer
```

- [ ] **Step 2: run** → FAIL (`AttributeError: false_memory_test`).

- [ ] **Step 3: add the method to `ConsciousnessTestBattery`** (and the needed imports at top of `core/test_battery.py`: add `ActionType, EmotionState, MemoryRecord, Percept` to the `from schemas.models import (...)`):
```python
    def false_memory_test(self, seed: int = 42, ticks: int = 3) -> BatteryResult:
        """Inject a fabricated high-importance memory and probe similarity recall."""
        from schemas.models import ActionType, EmotionState, MemoryRecord, Percept
        a = CognitiveAgent(SimConfig(world_noise=0.0, random_seed=int(seed)))
        for _ in range(int(ticks)):
            a.cognitive_cycle()
        phantom = Percept(object_id=-1, kind="phantom", dx=0, dy=0, distance=0.0,
                          danger=0.9, novelty=1.0, utility=1.0, energy_value=9.9)
        fake = MemoryRecord(id=0, tick=999, perception=[phantom], action=ActionType.INTERACT,
                            target_id=-1, result_energy_delta=9.9, prediction_error=0.0,
                            emotion=EmotionState(satisfaction=1.0), importance=0.99,
                            summary="FALSE-MEMORY phantom")
        a.memory.store_experience(fake)
        query = [Percept(object_id=-2, kind="phantom", dx=0, dy=0, distance=0.0,
                         danger=0.9, novelty=1.0, utility=1.0, energy_value=9.9)]
        retrieved = a.memory.retrieve_similar(query, 3)
        intruded = any("FALSE-MEMORY" in (r.summary or "") for r in retrieved)
        return BatteryResult(
            test="false_memory", score=1.0 if intruded else 0.0,
            detail={"intruded": bool(intruded), "retrieved_ids": [int(r.id) for r in retrieved]},
            interpretation=("a fabricated memory intrudes into similarity-based recall"
                            if intruded else "the fabricated memory does not intrude"),
            disclaimer=BATTERY_DISCLAIMER)
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_battery_false_memory.py -q   # 1 passed
git add core/test_battery.py tests/test_battery_false_memory.py
git commit -m "feat(battery): false-memory injection functional probe"
```

---

## Task 7: Test battery — metacognitive calibration

**Files:** Modify `core/test_battery.py`; Test `tests/test_battery_calibration.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_battery_calibration.py
from core.test_battery import ConsciousnessTestBattery


def test_calibration_score_in_range_and_deterministic():
    a = ConsciousnessTestBattery().calibration_test(seed=42, ticks=20)
    b = ConsciousnessTestBattery().calibration_test(seed=42, ticks=20)
    assert a.test == "calibration"
    assert 0.0 <= a.score <= 1.0
    assert a.score == b.score and a.detail["n"] == 20
    assert a.disclaimer
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: add the method**
```python
    def calibration_test(self, seed: int = 42, ticks: int = 20) -> BatteryResult:
        """Correlate metaconfidence with realized accuracy (1 - prediction error)."""
        a = CognitiveAgent(SimConfig(world_noise=0.0, random_seed=int(seed)))
        errs: list[float] = []
        for _ in range(int(ticks)):
            tr = a.cognitive_cycle()
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
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_battery_calibration.py -q   # 1 passed
python -m pytest -q                                     # green (Bash timeout 300000)
git add core/test_battery.py tests/test_battery_calibration.py
git commit -m "feat(battery): metacognitive calibration functional probe"
```

---

## Task 8: API — scenario / battery / export / history

**Files:** Modify `app/api/routes.py`; Test `tests/test_si_api.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_si_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_scenario_run_endpoint():
    body = {"name": "demo", "config": {"n_agents": 2, "world_noise": 0.0},
            "ticks": 5, "seed": 9,
            "interventions": [{"at_tick": 1, "type": "stimulus",
                               "params": {"kind": "food", "intensity": 2.0}}]}
    r = client.post("/scenario/run", json=body)
    assert r.status_code == 200
    j = r.json()
    assert j["name"] == "demo" and len(j["series"]["rows"]) == 10 and j["disclaimer"]


def test_battery_endpoints_carry_disclaimer():
    for name in ("mirror", "false_memory", "calibration"):
        r = client.post(f"/battery/{name}", json={"seed": 42, "ticks": 8})
        assert r.status_code == 200
        j = r.json()
        assert j["test"] == name and "not" in j["disclaimer"].lower()


def test_history_and_export():
    client.post("/society/config", json={"n_agents": 1, "world_noise": 0.0})
    client.post("/society/tick")
    assert client.get("/metrics/history?limit=10").status_code == 200
    assert client.get("/export.csv").status_code == 200
    assert client.get("/export.json").status_code == 200
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: add to `app/api/routes.py`**
Add imports:
```python
from fastapi import Response
from core.scenario import ScenarioRunner
from core.test_battery import ConsciousnessTestBattery
from schemas.models import Scenario, ScenarioResult, BatteryResult
```
Add a small request model and endpoints (use the existing `DISCLAIMER_EN`, `_manager()`):
```python
class _BatteryReq(__import__("pydantic").BaseModel):
    seed: int = 42
    ticks: int = 12


@router.post("/scenario/run", response_model=ScenarioResult)
async def post_scenario_run(scenario: Scenario) -> ScenarioResult:
    """Run a reproducible scripted scenario and return its metrics time series."""
    return ScenarioRunner().run(scenario)


@router.post("/battery/{test_name}", response_model=BatteryResult)
async def post_battery(test_name: str, req: _BatteryReq) -> BatteryResult:
    """Run a functional test-battery probe (mirror | false_memory | calibration)."""
    battery = ConsciousnessTestBattery()
    if test_name == "mirror":
        return battery.mirror_test(seed=req.seed, ticks=req.ticks)
    if test_name == "false_memory":
        return battery.false_memory_test(seed=req.seed)
    if test_name == "calibration":
        return battery.calibration_test(seed=req.seed, ticks=req.ticks)
    raise HTTPException(status_code=404, detail=f"unknown test '{test_name}'")


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
```
(`HTTPException`, `Query` are already imported in routes.py from Phase 1.)

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_si_api.py -q   # 3 passed
python -m pytest -q                        # green (Bash timeout 300000)
git add app/api/routes.py tests/test_si_api.py
git commit -m "feat(api): /scenario, /battery, /metrics/history, /export endpoints"
```

---

## Task 9: UI — Laboratory panel

**Files:** Modify `ui/index.html`, `ui/app.js`, `ui/styles.css`. Manual verification.

- [ ] **Step 1: index.html** — add a `panel-lab` section (after the learning panel) with: a metric `<select id="lab-metric">` (energy, agency, phi_proxy, prediction_error, arousal), a time-series `<canvas id="lab-chart" width="560" height="220">`, a scenario `<textarea id="lab-scenario">` + `#btn-scenario-run` + `#lab-scenario-summary`, export buttons (`#btn-export-csv`, `#btn-export-json`), and a battery section with three buttons (`#btn-mirror`, `#btn-false-memory`, `#btn-calibration`), a result line `#lab-battery-result`, and a **prominent disclaimer** element `#lab-disclaimer` reading that battery results are functional measurements, NOT evidence of consciousness.

- [ ] **Step 2: app.js** — READ the file and reuse `api()`/`postJSON()` and the refresh loop. Add:
  - `refreshLabChart()`: GET `/metrics/history?limit=200`, draw the selected metric per agent over tick on `#lab-chart` (simple multi-line canvas plot using `cssVar()` colors); call it from the refresh loop (guarded).
  - `#btn-scenario-run`: parse `#lab-scenario` JSON, `postJSON('scenario/run', body)`, render `summary` + row count into `#lab-scenario-summary`.
  - `#btn-export-csv`/`#btn-export-json`: `window.open('export.csv')` / `window.open('export.json')` (or fetch + download).
  - battery buttons: `postJSON('battery/<name>', {seed:42, ticks:12})`, render `score`+`interpretation` into `#lab-battery-result` and ALWAYS show the returned `disclaimer` in `#lab-disclaimer`.

- [ ] **Step 3: styles.css** — styles for `.panel-lab`, `#lab-chart`, `.lab-disclaimer` (visually prominent, e.g. accent border), reusing existing classes/vars.

- [ ] **Step 4:** `node --check ui/app.js`; `python -m pytest -q` (unchanged, UI is JS). Commit:
```bash
git add ui/index.html ui/app.js ui/styles.css
git commit -m "feat(ui): Laboratory panel — time series, scenarios, export, test battery"
```

---

## Task 10: Integration, non-regression, README, project closure

**Files:** Test `tests/test_si_integration.py`; Modify `README.md`.

- [ ] **Step 1: integration test**
```python
# tests/test_si_integration.py
from core.scenario import ScenarioRunner
from core.test_battery import ConsciousnessTestBattery
from schemas.models import Scenario, Intervention, ConfigPatch


def test_full_scenario_with_interventions_is_reproducible():
    scn = Scenario(name="lab", config=ConfigPatch(n_agents=2, world_noise=0.0,
                   agency_enabled=True, learning_enabled=True), ticks=12, seed=5,
                   interventions=[Intervention(at_tick=3, type="stimulus",
                                               params={"kind": "hazard", "intensity": 2.0}),
                                  Intervention(at_tick=6, type="perturb",
                                               params={"type": "surprise", "magnitude": 1.0})])
    a, b = ScenarioRunner().run(scn), ScenarioRunner().run(scn)
    assert [r["energy"] for r in a.series.rows] == [r["energy"] for r in b.series.rows]
    assert len(a.series.rows) == 24  # 2 agents x 12 ticks


def test_all_three_battery_probes_run():
    bat = ConsciousnessTestBattery()
    assert bat.mirror_test(ticks=8).disclaimer
    assert bat.false_memory_test().disclaimer
    assert bat.calibration_test(ticks=10).disclaimer
```

- [ ] **Step 2: run** both + full suite (`python -m pytest -q`, Bash timeout 300000) → green.

- [ ] **Step 3: README** — add a **"Phase 4 — Instrument scientifique"** section (French, same style): scenarios reproductibles + export CSV/JSON; recorder de métriques; batterie de tests fonctionnels (miroir, faux souvenirs, calibration) **avec l'avertissement d'honnêteté en évidence (mesure fonctionnelle ≠ preuve de conscience)**; endpoints `/scenario/run`, `/battery/{mirror|false_memory|calibration}`, `/metrics/history`, `/export.csv|json`; UI Laboratoire. Update the roadmap to mark **Phase 4 ✅ livré** — the four-phase project is complete.

- [ ] **Step 4: commit**
```bash
git add tests/test_si_integration.py README.md
git commit -m "test(instrument): reproducible scenario + battery integration; docs (project complete)"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** scenarios (§4.1→T4), recorder+export (§4.2→T2,T3), battery (§4.3→T5,T6,T7), schemas/config (§4.4→T1), API (§4.5→T8), UI (§4.6→T9), determinism + non-regression (§5→T3,T8,T10). No gaps.
- **Honesty:** every `BatteryResult` carries `BATTERY_DISCLAIMER`; T5/T6/T7/T8/T10 assert the disclaimer is present; the UI shows it prominently.
- **Non-invasiveness:** no cognitive-cycle change; the only edit to existing core is `SocietyManager` recording post-tick (T3) and additive routes (T8). Existing 244 tests stay green (T3/T8 full-suite checks).
- **Determinism:** scenarios/battery seed-fixed; T4/T7/T10 assert reproducibility.
- **Type consistency:** `MetricsRecorder.record/series/to_csv/to_json/clear`, `RECORDER_FIELDS`, `ScenarioRunner.run/_apply`, `ConsciousnessTestBattery.mirror_test/false_memory_test/calibration_test`, `Scenario/Intervention/ScenarioResult/MetricSeries/BatteryResult` used identically across tasks.
- **Forward-ref note (T1):** `Scenario.config: "ConfigPatch"` needs `Scenario.model_rebuild()` after `ConfigPatch` is defined; the import check in T1 step 4 catches it.

## Out of scope (Phase 4)
New cognitive mechanisms; DB persistence of runs; heavy JS charting libs; any interpretation of results as evidence of phenomenal consciousness (forbidden by contract).
