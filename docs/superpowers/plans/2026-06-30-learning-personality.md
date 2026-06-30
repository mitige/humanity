# Learning & Personality (Phase 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make each `CognitiveAgent` adaptive and singular via four per-agent, interpretable (tabular, no neural nets) mechanisms — learned action values, online concept formation, meta-learning of the learning rate, and divergent personalities — all flag-gated (default **off**), deterministic, grounded, and composing with the society + Phase-2 layers.

**Architecture:** Four new focused modules (`learning.py`, `concepts.py`, `meta_learning.py`, `personality.py`), small additive params on `WorldModel.update` (`lr_override`) and `Policy.choose_action` (`learned_values`), and additive flag-gated hooks in `cognitive_cycle`. New per-tick sub-states ride in `CycleTrace`/`Metrics`. Defaults off ⇒ Phases 1-2 byte-identical (the 220 tests stay green); the UI turns flags on for the live instrument.

**Tech Stack:** Python 3.11, Pydantic v2, NumPy, FastAPI, pytest, vanilla JS UI.

**Spec:** `docs/superpowers/specs/2026-06-30-humanity-learning-personality-design.md`

**Conventions:** branch `feature/learning-personality`. Run tests with `python -m pytest` (NOT bare `pytest`); the FULL suite takes ~4 min so pass a Bash timeout of 300000 ms (run targeted files first). Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Invariant after every task: `python -m pytest -q` green.

---

## Task 1: Phase-3 schemas, constants, config

**Files:** Modify `schemas/models.py`, `core/constants.py`; Test `tests/test_lp_schemas.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_lp_schemas.py
from schemas.models import LearningState, ConceptState, PersonalityState, SimConfig
from core.constants import WORKSPACE_SOURCES


def test_states_default_safely():
    assert LearningState().q_values == {} and LearningState().effective_lr == 0.2
    assert ConceptState().dominant_concept is None and ConceptState().n_concepts == 0
    assert PersonalityState().label == "nascent" and PersonalityState().caution == 0.5


def test_config_defaults_disable_phase3():
    cfg = SimConfig()
    for flag in ("learning_enabled", "concepts_enabled", "meta_learning_enabled", "personality_enabled"):
        assert getattr(cfg, flag) is False
    assert cfg.n_concepts == 6 and cfg.value_learning_rate == 0.2


def test_concept_workspace_source():
    assert "concept" in WORKSPACE_SOURCES
```

- [ ] **Step 2: run** `python -m pytest tests/test_lp_schemas.py -v` → FAIL.

- [ ] **Step 3: add models to `schemas/models.py`** (after the Phase-2 `AgencyState` block):
```python
class LearningState(BaseModel):
    """Learned action values + effective learning rate (Phase 3)."""
    q_values: dict[str, float] = Field(default_factory=dict)
    last_reward: float = 0.0
    effective_lr: float = 0.2


class ConceptState(BaseModel):
    """Online concept formation snapshot (Phase 3)."""
    dominant_concept: int | None = None
    match: float = 0.0
    n_concepts: int = 0


class PersonalityState(BaseModel):
    """Emergent personality profile (Phase 3)."""
    label: str = "nascent"
    openness: float = 0.5
    caution: float = 0.5
    novelty_seeking: float = 0.5
    vector: list[float] = Field(default_factory=list)
```

Extend `CycleTrace`:
```python
    learning: LearningState | None = None
    concept: ConceptState | None = None
    personality: PersonalityState | None = None
```
Extend `Metrics`:
```python
    effective_learning_rate: float = 0.2
    concept_match: float = 0.0
    n_concepts: int = 0
```
Append to `SimConfig` (before `ConfigPatch`):
```python
    # learning & personality (Phase 3) — default OFF => Phases-1/2-identical
    learning_enabled: bool = False
    value_learning_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    value_learning_weight: float = Field(default=0.5, ge=0.0)
    concepts_enabled: bool = False
    n_concepts: int = Field(default=6, ge=1, le=32)
    concept_lr: float = Field(default=0.2, ge=0.0, le=1.0)
    meta_learning_enabled: bool = False
    meta_lr_min: float = Field(default=0.05, ge=0.0, le=1.0)
    meta_lr_max: float = Field(default=0.6, ge=0.0, le=1.0)
    personality_enabled: bool = False
    personality_drift: float = Field(default=0.05, ge=0.0, le=1.0)
```
Append to `ConfigPatch` (plain optionals, no `Field`):
```python
    learning_enabled: bool | None = None
    value_learning_rate: float | None = None
    value_learning_weight: float | None = None
    concepts_enabled: bool | None = None
    n_concepts: int | None = None
    concept_lr: float | None = None
    meta_learning_enabled: bool | None = None
    meta_lr_min: float | None = None
    meta_lr_max: float | None = None
    personality_enabled: bool | None = None
    personality_drift: float | None = None
```

- [ ] **Step 4: `core/constants.py`** — append `"concept"` to `WORKSPACE_SOURCES` (it currently ends with `"imagination", "dream",`):
```python
WORKSPACE_SOURCES: list[str] = [
    "perception", "memory", "motivation", "prediction_error",
    "interoception", "metacognition", "communication", "social",
    "imagination", "dream", "concept",
]
```

- [ ] **Step 5: verify & commit**
```bash
python -m pytest tests/test_lp_schemas.py -q   # 3 passed
python -m pytest -q                            # green (Bash timeout 300000)
git add schemas/models.py core/constants.py tests/test_lp_schemas.py
git commit -m "feat(schemas): Phase-3 learning/personality states + default-off config"
```

---

## Task 2: PolicyLearner — `core/learning.py`

**Files:** Create `core/learning.py`; Test `tests/test_learning.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_learning.py
from core.learning import PolicyLearner


def test_q_rises_with_repeated_positive_reward():
    pl = PolicyLearner()
    for _ in range(20):
        pl.update("interact", reward=8.0, lr=0.3)
    assert pl.bonus("interact") > 0.5
    assert pl.bonus("rest") == 0.0  # untouched action stays neutral


def test_q_is_bounded_and_reward_recorded():
    pl = PolicyLearner()
    pl.update("explore", reward=1000.0, lr=1.0)
    assert -1.0 <= pl.bonus("explore") <= 1.0
    assert pl.last_reward == 1000.0
    assert pl.values()["explore"] == pl.bonus("explore")
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: implement**
```python
# core/learning.py
"""Learned action values (Phase 3): an interpretable per-action value table.

FUNCTIONAL NOTE: each action accumulates an EMA of the (normalized) reward it
yielded — a transparent Q[action] table, not a neural network. The policy adds a
small bonus for high-value actions. Bookkeeping over internal variables; no
subjective preference is implied.
"""
from __future__ import annotations

_REWARD_NORM = 10.0


class PolicyLearner:
    """Per-agent table of EMA action values updated from realized reward."""

    def __init__(self) -> None:
        self.q: dict[str, float] = {}
        self.last_reward: float = 0.0

    def update(self, action_label: str, reward: float, lr: float) -> None:
        """EMA-update Q[action] toward the normalized reward (clipped to [-1,1])."""
        self.last_reward = float(reward)
        r = float(max(-1.0, min(1.0, float(reward) / _REWARD_NORM)))
        a = float(max(0.0, min(1.0, float(lr))))
        prev = float(self.q.get(action_label, 0.0))
        self.q[action_label] = float(max(-1.0, min(1.0, prev + a * (r - prev))))

    def bonus(self, action_label: str) -> float:
        """Return the learned value of an action (0.0 if never updated)."""
        return float(self.q.get(action_label, 0.0))

    def values(self) -> dict[str, float]:
        """Return a copy of the full action-value table."""
        return {k: float(v) for k, v in self.q.items()}
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_learning.py -q     # 2 passed
python -m pytest -q                            # green
git add core/learning.py tests/test_learning.py
git commit -m "feat(learning): interpretable per-action value table"
```

---

## Task 3: ConceptFormation — `core/concepts.py`

**Files:** Create `core/concepts.py`; Test `tests/test_concepts.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_concepts.py
from core.concepts import ConceptFormation
from schemas.models import SimConfig


def _cfg(**kw):
    return SimConfig(concepts_enabled=True, n_concepts=4, concept_lr=0.2, **kw)


def test_disabled_is_neutral():
    c = ConceptFormation(SimConfig())
    st = c.observe([0.1, 0.2, 0.3], SimConfig(concepts_enabled=False))
    assert st.dominant_concept is None and st.n_concepts == 0


def test_distinct_percepts_form_distinct_concepts_then_assign():
    c = ConceptFormation(_cfg())
    a1 = c.observe([1.0, 0.0, 0.0], _cfg())   # spawns concept 0
    b1 = c.observe([0.0, 1.0, 0.0], _cfg())   # spawns concept 1 (far from 0)
    assert a1.dominant_concept == 0 and b1.dominant_concept == 1
    a2 = c.observe([0.95, 0.02, 0.0], _cfg())  # close to concept 0 -> assigned, not spawned
    assert a2.dominant_concept == 0 and a2.n_concepts == 2
    assert a2.match > 0.5


def test_capacity_caps_concept_count_and_is_deterministic():
    cfg = _cfg(n_concepts=2)
    c1, c2 = ConceptFormation(cfg), ConceptFormation(cfg)
    vecs = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0.5, 0.5, 0.5]]
    out1 = [c1.observe(v, cfg).dominant_concept for v in vecs]
    out2 = [c2.observe(v, cfg).dominant_concept for v in vecs]
    assert out1 == out2  # deterministic
    assert max(c1.n_concepts(), 0) if callable(getattr(c1, "n_concepts", None)) else True
    assert len(c1.prototypes) <= 2  # capacity respected
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: implement**
```python
# core/concepts.py
"""Online concept formation (Phase 3): emergent prototype categories.

FUNCTIONAL NOTE: percept feature vectors are clustered online into a bounded set
of prototypes (nearest-prototype assignment with a drift update; a new prototype
is spawned when nothing is close enough and capacity remains). Deterministic
(prototypes are initialised from observed percepts, never randomly). The dominant
recognized concept becomes a 'concept' workspace bid. These are learned
categories over internal features, not subjective concepts.
"""
from __future__ import annotations

import numpy as np

from schemas.models import ConceptState, SimConfig

_SPAWN_SIM_BELOW = 0.6  # spawn a new concept when the best match is weaker than this


class ConceptFormation:
    """Bounded online prototype clustering of percept feature vectors."""

    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.prototypes: list[np.ndarray] = []

    def observe(self, feature_vector, config: SimConfig) -> ConceptState:
        if not config.concepts_enabled:
            return ConceptState()
        x = np.asarray([float(v) for v in feature_vector], dtype=float)
        n = len(self.prototypes)
        if x.size == 0:
            return ConceptState(dominant_concept=None, match=0.0, n_concepts=n)
        cid, sim = self._nearest(x)
        if cid is None or (sim < _SPAWN_SIM_BELOW and n < int(config.n_concepts)):
            self.prototypes.append(x.copy())
            return ConceptState(dominant_concept=n, match=1.0, n_concepts=n + 1)
        lr = float(max(0.0, min(1.0, config.concept_lr)))
        self.prototypes[cid] = self.prototypes[cid] + lr * (x - self.prototypes[cid])
        return ConceptState(dominant_concept=int(cid), match=round(float(sim), 4), n_concepts=n)

    def _nearest(self, x: np.ndarray):
        """Return (index, similarity in [0,1]) of the closest prototype, or (None, 0)."""
        if not self.prototypes:
            return None, 0.0
        best_i, best_sim = 0, -1.0
        for i, p in enumerate(self.prototypes):
            d = float(np.linalg.norm(x - p))
            sim = 1.0 / (1.0 + d)
            if sim > best_sim:
                best_sim, best_i = sim, i
        return best_i, best_sim
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_concepts.py -q     # 3 passed
python -m pytest -q                            # green
git add core/concepts.py tests/test_concepts.py
git commit -m "feat(concepts): bounded online concept formation"
```

---

## Task 4: MetaLearner — `core/meta_learning.py`

**Files:** Create `core/meta_learning.py`; Test `tests/test_meta_learning.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_meta_learning.py
from core.meta_learning import MetaLearner
from schemas.models import SimConfig


def _cfg(**kw):
    return SimConfig(meta_learning_enabled=True, meta_lr_min=0.05, meta_lr_max=0.6, **kw)


def test_disabled_returns_base():
    assert MetaLearner().effective_lr(0.2, [0.5, 0.4, 0.3], SimConfig()) == 0.2


def test_high_falling_error_raises_rate():
    lr = MetaLearner().effective_lr(0.2, [0.8, 0.7, 0.5, 0.3, 0.2, 0.1], _cfg())
    assert lr > 0.2 and lr <= 0.6


def test_low_flat_error_lowers_rate_within_bounds():
    lr = MetaLearner().effective_lr(0.2, [0.05] * 8, _cfg())
    assert 0.05 <= lr < 0.2
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: implement**
```python
# core/meta_learning.py
"""Meta-learning (Phase 3): the agent adapts its own learning rate.

FUNCTIONAL NOTE: when recent prediction error is high and falling, learning is
productive, so the effective rate rises; when error is low and flat (already
learned), it falls. A bounded, deterministic function of the error history — no
subjective metacognition is implied.
"""
from __future__ import annotations

from schemas.models import SimConfig


class MetaLearner:
    """Computes a bounded effective learning rate from recent error dynamics."""

    def effective_lr(self, base_lr: float, recent_errors: list[float], config: SimConfig) -> float:
        if not config.meta_learning_enabled or len(recent_errors) < 3:
            return float(base_lr)
        errs = [float(e) for e in list(recent_errors)[-8:]]
        mean_err = sum(errs) / len(errs)
        half = max(1, len(errs) // 2)
        early = sum(errs[:half]) / half
        late = sum(errs[half:]) / max(1, len(errs) - half)
        trend = early - late  # > 0 => error is falling (improving)
        raise_term = max(0.0, trend) * mean_err          # productive learning
        lower_term = (1.0 - mean_err) * 0.3              # settled => ease off
        factor = 1.0 + 3.0 * raise_term - lower_term
        lr = float(base_lr) * factor
        return float(max(float(config.meta_lr_min), min(float(config.meta_lr_max), lr)))
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_meta_learning.py -q   # 3 passed
python -m pytest -q                               # green
git add core/meta_learning.py tests/test_meta_learning.py
git commit -m "feat(meta): adaptive learning-rate from error dynamics"
```

---

## Task 5: PersonalityModel — `core/personality.py`

**Files:** Create `core/personality.py`; Test `tests/test_personality.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_personality.py
from core.personality import PersonalityModel
from schemas.models import EmotionState


def test_novelty_drives_openness_and_label():
    p = PersonalityModel()
    for _ in range(30):
        st = p.update(novelty_experienced=1.0, danger_experienced=0.0, drift=0.3)
    assert st.novelty_seeking > 0.7 and st.openness > 0.6
    assert "explor" in st.label.lower() or "audac" in st.label.lower()


def test_danger_drives_caution():
    p = PersonalityModel()
    for _ in range(30):
        st = p.update(novelty_experienced=0.0, danger_experienced=1.0, drift=0.3)
    assert st.caution > 0.7 and "prudent" in st.label.lower()


def test_modulate_is_bounded_and_shifts_affect():
    p = PersonalityModel()
    for _ in range(30):
        p.update(novelty_experienced=0.0, danger_experienced=1.0, drift=0.3)  # cautious
    out = p.modulate(EmotionState(fear=0.4, curiosity=0.4))
    assert 0.0 <= out.fear <= 1.0 and out.fear >= 0.4  # caution lifts baseline fear


def test_two_histories_diverge():
    bold, timid = PersonalityModel(), PersonalityModel()
    for _ in range(30):
        bold.update(novelty_experienced=1.0, danger_experienced=0.0, drift=0.3)
        timid.update(novelty_experienced=0.0, danger_experienced=1.0, drift=0.3)
    assert bold.update(0.5, 0.5, 0.0).label != timid.update(0.5, 0.5, 0.0).label
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: implement**
```python
# core/personality.py
"""Emergent personality (Phase 3): a stable profile that diverges with experience.

FUNCTIONAL NOTE: three bounded traits drift (EMA) with what the agent lives —
novelty_seeking toward experienced novelty, caution toward experienced danger,
openness derived from their balance. A label names the dominant trait, and a
bounded affect bias is applied so agents with different histories behave
differently. Aggregate bookkeeping over the agent's own variables; no character
or subjectivity is implied.
"""
from __future__ import annotations


def _clip01(v: float) -> float:
    return float(min(1.0, max(0.0, v)))


class PersonalityModel:
    """Per-agent emergent personality profile + affect modulation."""

    def __init__(self) -> None:
        self.novelty_seeking: float = 0.5
        self.caution: float = 0.5
        self.openness: float = 0.5

    def update(self, novelty_experienced: float, danger_experienced: float, drift: float):
        from schemas.models import PersonalityState
        a = _clip01(float(drift))
        self.novelty_seeking = _clip01((1.0 - a) * self.novelty_seeking + a * _clip01(novelty_experienced))
        self.caution = _clip01((1.0 - a) * self.caution + a * _clip01(danger_experienced))
        self.openness = _clip01(0.5 + 0.5 * (self.novelty_seeking - self.caution))
        return PersonalityState(
            label=self._label(), openness=round(self.openness, 4),
            caution=round(self.caution, 4), novelty_seeking=round(self.novelty_seeking, 4),
            vector=[round(self.openness, 4), round(self.caution, 4), round(self.novelty_seeking, 4)],
        )

    def _label(self) -> str:
        if self.caution > 0.6 and self.novelty_seeking > 0.6:
            return "prudent curieux"
        if self.caution > 0.6:
            return "prudent"
        if self.novelty_seeking > 0.6 or self.openness > 0.6:
            return "explorateur audacieux"
        return "équilibré"

    def modulate(self, emotion):
        """Apply a small, bounded personality bias to baseline affect."""
        return emotion.model_copy(update={
            "curiosity": _clip01(emotion.curiosity + 0.2 * (self.openness - 0.5)),
            "fear": _clip01(emotion.fear + 0.2 * (self.caution - 0.5)),
        })
```

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_personality.py -q   # 4 passed
python -m pytest -q                             # green
git add core/personality.py tests/test_personality.py
git commit -m "feat(personality): emergent divergent personality profiles"
```

---

## Task 6: WorldModel `lr_override` + Policy `learned_values`

**Files:** Modify `core/world_model.py`, `core/policy.py`; Test `tests/test_lp_hooks.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_lp_hooks.py
from core.world_model import WorldModel
from core.policy import Policy
from core.self_model import SelfModel
from schemas.models import (ActionType, EmotionState, Observation, Prediction, SimConfig, StepResult)


def _result(e, g):
    return StepResult(tick=1, action=ActionType.INTERACT, target_id=None, energy_delta=e,
                      new_energy=50.0, events=[], actual={"danger": 0.0, "novelty": 0.0, "goal_progress": g})


def test_world_model_lr_override_changes_update_magnitude():
    obs = Observation(tick=0, agent_x=0, agent_y=0, agent_energy=50.0, radius=3, visible=[])
    slow = WorldModel(SimConfig(learning_rate=0.2)); fast = WorldModel(SimConfig(learning_rate=0.2))
    pred = slow.predict(obs, ActionType.INTERACT, None)
    res = _result(9.0, 0.5)
    slow.update(pred, res)                      # base lr 0.2
    fast.update(pred, res, lr_override=0.9)     # overridden lr
    sb = slow.beliefs["interact"]["energy_delta"]; fb = fast.beliefs["interact"]["energy_delta"]
    assert abs(fb - 9.0) < abs(sb - 9.0)       # higher lr moved the belief closer to observed


def test_policy_learned_values_bonus_lifts_action():
    p = Policy()
    sm = SelfModel(SimConfig()).snapshot()
    preds = [Prediction(action=ActionType.OBSERVE, target_id=None, expected_energy_delta=-0.6,
                        expected_danger=0.0, expected_novelty=0.3, expected_goal_progress=0.05,
                        uncertainty=0.5, value=0.1)]
    base = p.choose_action(preds, [], sm, [], EmotionState(), [], SimConfig())
    lifted = p.choose_action(preds, [], sm, [], EmotionState(), [], SimConfig(value_learning_weight=1.0),
                             learned_values={"observe": 0.9})
    assert lifted.candidate_scores["observe"] > base.candidate_scores["observe"]
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3a: `core/world_model.py`** — add `lr_override` to `update`. Change the signature
`def update(self, prediction: Prediction, result: StepResult) -> None:` to:
```python
    def update(self, prediction: Prediction, result: StepResult, lr_override: float | None = None) -> None:
```
and change the line `lr = float(self.config.learning_rate)` to:
```python
        lr = float(self.config.learning_rate if lr_override is None else lr_override)
        lr = float(max(0.0, min(1.0, lr)))
```

- [ ] **Step 3b: `core/policy.py`** — add `learned_values` as the LAST parameter of `choose_action`:
```python
        config: SimConfig,
        imagined_best_action: ActionType | None = None,
        learned_values: dict[str, float] | None = None,
    ) -> ActionDecision:
```
In the per-prediction loop, after the `imagination_term` line and before the `score = (...)` assignment, add:
```python
            # Learned-value bonus: the action's learned Q value (additive; None => 0).
            learned_term = (float(config.value_learning_weight) * float(learned_values.get(label, 0.0))
                            if learned_values else 0.0)
```
and add `+ learned_term` to the `score = (...)` summation.

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_lp_hooks.py -q   # 2 passed
python -m pytest -q                          # green (both new params optional => existing callers unaffected)
git add core/world_model.py core/policy.py tests/test_lp_hooks.py
git commit -m "feat(world,policy): optional lr_override + learned-value bonus"
```

---

## Task 7: Wire Phase-3 into the cognitive cycle

**Files:** Modify `core/agent.py`; Test `tests/test_lp_cycle.py`.

All hooks are flag-gated; with all Phase-3 flags off the cycle is byte-identical (the 220+ existing tests stay green).

- [ ] **Step 1: failing test**
```python
# tests/test_lp_cycle.py
from core.agent import CognitiveAgent
from schemas.models import SimConfig


def _cfg(**kw):
    return SimConfig(grid_size=8, n_objects=5, world_noise=0.0, learning_enabled=True,
                     concepts_enabled=True, meta_learning_enabled=True, personality_enabled=True, **kw)


def test_phase3_substates_present_when_enabled():
    a = CognitiveAgent(_cfg())
    tr = a.cognitive_cycle()
    assert tr.learning is not None and tr.concept is not None and tr.personality is not None
    assert "effective_learning_rate" in tr.metrics.model_dump()


def test_phase3_substates_absent_when_disabled():
    a = CognitiveAgent(SimConfig(grid_size=8, n_objects=5, world_noise=0.0))
    tr = a.cognitive_cycle()
    assert tr.learning is None and tr.concept is None and tr.personality is None


def test_learned_value_grows_over_time():
    a = CognitiveAgent(_cfg(initial_energy=100.0))
    for _ in range(20):
        a.cognitive_cycle()
    assert a.policy_learner.values()  # non-empty learned table after acting
```

- [ ] **Step 2: run** → FAIL.

- [ ] **Step 3: edits to `core/agent.py`**

(a) Imports near other `core` imports:
```python
from core.concepts import ConceptFormation
from core.learning import PolicyLearner
from core.meta_learning import MetaLearner
from core.personality import PersonalityModel
```
and add `ConceptState, LearningState, PersonalityState` to the `from schemas.models import (...)` block.

(b) In `_build`, after the Phase-2 block, add:
```python
        # Phase 3: learning & personality (active only when their flags are on).
        self.policy_learner = PolicyLearner()
        self.concepts = ConceptFormation(config)
        self.meta_learner = MetaLearner()
        self.personality = PersonalityModel()
        self._concept_state: ConceptState | None = None
```

(c) In `cognitive_cycle`, AFTER percepts are computed (step 2) and BEFORE `# 6b) BUILD COALITIONS`, compute the concept state (gated):
```python
        # Phase 3 — concept formation (gated): cluster a normalized percept feature
        # vector into emergent prototypes; the dominant concept bids in the workspace.
        concept_state = None
        if cfg.concepts_enabled:
            if percepts:
                import numpy as _np
                cvec = [
                    float(_np.mean([p.danger for p in percepts])),
                    float(_np.mean([p.novelty for p in percepts])),
                    float(_np.mean([p.utility for p in percepts])),
                    float(min(1.0, _np.mean([p.energy_value for p in percepts]) / 10.0)),
                    float(min(1.0, _np.mean([p.distance for p in percepts]) / max(1, cfg.grid_size))),
                ]
            else:
                cvec = []
            concept_state = self.concepts.observe(cvec, cfg)
        self._concept_state = concept_state
```

(d) Meta-learning effective rate — compute just before `# 11)`'s `self.world_model.update(...)` call. Find `current_error = self.world_model.compute_error(...)` (step 11) and AFTER it (after any surprise hook, before `self.world_model.update(chosen_prediction, result)`), add:
```python
        # Phase 3 — meta-learning (gated): adapt the effective learning rate.
        effective_lr = float(cfg.learning_rate)
        if cfg.meta_learning_enabled:
            effective_lr = self.meta_learner.effective_lr(cfg.learning_rate, list(self._recent_errors), cfg)
```
Then change the update call `self.world_model.update(chosen_prediction, result)` to:
```python
        self.world_model.update(chosen_prediction, result,
                                lr_override=(effective_lr if cfg.meta_learning_enabled else None))
```

(e) Learned-value policy bonus — pass the learned table to the policy. Find the `decision = self.policy.choose_action(...)` call and add the kwarg:
```python
            learned_values=(self.policy_learner.values() if cfg.learning_enabled else None),
```
(Keep the existing `imagined_best_action=...` kwarg from Phase 2.)

(f) PolicyLearner update — AFTER the world step + error (after `result` exists; place it right after the meta-learning/world_model.update block), add:
```python
        # Phase 3 — learn the value of the action just taken (gated).
        if cfg.learning_enabled:
            reward = float(result.energy_delta) + float(result.actual.get("goal_progress", 0.0))
            self.policy_learner.update(decision.action.value, reward,
                                       lr=(effective_lr if cfg.meta_learning_enabled else cfg.value_learning_rate))
```

(g) Personality — AFTER the emotion update + Phase-2 contagion/curiosity modulation, add (gated):
```python
        # Phase 3 — personality (gated): drift traits with lived experience, then
        # apply a bounded affect bias so divergent histories yield divergent agents.
        personality_state = None
        if cfg.personality_enabled:
            personality_state = self.personality.update(
                novelty_experienced=float(result.actual.get("novelty", 0.0)),
                danger_experienced=float(result.actual.get("danger", 0.0)),
                drift=float(cfg.personality_drift))
            emotion = self.personality.modulate(emotion)
```

(h) Build the `concept` coalition. In `_build_coalitions`, after the Phase-2 imagination/dream block and before `return coalitions`, add:
```python
        # Phase 3 — concept coalition: the dominant recognized concept (gated).
        if cfg.concepts_enabled and self._concept_state is not None \
                and self._concept_state.dominant_concept is not None:
            cs = self._concept_state
            coalitions.append(self.global_workspace.make_coalition(
                "concept", f"concept #{cs.dominant_concept}",
                activation=float(max(0.0, min(1.0, cs.match))), precision=0.6,
                vector=[float(cs.match), 0.0, 0.0, 0.0]))
```

(i) Build `learning_state` and extend trace + metrics. Just before the `trace = CycleTrace(...)` build, add:
```python
        learning_state = None
        if cfg.learning_enabled or cfg.meta_learning_enabled:
            learning_state = LearningState(
                q_values=self.policy_learner.values(),
                last_reward=round(float(self.policy_learner.last_reward), 4),
                effective_lr=round(float(effective_lr), 6))
```
Add to the `CycleTrace(...)` constructor:
```python
            learning=learning_state,
            concept=concept_state,
            personality=personality_state,
```
Add to the `Metrics(...)` constructor:
```python
            effective_learning_rate=round(float(effective_lr), 6),
            concept_match=round(float(concept_state.match), 4) if concept_state else 0.0,
            n_concepts=int(concept_state.n_concepts) if concept_state else 0,
```

(j) Ensure every new local (`concept_state`, `effective_lr`, `personality_state`, `learning_state`) is defined on all paths (initialise to None / `cfg.learning_rate` as shown) before it is read.

- [ ] **Step 4: verify & commit**
```bash
python -m pytest tests/test_lp_cycle.py -q   # 3 passed
python -m pytest -q                          # FULL suite green (flags off => unchanged)
git add core/agent.py tests/test_lp_cycle.py
git commit -m "feat(agent): wire Phase-3 hooks (learning, concepts, meta, personality)"
```

---

## Task 8: API check + learning/personality UI

**Files:** Modify `ui/index.html`, `ui/app.js`, `ui/styles.css`; Test `tests/test_lp_api.py`.

- [ ] **Step 1: failing test**
```python
# tests/test_lp_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_tick_carries_phase3_when_enabled():
    client.post("/config", json={"learning_enabled": True, "concepts_enabled": True,
                                 "meta_learning_enabled": True, "personality_enabled": True,
                                 "world_noise": 0.0})
    body = client.post("/tick").json()
    assert body["learning"] is not None and body["personality"] is not None
    assert "effective_learning_rate" in body["metrics"]


def test_tick_omits_phase3_by_default():
    client.post("/config", json={"learning_enabled": False, "concepts_enabled": False,
                                 "meta_learning_enabled": False, "personality_enabled": False})
    body = client.post("/tick").json()
    assert body["learning"] is None and body["personality"] is None
```

- [ ] **Step 2: run** `python -m pytest tests/test_lp_api.py -q` → should PASS already (Task 7 wired the trace; routes/ConfigPatch already accept the keys). If a `/config` key is rejected, fix Task 1's `ConfigPatch`.

- [ ] **Step 3: UI** — READ `ui/index.html`, `ui/app.js`, `ui/styles.css`; follow the existing `api()`/`postJSON()` helpers and the `refreshAll()` loop (and the Phase-2 `lastTrace` global already added). Add:
  - `index.html`: a `panel-learning` section (after `panel-deep`) with: learned-value bars (`#q-bars`), dominant concept (`#concept-state`), effective learning rate (`#elr-val`), and a **personality card** (`#personality-label`, `#personality-traits`). Add the 4 Phase-3 toggles (`data-flag` = `learning_enabled, concepts_enabled, meta_learning_enabled, personality_enabled`) to the Settings toggles, checked by default.
  - `app.js`: extend `applyDeepDefaults()` (or add `applyLearningDefaults()`) to also POST the 4 Phase-3 flags `true` on load; add `refreshLearning(trace)` that renders `trace.learning.q_values` as bars, `trace.concept`, `trace.metrics.effective_learning_rate`, and `trace.personality.{label,vector}`; call it from the refresh loop (guarded). Wire the 4 toggles to `postJSON('config', {<flag>: checked})`.
  - `styles.css`: styles for `.panel-learning`, `#q-bars`, `.personality-card`, reusing existing classes/vars.

- [ ] **Step 4:** `node --check ui/app.js` (if node present); `python -m pytest -q` → green. Commit:
```bash
git add ui/index.html ui/app.js ui/styles.css tests/test_lp_api.py
git commit -m "feat(ui): learning & personality panel + Phase-3 default-on toggles"
```

---

## Task 9: Regression — flags off ⇒ Phases-1/2 identical

**Files:** Test `tests/test_lp_regression.py`.

- [ ] **Step 1: test**
```python
# tests/test_lp_regression.py
from core.agent import CognitiveAgent
from schemas.models import SimConfig


def test_all_phase3_flags_off_is_deterministic_and_clean():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, random_seed=55)
    a, b = CognitiveAgent(cfg), CognitiveAgent(cfg)
    sa = [a.cognitive_cycle().decision.action for _ in range(15)]
    sb = [b.cognitive_cycle().decision.action for _ in range(15)]
    assert sa == sb
    assert a.last_trace.learning is None and a.last_trace.personality is None
    assert a.last_trace.concept is None
```

- [ ] **Step 2: run** both targeted and full (`python -m pytest -q`, Bash timeout 300000) → green. Commit:
```bash
git add tests/test_lp_regression.py
git commit -m "test(lp): flags-off regression stays Phases-1/2 identical"
```

---

## Task 10: Society — divergent personalities + README

**Files:** Test `tests/test_lp_society.py`; Modify `README.md`.

- [ ] **Step 1: test**
```python
# tests/test_lp_society.py
from core.society import SocietyManager
from schemas.models import SimConfig


def test_phase3_society_is_deterministic_and_learns():
    cfg = SimConfig(grid_size=10, n_objects=10, world_noise=0.0, n_agents=3, random_seed=77,
                    learning_enabled=True, concepts_enabled=True, meta_learning_enabled=True,
                    personality_enabled=True)
    a, b = SocietyManager(cfg), SocietyManager(cfg)
    for _ in range(25):
        a.tick(); b.tick()
    sa = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in a.world.agents.items()}
    sb = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in b.world.agents.items()}
    assert sa == sb  # reproducible at a fixed seed
    # Agents have learned and formed a personality.
    assert a.agents[0].last_trace.personality is not None
    assert any(ag.policy_learner.values() for ag in a.agents.values())
```

- [ ] **Step 2: run** targeted + full → green.

- [ ] **Step 3: README** — add a **"Phase 3 — Apprentissage & personnalité"** section (French, matching style): the four mechanisms; interpretable/tabular & no-NN; flag-gated default-off in `SimConfig` / on in the UI; config keys (`learning_enabled/value_learning_rate/value_learning_weight, concepts_enabled/n_concepts/concept_lr, meta_learning_enabled/meta_lr_min/meta_lr_max, personality_enabled/personality_drift`); new trace/metrics fields (`learning, concept, personality`; `effective_learning_rate, concept_match, n_concepts`); society note (agents develop distinct personalities from distinct experience); spec pointer; mark Phase 3 delivered, Phase 4 remaining.

- [ ] **Step 4: commit**
```bash
git add tests/test_lp_society.py README.md
git commit -m "test(lp): society determinism + divergent personalities; docs"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** learned policy (§4.1→T2,T6,T7), concepts (§4.2→T3,T7), meta-learning (§4.3→T4,T7), personality (§4.4→T5,T7), schemas/config (§4.5→T1), API/UI (§4.6→T8), determinism + flags-off regression (§5→T9), society divergence (§7→T10). No gaps.
- **Backward-compat:** all flags default False; T7 and T9 assert disabled cycle is unchanged; `lr_override`/`learned_values`/policy `imagined_best_action` are additive optionals.
- **Determinism:** Q-EMA, prototypes init-from-percepts (no random), meta-lr from error history, bounded personality drift; T10 asserts society reproducibility.
- **Type consistency:** `PolicyLearner.update/bonus/values`, `ConceptFormation.observe/_nearest/prototypes`, `MetaLearner.effective_lr`, `PersonalityModel.update/modulate`, `WorldModel.update(..., lr_override=None)`, `Policy.choose_action(..., learned_values=None)`, `LearningState/ConceptState/PersonalityState` used identically across tasks.
- **Concept-coalition timing:** concept_state is computed at step 2 (before `_build_coalitions`), so the `concept` bid is current-tick (no latency), unlike Phase-2 imagination/dream.

## Out of scope (Phase 3)
Neural nets / deep RL; full-state Q-learning; social/cultural learning between agents; the consciousness test battery (Phase 4).
