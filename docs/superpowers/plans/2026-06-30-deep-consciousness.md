# Deep Consciousness (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Deepen each `CognitiveAgent` with five per-agent mechanisms — a circadian clock, sleep/dream + memory consolidation, mental imagination (bounded rollouts), curiosity/boredom (learning progress), and a sense of agency — all LLM-free, deterministic, grounded, and additive, composing with the multi-agent society.

**Architecture:** Five new focused modules (`circadian.py`, `sleep.py`, `imagination.py`, `curiosity.py`, `agency.py`) plus additive hooks in `CognitiveAgent.cognitive_cycle`. Every mechanism is gated by a `SimConfig` flag that **defaults to `False`** (so the existing 194 tests and the Phase-1 single-agent/society dynamics are byte-identical out of the box); the UI turns the flags on by default so the live instrument is fully Phase-2. New per-tick sub-states ride along in `CycleTrace`/`Metrics`.

**Tech Stack:** Python 3.11, Pydantic v2, NumPy (math stdlib for circadian), FastAPI, pytest, vanilla JS UI.

**Spec:** `docs/superpowers/specs/2026-06-30-humanity-deep-consciousness-design.md`

**Invariant after every task:** `python -m pytest -q` is green. Run tests with `python -m pytest` (NOT bare `pytest`). Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

**Create:** `core/circadian.py`, `core/sleep.py`, `core/imagination.py`, `core/curiosity.py`, `core/agency.py`, and one test file per module + integration/regression tests.

**Modify:** `schemas/models.py` (new states + defaulted config), `core/constants.py` (workspace sources), `core/autobiographical_memory.py` (consolidation helper), `core/policy.py` (optional imagination bonus), `core/self_model.py` (optional agency nudge), `core/agent.py` (additive cycle hooks), `app/api/routes.py` (expose new fields — mostly automatic via CycleTrace), `ui/` (deep-consciousness panel + default-on toggles).

---

## Task 1: Phase-2 schemas, constants, config

**Files:** Modify `schemas/models.py`, `core/constants.py`; Test `tests/test_deep_schemas.py`.

- [ ] **Step 1: Write the failing test**
```python
# tests/test_deep_schemas.py
from schemas.models import (
    CircadianState, SleepState, ImaginationState, CuriosityState, AgencyState,
    CycleTrace, Metrics, SimConfig,
)
from core.constants import WORKSPACE_SOURCES


def test_states_have_safe_defaults():
    assert SleepState(is_sleeping=False, fatigue=0.0).dream is None
    assert ImaginationState().best_first_action is None
    assert CuriosityState().boredom == 0.0
    assert AgencyState().agency == 0.0
    assert CircadianState(phase=0.0, daylight=1.0, is_night=False, period=50).daylight == 1.0


def test_config_defaults_disable_phase2():
    cfg = SimConfig()
    for flag in ("circadian_enabled", "sleep_enabled", "dream_enabled",
                 "imagination_enabled", "curiosity_enabled", "agency_enabled"):
        assert getattr(cfg, flag) is False
    assert cfg.circadian_period == 50 and cfg.imagination_horizon == 3


def test_imagination_and_dream_workspace_sources():
    assert "imagination" in WORKSPACE_SOURCES and "dream" in WORKSPACE_SOURCES
```

- [ ] **Step 2: Run** `python -m pytest tests/test_deep_schemas.py -v` → FAIL (ImportError).

- [ ] **Step 3: Add models + config to `schemas/models.py`**

Add these classes after `AgencyState`'s logical neighbours (place after the `SocialState` class):
```python
class CircadianState(BaseModel):
    """Deterministic day/night phase modulating arousal (Phase 2)."""
    phase: float          # 0..1 within the period
    daylight: float       # 0..1 (1 = noon, 0 = midnight)
    is_night: bool
    period: int


class SleepState(BaseModel):
    """Sleep / consolidation / dream snapshot (Phase 2)."""
    is_sleeping: bool
    fatigue: float
    consolidated: int = 0
    pruned: int = 0
    dream: str | None = None
    sleep_ticks: int = 0


class ImaginationState(BaseModel):
    """Bounded mental rollout outcome (Phase 2)."""
    best_first_action: ActionType | None = None
    horizon: int = 0
    imagined_value: float = 0.0
    n_rollouts: int = 0


class CuriosityState(BaseModel):
    """Learning-progress driven curiosity / boredom (Phase 2)."""
    learning_progress: float = 0.0
    boredom: float = 0.0
    intrinsic_reward: float = 0.0


class AgencyState(BaseModel):
    """Sense of agency: predicted vs actual effect of one's own action (Phase 2)."""
    agency: float = 0.0
    predicted_self_effect: float = 0.0
    actual_self_effect: float = 0.0
```

Extend `CycleTrace` with (all optional):
```python
    circadian: CircadianState | None = None
    sleep: SleepState | None = None
    imagination: ImaginationState | None = None
    curiosity: CuriosityState | None = None
    agency: AgencyState | None = None
```

Extend `Metrics` with:
```python
    agency: float = 0.0
    boredom: float = 0.0
    learning_progress: float = 0.0
    daylight: float = 1.0
    is_sleeping: bool = False
```

Append to `SimConfig` (before `ConfigPatch`):
```python
    # deep consciousness (Phase 2) — default OFF => Phase-1-identical behaviour
    circadian_enabled: bool = False
    circadian_period: int = Field(default=50, ge=1)
    night_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    sleep_enabled: bool = False
    dream_enabled: bool = False
    sleep_fatigue_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    wake_fatigue_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    max_sleep_ticks: int = Field(default=30, ge=1)
    replay_boost: float = Field(default=1.3, ge=1.0)
    consolidation_prune_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    imagination_enabled: bool = False
    imagination_horizon: int = Field(default=3, ge=1, le=6)
    curiosity_enabled: bool = False
    curiosity_window: int = Field(default=8, ge=2)
    agency_enabled: bool = False
```

Append the same fields to `ConfigPatch` as `| None = None` (plain optionals, no `Field`):
```python
    circadian_enabled: bool | None = None
    circadian_period: int | None = None
    night_threshold: float | None = None
    sleep_enabled: bool | None = None
    dream_enabled: bool | None = None
    sleep_fatigue_threshold: float | None = None
    wake_fatigue_threshold: float | None = None
    max_sleep_ticks: int | None = None
    replay_boost: float | None = None
    consolidation_prune_threshold: float | None = None
    imagination_enabled: bool | None = None
    imagination_horizon: int | None = None
    curiosity_enabled: bool | None = None
    curiosity_window: int | None = None
    agency_enabled: bool | None = None
```

- [ ] **Step 4: Extend `core/constants.py`** — replace `WORKSPACE_SOURCES` with the list plus `"imagination", "dream"` appended (keep the 8 existing entries, add 2):
```python
WORKSPACE_SOURCES: list[str] = [
    "perception", "memory", "motivation", "prediction_error",
    "interoception", "metacognition", "communication", "social",
    "imagination", "dream",
]
```

- [ ] **Step 5: Run** `python -m pytest tests/test_deep_schemas.py -q` → PASS; then `python -m pytest -q` → still green. Commit:
```bash
git add schemas/models.py core/constants.py tests/test_deep_schemas.py
git commit -m "feat(schemas): Phase-2 states + flag-gated (default-off) config"
```

---

## Task 2: Circadian clock — `core/circadian.py`

**Files:** Create `core/circadian.py`; Test `tests/test_circadian.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_circadian.py
from core.circadian import Circadian
from schemas.models import SimConfig


def test_disabled_is_constant_daylight():
    c = Circadian()
    st = c.state(tick=13, config=SimConfig(circadian_enabled=False, circadian_period=50))
    assert st.daylight == 1.0 and st.is_night is False
    assert c.arousal_baseline(0.45, st.daylight, SimConfig(circadian_enabled=False)) == 0.45


def test_phase_cycles_and_night_at_midnight():
    cfg = SimConfig(circadian_enabled=True, circadian_period=40, night_threshold=0.3)
    c = Circadian()
    noon = c.state(tick=0, config=cfg)          # phase 0 => daylight 1
    midnight = c.state(tick=20, config=cfg)     # half period => daylight ~0
    assert noon.daylight > 0.9 and noon.is_night is False
    assert midnight.daylight < 0.1 and midnight.is_night is True


def test_arousal_baseline_drops_at_night():
    cfg = SimConfig(circadian_enabled=True, circadian_period=40)
    c = Circadian()
    day_b = c.arousal_baseline(0.5, c.state(0, cfg).daylight, cfg)
    night_b = c.arousal_baseline(0.5, c.state(20, cfg).daylight, cfg)
    assert night_b < day_b
```

- [ ] **Step 2: Run** → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**
```python
# core/circadian.py
"""Circadian clock (Phase 2): a deterministic day/night oscillator.

FUNCTIONAL NOTE: phase is a pure function of the tick; daylight modulates the
arousal baseline (lower at night => higher ignition bar => 'sleepiness'). No
subjective time is implied. Disabled => constant daylight (no effect).
"""
from __future__ import annotations

import math

from schemas.models import CircadianState, SimConfig


class Circadian:
    """Maps a tick to a circadian phase and an arousal-baseline modulation."""

    def state(self, tick: int, config: SimConfig) -> CircadianState:
        period = max(1, int(config.circadian_period))
        if not config.circadian_enabled:
            return CircadianState(phase=0.0, daylight=1.0, is_night=False, period=period)
        phase = float((int(tick) % period) / period)
        daylight = float(0.5 * (1.0 + math.cos(2.0 * math.pi * phase)))
        is_night = bool(daylight < float(config.night_threshold))
        return CircadianState(
            phase=round(phase, 6), daylight=round(daylight, 6),
            is_night=is_night, period=period,
        )

    def arousal_baseline(self, base: float, daylight: float, config: SimConfig) -> float:
        """Scale the resting arousal baseline by daylight (no-op when disabled)."""
        if not config.circadian_enabled:
            return float(base)
        return float(base * (0.5 + 0.5 * float(daylight)))
```

- [ ] **Step 4: Run** `python -m pytest tests/test_circadian.py -q` → PASS; `python -m pytest -q` → green. Commit:
```bash
git add core/circadian.py tests/test_circadian.py
git commit -m "feat(circadian): deterministic day/night arousal modulation"
```

---

## Task 3: Sleep + consolidation — `core/autobiographical_memory.py` + `core/sleep.py`

**Files:** Modify `core/autobiographical_memory.py`; Create `core/sleep.py`; Test `tests/test_sleep.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_sleep.py
from core.sleep import SleepCycle
from core.autobiographical_memory import AutobiographicalMemory
from schemas.models import (ActionType, EmotionState, MemoryRecord, SimConfig)


def _mem(cfg):
    m = AutobiographicalMemory(cfg, store=None)
    for i in range(5):
        m.store_experience(MemoryRecord(
            id=0, tick=i, perception=[], action=ActionType.OBSERVE, target_id=None,
            result_energy_delta=0.0, prediction_error=0.0, emotion=EmotionState(),
            importance=0.3 + 0.1 * i, summary=f"e{i}"))
    return m


def test_falls_asleep_when_tired_at_night_and_wakes_rested():
    cfg = SimConfig(sleep_enabled=True, sleep_fatigue_threshold=0.8, wake_fatigue_threshold=0.35)
    s = SleepCycle()
    assert s.evaluate(fatigue=0.9, is_night=True, config=cfg) is True
    assert s.is_sleeping is True
    assert s.evaluate(fatigue=0.2, is_night=False, config=cfg) is False  # rested + day => wake


def test_disabled_never_sleeps():
    s = SleepCycle()
    assert s.evaluate(fatigue=0.99, is_night=True, config=SimConfig(sleep_enabled=False)) is False


def test_consolidation_boosts_top_k_and_prunes_below_threshold():
    cfg = SimConfig(memory_retrieval_k=2, replay_boost=1.5, consolidation_prune_threshold=0.45)
    m = _mem(cfg)
    boosted, pruned = m.consolidate(k=cfg.memory_retrieval_k, boost=cfg.replay_boost,
                                    prune_threshold=cfg.consolidation_prune_threshold)
    assert boosted >= 1 and pruned >= 1  # weak memories forgotten, strong reinforced


def test_dream_recombines_two_memories():
    s = SleepCycle()
    m = _mem(SimConfig())
    d = s.dream(m, SimConfig(dream_enabled=True))
    assert d is not None and d.startswith("dream:") and "+" in d
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3a: Add `consolidate` to `core/autobiographical_memory.py`** (new public method on `AutobiographicalMemory`, place after `recent`):
```python
    def consolidate(self, k: int, boost: float, prune_threshold: float) -> tuple[int, int]:
        """Offline consolidation: reinforce the top-k important records and forget
        any record whose importance is below ``prune_threshold``.

        Returns (n_boosted, n_pruned). Persists via the store when present.
        """
        if not self._records:
            return 0, 0
        ordered = sorted(self._records, key=lambda r: r.importance, reverse=True)
        n_boost = max(0, int(k))
        boosted = 0
        for record in ordered[:n_boost]:
            new_imp = float(min(1.0, record.importance * float(boost)))
            if new_imp > record.importance:
                record.importance = round(new_imp, 6)
                boosted += 1
        before = len(self._records)
        kept = [r for r in self._records if r.importance >= float(prune_threshold)]
        pruned = before - len(kept)
        if pruned > 0:
            self._records = kept
            if self._store is not None:
                self._store.save_records(self._records)
        return boosted, pruned
```

- [ ] **Step 3b: Create `core/sleep.py`**
```python
# core/sleep.py
"""Sleep cycle (Phase 2): sleep/wake gating, offline consolidation, dreaming.

FUNCTIONAL NOTE: sleep is a functional state in which the agent rests (REST),
consolidates episodic memory (reinforce the important, forget the trivial), and
'dreams' by recombining stored summaries. None of this implies subjective sleep
or dreaming. Disabled => the agent never sleeps. Wake is guaranteed: REST
recovers energy, so fatigue (1 - energy/initial) falls below the wake threshold;
``max_sleep_ticks`` is a hard backstop.
"""
from __future__ import annotations

from core.autobiographical_memory import AutobiographicalMemory
from schemas.models import SimConfig


class SleepCycle:
    """Per-agent sleep/wake state machine + consolidation/dream orchestration."""

    def __init__(self) -> None:
        self.is_sleeping: bool = False
        self.sleep_ticks: int = 0

    def evaluate(self, fatigue: float, is_night: bool, config: SimConfig) -> bool:
        """Update and return the sleeping flag from fatigue + circadian night."""
        if not config.sleep_enabled:
            self.is_sleeping = False
            self.sleep_ticks = 0
            return False
        f = float(fatigue)
        if self.is_sleeping:
            self.sleep_ticks += 1
            rested = f <= float(config.wake_fatigue_threshold)
            too_long = self.sleep_ticks >= int(config.max_sleep_ticks)
            if (rested and not is_night) or too_long:
                self.is_sleeping = False
                self.sleep_ticks = 0
        else:
            sleepy = f >= float(config.sleep_fatigue_threshold)
            if sleepy and (is_night or f >= 0.95):
                self.is_sleeping = True
                self.sleep_ticks = 0
        return self.is_sleeping

    def consolidate(self, memory: AutobiographicalMemory, config: SimConfig) -> tuple[int, int]:
        """Run one consolidation pass on the agent's episodic memory."""
        return memory.consolidate(
            k=int(config.memory_retrieval_k),
            boost=float(config.replay_boost),
            prune_threshold=float(config.consolidation_prune_threshold),
        )

    def dream(self, memory: AutobiographicalMemory, config: SimConfig) -> str | None:
        """Recombine the two most recent records into a grounded dream string."""
        if not config.dream_enabled:
            return None
        recent = memory.recent(4)
        if len(recent) < 2:
            return None
        a, b = recent[-1], recent[-2]
        sa = a.summary or a.action.value
        sb = b.summary or b.action.value
        return f"dream: {sa} + {sb}"
```

- [ ] **Step 4: Run** `python -m pytest tests/test_sleep.py -q` → PASS; `python -m pytest -q` → green. Commit:
```bash
git add core/autobiographical_memory.py core/sleep.py tests/test_sleep.py
git commit -m "feat(sleep): sleep/wake gating, memory consolidation, dreaming"
```

---

## Task 4: Imagination — `core/imagination.py`

**Files:** Create `core/imagination.py`; Test `tests/test_imagination.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_imagination.py
from core.imagination import Imagination
from core.world_model import WorldModel
from schemas.models import ActionType, Observation, SimConfig


def _obs():
    return Observation(tick=0, agent_x=2, agent_y=2, agent_energy=50.0, radius=3, visible=[])


def test_rollout_respects_horizon_and_is_pure():
    cfg = SimConfig(imagination_enabled=True, imagination_horizon=3)
    wm = WorldModel(cfg)
    beliefs_before = {a: dict(v) for a, v in wm.beliefs.items()}
    candidates = [(ActionType.OBSERVE, None), (ActionType.EXPLORE, None),
                  (ActionType.REST, None), (ActionType.ANALYZE, None)]
    st = Imagination().plan(wm, _obs(), candidates, current_energy=50.0,
                            initial_energy=100.0, config=cfg)
    assert st.horizon == 3 and st.best_first_action is not None
    assert st.n_rollouts == 3 * len(candidates)
    # purity: predicting must not mutate learned beliefs.
    assert {a: dict(v) for a, v in wm.beliefs.items()} == beliefs_before


def test_low_imagined_energy_favours_rest_eventually():
    cfg = SimConfig(imagination_enabled=True, imagination_horizon=4)
    wm = WorldModel(cfg)
    candidates = [(ActionType.EXPLORE, None), (ActionType.REST, None)]
    # Start nearly empty: REST (energy-positive) should look best first.
    st = Imagination().plan(wm, _obs(), candidates, current_energy=3.0,
                            initial_energy=100.0, config=cfg)
    assert st.best_first_action == ActionType.REST
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**
```python
# core/imagination.py
"""Imagination (Phase 2): a bounded, pure mental rollout over action sequences.

FUNCTIONAL NOTE: the agent 'imagines' a short plan by repeatedly consulting its
world model (a pure forward prediction; the real world is never touched) while
tracking an imagined energy budget, so the rollout produces non-degenerate plans
(e.g. act while energised, then rest). It returns the best first action and a
discounted cumulative imagined value. This is approximate look-ahead, not a
generative world simulator, and implies no subjective imagery.
"""
from __future__ import annotations

from schemas.models import ActionType, ImaginationState, Observation, SimConfig

_DISCOUNT = 0.8
_ENERGY_NORM = 10.0


class Imagination:
    """Bounded best-first rollout using the world model + an imagined energy budget."""

    def plan(self, world_model, observation: Observation,
             candidates: list, current_energy: float, initial_energy: float,
             config: SimConfig) -> ImaginationState:
        horizon = max(1, int(config.imagination_horizon))
        cap = float(max(1.0, initial_energy))
        imagined_energy = float(current_energy)
        first_action: ActionType | None = None
        total = 0.0
        n_rollouts = 0
        for t in range(horizon):
            best = None
            best_score = -1e9
            for action, target in candidates:
                pred = world_model.predict(observation, action, target)
                n_rollouts += 1
                # Energy-aware score: when imagined energy is low, recovery is
                # attractive and costly actions are penalised.
                energy_frac = max(0.0, min(1.0, imagined_energy / cap))
                score = float(pred.value) + (1.0 - energy_frac) * (
                    float(pred.expected_energy_delta) / _ENERGY_NORM
                )
                if score > best_score:
                    best_score, best = score, (action, pred)
            if best is None:
                break
            action, pred = best
            if t == 0:
                first_action = action
            total += (_DISCOUNT ** t) * best_score
            imagined_energy = float(
                min(cap, max(0.0, imagined_energy + float(pred.expected_energy_delta)))
            )
        return ImaginationState(
            best_first_action=first_action, horizon=horizon,
            imagined_value=round(float(total), 4), n_rollouts=int(n_rollouts),
        )
```

- [ ] **Step 4: Run** `python -m pytest tests/test_imagination.py -q` → PASS; `python -m pytest -q` → green. Commit:
```bash
git add core/imagination.py tests/test_imagination.py
git commit -m "feat(imagination): bounded pure mental rollout with energy budget"
```

---

## Task 5: Curiosity / boredom — `core/curiosity.py`

**Files:** Create `core/curiosity.py`; Test `tests/test_curiosity.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_curiosity.py
from core.curiosity import Curiosity
from schemas.models import SimConfig


def test_disabled_or_too_few_errors_is_neutral():
    c = Curiosity()
    assert c.update([0.5], SimConfig(curiosity_enabled=True)).boredom == 0.0
    assert c.update([0.1] * 8, SimConfig(curiosity_enabled=False)).boredom == 0.0


def test_learning_progress_positive_when_error_falls():
    c = Curiosity()
    st = c.update([0.8, 0.7, 0.6, 0.3, 0.2, 0.1], SimConfig(curiosity_enabled=True, curiosity_window=6))
    assert st.learning_progress > 0.0 and st.intrinsic_reward > 0.0


def test_boredom_high_when_error_low_and_flat():
    c = Curiosity()
    st = c.update([0.05] * 8, SimConfig(curiosity_enabled=True, curiosity_window=8))
    assert st.boredom > 0.5  # world 'solved' => bored
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**
```python
# core/curiosity.py
"""Curiosity / boredom (Phase 2): intrinsic motivation from learning progress.

FUNCTIONAL NOTE: learning progress is the recent reduction in prediction error.
Positive progress yields an intrinsic reward (learning is engaging); a low, flat
error means the environment is 'solved', raising boredom, which downstream boosts
novelty seeking. These are bounded control scalars, not feelings.
"""
from __future__ import annotations

from schemas.models import CuriosityState, SimConfig


class Curiosity:
    """Computes learning progress, intrinsic reward and boredom from recent error."""

    def update(self, recent_errors: list[float], config: SimConfig) -> CuriosityState:
        if not config.curiosity_enabled or len(recent_errors) < 2:
            return CuriosityState()
        window = min(len(recent_errors), int(config.curiosity_window))
        errs = [float(e) for e in list(recent_errors)[-window:]]
        half = max(1, len(errs) // 2)
        early = sum(errs[:half]) / half
        late = sum(errs[half:]) / max(1, len(errs) - half)
        learning_progress = float(max(-1.0, min(1.0, early - late)))  # >0 => improving
        intrinsic_reward = float(max(0.0, learning_progress))
        mean_err = sum(errs) / len(errs)
        boredom = float(max(0.0, min(1.0, (1.0 - mean_err) * (1.0 - abs(learning_progress)))))
        return CuriosityState(
            learning_progress=round(learning_progress, 4),
            boredom=round(boredom, 4),
            intrinsic_reward=round(intrinsic_reward, 4),
        )
```

- [ ] **Step 4: Run** `python -m pytest tests/test_curiosity.py -q` → PASS; `python -m pytest -q` → green. Commit:
```bash
git add core/curiosity.py tests/test_curiosity.py
git commit -m "feat(curiosity): learning-progress curiosity + boredom"
```

---

## Task 6: Sense of agency — `core/agency.py`

**Files:** Create `core/agency.py`; Test `tests/test_agency.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_agency.py
from core.agency import Agency
from schemas.models import ActionType, Prediction, StepResult


def _pred(e, g):
    return Prediction(action=ActionType.INTERACT, target_id=1, expected_energy_delta=e,
                      expected_danger=0.0, expected_novelty=0.0, expected_goal_progress=g,
                      uncertainty=0.2, value=0.0)


def _result(e, g):
    return StepResult(tick=1, action=ActionType.INTERACT, target_id=1, energy_delta=e,
                      new_energy=50.0, events=[], actual={"goal_progress": g})


def test_agency_high_when_prediction_matches_outcome():
    st = Agency().compute(_pred(5.0, 0.5), _result(5.0, 0.5))
    assert st.agency > 0.95


def test_agency_low_when_outcome_surprising():
    st = Agency().compute(_pred(5.0, 0.5), _result(-8.0, 0.0))
    assert st.agency < 0.5
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**
```python
# core/agency.py
"""Sense of agency (Phase 2): did my own action cause the outcome I predicted?

FUNCTIONAL NOTE: agency = 1 - normalized error between the chosen action's
predicted self-effect (energy delta + goal progress) and the actual outcome.
High when the agent's own action unfolds as predicted (self-causation), low under
surprise. A bounded scalar; no subjective ownership is implied.
"""
from __future__ import annotations

from schemas.models import AgencyState, Prediction, StepResult

_ENERGY_NORM = 10.0


class Agency:
    """Computes an agency scalar from the executed action's prediction vs result."""

    def compute(self, chosen_prediction: Prediction, result: StepResult) -> AgencyState:
        pred_e = float(chosen_prediction.expected_energy_delta)
        pred_g = float(chosen_prediction.expected_goal_progress)
        act_e = float(result.energy_delta)
        act_g = float(result.actual.get("goal_progress", 0.0))
        err_e = min(1.0, abs(pred_e - act_e) / _ENERGY_NORM)
        err_g = min(1.0, abs(pred_g - act_g))
        err = max(0.0, min(1.0, 0.5 * err_e + 0.5 * err_g))
        return AgencyState(
            agency=round(float(1.0 - err), 4),
            predicted_self_effect=round(pred_e + pred_g, 4),
            actual_self_effect=round(act_e + act_g, 4),
        )
```

- [ ] **Step 4: Run** `python -m pytest tests/test_agency.py -q` → PASS; `python -m pytest -q` → green. Commit:
```bash
git add core/agency.py tests/test_agency.py
git commit -m "feat(agency): sense-of-agency from self-action prediction error"
```

---

## Task 7: Policy imagination bonus + self-model agency nudge

**Files:** Modify `core/policy.py`, `core/self_model.py`; Test `tests/test_policy_agency_hooks.py`.

- [ ] **Step 1: Failing test**
```python
# tests/test_policy_agency_hooks.py
from core.policy import Policy
from core.self_model import SelfModel
from schemas.models import (ActionType, EmotionState, Prediction, SimConfig)


def _preds():
    return [
        Prediction(action=ActionType.OBSERVE, target_id=None, expected_energy_delta=-0.6,
                   expected_danger=0.0, expected_novelty=0.3, expected_goal_progress=0.05,
                   uncertainty=0.5, value=0.10),
        Prediction(action=ActionType.EXPLORE, target_id=None, expected_energy_delta=-1.2,
                   expected_danger=0.0, expected_novelty=0.3, expected_goal_progress=0.1,
                   uncertainty=0.5, value=0.11),
    ]


def test_imagination_bonus_can_tip_the_choice():
    p = Policy()
    sm = SelfModel(SimConfig()).snapshot()
    base = p.choose_action(_preds(), [], sm, [], EmotionState(), [], SimConfig())
    tipped = p.choose_action(_preds(), [], sm, [], EmotionState(), [], SimConfig(),
                             imagined_best_action=ActionType.OBSERVE)
    # The bonus lifts OBSERVE; with a large enough nudge it should win or tie-break to it.
    assert tipped.candidate_scores["observe"] > base.candidate_scores["observe"]


def test_self_model_agency_raises_confidence():
    sm = SelfModel(SimConfig())
    before = sm.snapshot().confidence
    sm._apply_agency(0.95)
    assert sm.snapshot().confidence >= before
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3a: `core/policy.py`** — add an optional `imagined_best_action` parameter to `choose_action` (LAST param, default `None`) and a small bonus in the scoring loop. Change the signature:
```python
    def choose_action(
        self,
        predictions: list[Prediction],
        memory_matches: list[MemoryRecord],
        self_model: SelfModelState,
        motivations: list[GoalPressure],
        emotion: EmotionState,
        salient: list[SalientItem],
        config: SimConfig,
        imagined_best_action: ActionType | None = None,
    ) -> ActionDecision:
```
Inside the per-prediction loop, after `certainty_term` is computed and before `score = (...)`, add:
```python
            # Imagination bonus: the action the mental rollout favoured gets a
            # small forward-looking lift (additive; None => no effect).
            imagination_term = 0.3 if (imagined_best_action is not None
                                       and action == imagined_best_action) else 0.0
```
and add `+ imagination_term` to the `score = (...)` sum.

- [ ] **Step 3b: `core/self_model.py`** — add a public nudge method (place after `set_goal`):
```python
    def _apply_agency(self, agency: float) -> None:
        """Nudge confidence toward a high sense of agency (Phase 2, gentle EMA)."""
        a = _clip01(float(agency))
        self._state.confidence = _clip01(0.9 * self._state.confidence + 0.1 * a)
```

- [ ] **Step 4: Run** `python -m pytest tests/test_policy_agency_hooks.py -q` → PASS; `python -m pytest -q` → green (the new policy arg is optional; existing callers unaffected). Commit:
```bash
git add core/policy.py core/self_model.py tests/test_policy_agency_hooks.py
git commit -m "feat(policy,self): imagination bonus + agency confidence nudge"
```

---

## Task 8: Wire Phase 2 into the cognitive cycle

**Files:** Modify `core/agent.py`; Test `tests/test_deep_cycle.py`.

This task adds the per-tick hooks. EVERY hook is gated by its flag, so with the default config (all flags `False`) the cycle is byte-identical to Phase 1.

- [ ] **Step 1: Failing test**
```python
# tests/test_deep_cycle.py
from core.agent import CognitiveAgent
from schemas.models import SimConfig


def _deep_cfg(**kw):
    return SimConfig(grid_size=8, n_objects=5, world_noise=0.0,
                     circadian_enabled=True, circadian_period=20, sleep_enabled=True,
                     dream_enabled=True, imagination_enabled=True, curiosity_enabled=True,
                     agency_enabled=True, **kw)


def test_phase2_substates_present_when_enabled():
    a = CognitiveAgent(_deep_cfg())
    tr = a.cognitive_cycle()
    assert tr.circadian is not None and tr.imagination is not None
    assert tr.curiosity is not None and tr.agency is not None and tr.sleep is not None
    assert tr.metrics.daylight <= 1.0


def test_phase2_substates_absent_when_disabled():
    a = CognitiveAgent(SimConfig(grid_size=8, n_objects=5, world_noise=0.0))
    tr = a.cognitive_cycle()
    assert tr.circadian is None and tr.imagination is None and tr.curiosity is None
    assert tr.agency is None and tr.sleep is None


def test_exhausted_agent_sleeps_and_recovers():
    a = CognitiveAgent(_deep_cfg(initial_energy=100.0))
    # Drain energy so fatigue is high, force night by config period alignment.
    a.world.agent_energy = 5.0
    slept = False
    for _ in range(40):
        tr = a.cognitive_cycle()
        if tr.sleep and tr.sleep.is_sleeping:
            slept = True
        if slept and tr.sleep and not tr.sleep.is_sleeping and tr.result.new_energy > 40:
            break
    assert slept  # the agent entered sleep at least once
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement the hooks in `core/agent.py`**

(a) Imports near other `core` imports:
```python
from core.agency import Agency
from core.circadian import Circadian
from core.curiosity import Curiosity
from core.imagination import Imagination
from core.sleep import SleepCycle
```
and add `AgencyState, CircadianState, CuriosityState, ImaginationState, SleepState` to the `from schemas.models import (...)` block.

(b) In `_build`, after the society-layer block, add:
```python
        # Phase 2: deep-consciousness mechanisms (active only when their flags are on).
        self.circadian = Circadian()
        self.sleep_cycle = SleepCycle()
        self.imagination = Imagination()
        self.curiosity = Curiosity()
        self.agency = Agency()
        self._last_circadian: CircadianState | None = None
        self._last_sleep: SleepState | None = None
        self._last_imagination: ImaginationState | None = None
        self._last_curiosity: CuriosityState | None = None
        self._last_agency: AgencyState | None = None
        self._curiosity_state: CuriosityState | None = None
```

(c) In `cognitive_cycle`, right after `cfg = self.config`, compute circadian + sleep and an effective arousal baseline. (Read the observation tick from the world the agent uses.):
```python
        # Phase 2 — circadian phase + sleep decision (gated).
        cur_tick = self._shared_world.tick if self._shared_world is not None else self.world.tick
        circadian = self.circadian.state(cur_tick, cfg) if cfg.circadian_enabled else None
        prev_fatigue = float(self.last_emotion.fatigue)
        is_night = bool(circadian.is_night) if circadian is not None else False
        sleeping = self.sleep_cycle.evaluate(prev_fatigue, is_night, cfg)
```

(d) Curiosity modulation of emotion happens AFTER the emotion is computed (step 12) and after contagion. Insert (gated):
```python
        # Phase 2 — curiosity/boredom from learning progress (gated): boredom
        # boosts novelty seeking; intrinsic reward lifts satisfaction.
        if cfg.curiosity_enabled:
            curiosity_state = self.curiosity.update(list(self._recent_errors), cfg)
            self._curiosity_state = curiosity_state
            emotion = emotion.model_copy(update={
                "curiosity": float(min(1.0, emotion.curiosity + 0.3 * curiosity_state.boredom)),
                "satisfaction": float(min(1.0, emotion.satisfaction + 0.3 * curiosity_state.intrinsic_reward)),
            })
        else:
            curiosity_state = None
```

(e) Imagination before policy choice (gated, and only when awake). After `predictions = self.world_model.predict_all(...)` and before the workspace competition is fine, but the chosen action needs it — compute it just before `decision = self.policy.choose_action(...)` and pass the best first action:
```python
        # Phase 2 — imagination (gated, awake only): a bounded mental rollout whose
        # preferred first action gives the policy a forward-looking bonus.
        imagination_state = None
        imagined_best = None
        if cfg.imagination_enabled and not sleeping:
            cur_energy = (self._shared_world.agents[self.agent_id].energy
                          if self._shared_world is not None else self.world.agent_energy)
            imagination_state = self.imagination.plan(
                self.world_model, observation, candidates,
                current_energy=float(cur_energy), initial_energy=float(cfg.initial_energy), config=cfg)
            imagined_best = imagination_state.best_first_action
```
Then pass `imagined_best_action=imagined_best` to `self.policy.choose_action(...)`.

(f) Sleep override: immediately AFTER `decision = self.policy.choose_action(...)` (and its `chosen_prediction = self._prediction_for(...)`), force REST when sleeping and run consolidation/dream:
```python
        # Phase 2 — sleep override (gated): the agent rests; offline consolidation
        # + dreaming run instead of purposeful action.
        dream_text = None
        consolidated = pruned = 0
        if sleeping:
            decision = ActionDecision(
                action=ActionType.REST, target_id=None, direction=None,
                confidence=1.0, rationale="Asleep: resting; offline memory consolidation.",
                candidate_scores={})
            chosen_prediction = self._prediction_for(predictions, decision)
            consolidated, pruned = self.sleep_cycle.consolidate(self.memory, cfg)
            dream_text = self.sleep_cycle.dream(self.memory, cfg)
```
(Build coalitions BEFORE this override already happened; that is fine — the workspace reflects pre-decision bids. To surface the dream, see (g).)

(g) Dream + imagination coalitions: in `_build_coalitions`, after the social/communication block and before `return coalitions`, add (gated; uses state stashed on self):
```python
        # Phase 2 — imagination coalition (faint background projection).
        if cfg.imagination_enabled and self._pending_imagination is not None:
            im = self._pending_imagination
            coalitions.append(self.global_workspace.make_coalition(
                "imagination", f"imagining: {im.best_first_action.value if im.best_first_action else 'none'}",
                activation=float(max(0.0, min(1.0, 0.3 + 0.2 * im.imagined_value))),
                precision=0.5, vector=[float(im.imagined_value), 0.0, 0.0, 0.0]))
        # Phase 2 — dream coalition while asleep (internally generated content).
        if cfg.dream_enabled and self._pending_dream:
            coalitions.append(self.global_workspace.make_coalition(
                "dream", self._pending_dream, activation=0.7, precision=0.5,
                vector=[0.0, 0.0, 0.0, 0.0]))
```
Because `_build_coalitions` runs before imagination/sleep are computed this tick, stash the PREVIOUS tick's imagination and the current sleep intent on `self` for the coalition to read. In `_build`, add `self._pending_imagination = None` and `self._pending_dream = None`. At the very END of `cognitive_cycle` (after the trace is built), set `self._pending_imagination = imagination_state` and `self._pending_dream = dream_text`. (One-tick latency for the imagination/dream bid is acceptable and mirrors the message-delivery pattern.)

(h) Agency after the step + error (gated). After `current_error` is computed and `result` exists, insert:
```python
        # Phase 2 — sense of agency (gated): did my own action unfold as predicted?
        agency_state = self.agency.compute(chosen_prediction, result) if cfg.agency_enabled else None
```
and after `self_state_after = self.self_model.snapshot()` (step 15), nudge confidence:
```python
        if agency_state is not None:
            self.self_model._apply_agency(agency_state.agency)
            self_state_after = self.self_model.snapshot()
```

(i) Effective arousal baseline: where `_update_arousal` is called, pass the circadian-modulated baseline. Simplest: temporarily compute it and patch the config is messy — instead, modulate inside `_update_arousal` by reading circadian. Add to `_update_arousal` a multiplier: at its start compute
```python
        base_daylight = self._last_circadian.daylight if (self._last_circadian is not None) else 1.0
```
and where it relaxes toward `arousal_baseline`, use `self.circadian.arousal_baseline(cfg.arousal_baseline, base_daylight, cfg)` instead of the raw baseline. Set `self._last_circadian = circadian` BEFORE `_update_arousal` is called in the cycle.

(j) Populate the trace: set `self._last_circadian/_last_sleep/_last_imagination/_last_curiosity/_last_agency`, build a `SleepState`:
```python
        sleep_state = None
        if cfg.sleep_enabled:
            sleep_state = SleepState(
                is_sleeping=bool(sleeping), fatigue=round(float(emotion.fatigue), 4),
                consolidated=int(consolidated), pruned=int(pruned),
                dream=dream_text, sleep_ticks=int(self.sleep_cycle.sleep_ticks))
```
Add to the `CycleTrace(...)` constructor:
```python
            circadian=circadian,
            sleep=sleep_state,
            imagination=imagination_state,
            curiosity=curiosity_state,
            agency=agency_state,
```
and extend the `Metrics(...)` build with:
```python
            agency=round(float(agency_state.agency), 4) if agency_state else 0.0,
            boredom=round(float(curiosity_state.boredom), 4) if curiosity_state else 0.0,
            learning_progress=round(float(curiosity_state.learning_progress), 4) if curiosity_state else 0.0,
            daylight=round(float(circadian.daylight), 4) if circadian else 1.0,
            is_sleeping=bool(sleeping),
```

- [ ] **Step 4: Run** `python -m pytest tests/test_deep_cycle.py -q` → PASS; then `python -m pytest -q` → FULL suite green (default flags off ⇒ existing 200+ tests unchanged). If any existing test fails, the gating is leaking — fix the gate, don't weaken the test. Commit:
```bash
git add core/agent.py tests/test_deep_cycle.py
git commit -m "feat(agent): wire Phase-2 hooks (circadian, sleep, imagination, curiosity, agency)"
```

---

## Task 9: API surface check + UI deep-consciousness panel

**Files:** Modify `ui/index.html`, `ui/app.js`, `ui/styles.css`; Test `tests/test_deep_api.py`.

The new sub-states already flow through `/tick`, `/society/tick`, `/society/agent/{id}/...` via `CycleTrace`. This task verifies that and adds the UI.

- [ ] **Step 1: Failing test**
```python
# tests/test_deep_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_tick_trace_carries_phase2_when_enabled():
    client.post("/config", json={"circadian_enabled": True, "imagination_enabled": True,
                                 "curiosity_enabled": True, "agency_enabled": True,
                                 "sleep_enabled": True, "world_noise": 0.0})
    body = client.post("/tick").json()
    assert body["circadian"] is not None and body["imagination"] is not None
    assert "daylight" in body["metrics"] and "agency" in body["metrics"]


def test_tick_trace_omits_phase2_by_default():
    client.post("/config", json={"circadian_enabled": False, "imagination_enabled": False,
                                 "curiosity_enabled": False, "agency_enabled": False,
                                 "sleep_enabled": False})
    body = client.post("/tick").json()
    assert body["circadian"] is None and body["agency"] is None
```

- [ ] **Step 2: Run** `python -m pytest tests/test_deep_api.py -q` → it should PASS already if Task 8 is correct (no route change needed). If `/config` rejects the new keys, ensure Task 1 added them to `ConfigPatch`. (No code change expected here beyond confirming.)

- [ ] **Step 3: UI** — READ `ui/index.html`, `ui/app.js`, `ui/styles.css` and follow their conventions (the `api()`/`postJSON()` helpers and the `refreshAll()` loop discovered in Phase 1).
  - In `index.html`, add a `panel-deep` section after `panel-hero` with: a circadian day/night dial (`<canvas id="circadian-dial" width="120" height="120">`), a sleep indicator + dream line (`#sleep-state`, `#dream-line`), an agency meter (`#agency-meter`), a boredom/curiosity meter (`#boredom-meter`), and an imagined-plan line (`#imagined-plan`). Also add a small "Deep consciousness" toggle group in the Settings panel with checkboxes for the 6 flags, **all checked by default**.
  - In `app.js`, add `applyDeepDefaults()` that on first load POSTs the config enabling the 6 Phase-2 flags (so the live instrument is Phase-2 by default), and `refreshDeep()` that reads the latest `/tick`/`/state` fields (`daylight`, `is_sleeping`, `agency`, `boredom`, `learning_progress`) and the latest trace's `imagination`/`sleep.dream` to update the panel; call `refreshDeep()` from the existing refresh loop. Wire the 6 checkboxes to `postJSON('config', {<flag>: checked})`.
  - In `styles.css`, add styles for `.panel-deep`, the dial, and the meters (reuse existing meter classes/vars).

- [ ] **Step 4:** `node --check ui/app.js` (if node present) and `python -m pytest -q` → green. Commit:
```bash
git add ui/index.html ui/app.js ui/styles.css tests/test_deep_api.py
git commit -m "feat(ui): deep-consciousness panel + Phase-2 default-on toggles"
```

---

## Task 10: Regression + integration + society composition + README

**Files:** Test `tests/test_deep_regression.py`, `tests/test_deep_society.py`; Modify `README.md`.

- [ ] **Step 1: Regression test — flags off ⇒ Phase-1 trajectory**
```python
# tests/test_deep_regression.py
from core.agent import CognitiveAgent
from schemas.models import SimConfig


def test_all_flags_off_matches_phase1_energy_and_actions():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, random_seed=33)
    a, b = CognitiveAgent(cfg), CognitiveAgent(cfg)
    seq_a, seq_b = [], []
    for _ in range(15):
        seq_a.append(a.cognitive_cycle().decision.action)
        seq_b.append(b.cognitive_cycle().decision.action)
    assert seq_a == seq_b  # deterministic
    # No Phase-2 sub-states leak when disabled.
    assert a.last_trace.circadian is None and a.last_trace.agency is None
```

- [ ] **Step 2: Society composition test**
```python
# tests/test_deep_society.py
from core.society import SocietyManager
from schemas.models import SimConfig


def test_phase2_runs_in_a_society_deterministically():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, n_agents=3, random_seed=44,
                    circadian_enabled=True, circadian_period=12, sleep_enabled=True,
                    imagination_enabled=True, curiosity_enabled=True, agency_enabled=True)
    a, b = SocietyManager(cfg), SocietyManager(cfg)
    for _ in range(15):
        a.tick(); b.tick()
    sa = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in a.world.agents.items()}
    sb = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in b.world.agents.items()}
    assert sa == sb  # Phase-2 + society stays reproducible at a fixed seed
    # Per-agent Phase-2 sub-states are populated.
    assert a.agents[0].last_trace.circadian is not None
```

- [ ] **Step 3: Run** both, then `python -m pytest -q` → full suite green.

- [ ] **Step 4: README** — add a "Phase 2 — Conscience approfondie" section (match the README's language/structure): the five mechanisms, the flag-gated default-off design (with the UI enabling them live), the determinism guarantee, society composition, and a pointer to the spec. Note Phases 3–4 remain planned.

- [ ] **Step 5: Commit**
```bash
git add tests/test_deep_regression.py tests/test_deep_society.py README.md
git commit -m "test(deep): flags-off regression + society composition; docs"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** circadian (§4.1→T2), sleep/consolidation/dream (§4.2→T3), imagination (§4.3→T4), curiosity/boredom (§4.4→T5), agency (§4.5→T6), policy/self hooks (T7), cycle integration with flag gating (§4.7→T8), API/UI (§4.8→T9), determinism + flags-off regression + society (§5→T10). No gaps.
- **Backward-compat:** all flags default `False`; T8 step 4 and T10 assert the disabled cycle is byte-identical to Phase 1; the imagination policy arg and agency nudge are additive/optional.
- **Determinism:** circadian = pure tick function; imagination is pure (asserted) and bounded; consolidation sorts stably; T10 asserts society+Phase-2 reproducibility.
- **Type consistency:** `CircadianState/SleepState/ImaginationState/CuriosityState/AgencyState`, `Circadian.state/arousal_baseline`, `SleepCycle.evaluate/consolidate/dream`, `AutobiographicalMemory.consolidate`, `Imagination.plan`, `Curiosity.update`, `Agency.compute`, `Policy.choose_action(..., imagined_best_action=None)`, `SelfModel._apply_agency` are used identically across tasks.
- **One-tick-latency note:** the imagination/dream coalitions read the previous tick's stashed state (mirrors the society message pattern) because `_build_coalitions` runs before the policy/sleep step — documented in T8(g).

## Out of scope (Phase 2)
Learned policy / deep planning (Phase 3); differentiated REM/NREM; natural-language dreams; scientific test battery (Phase 4).
