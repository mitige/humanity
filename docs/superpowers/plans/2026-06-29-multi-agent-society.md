# Multi-Agent Society (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the single-agent `Humanity` instrument into a deterministic, LLM-free *society* of cognitive agents that share a world, perceive each other, communicate, model each other's minds (theory of mind), and influence each other affectively — while keeping the existing single-agent API/UI/tests working unchanged.

**Architecture:** A new `SharedWorld` hosts N agents + shared objects + spatial messages. A `MessageBus` delivers `VERBALIZE` utterances one tick later. Each `CognitiveAgent` gains an `agent_id` and additive social hooks that produce two new global-workspace coalitions (`communication`, `social`) plus emotional contagion and reputation. A `SocietyManager` orchestrates deterministic round-robin ticks and exposes `/society/*` endpoints (REST + WebSocket). The legacy `SimulationManager` becomes a thin "society of 1" façade so `/agent/*` and all current tests are byte-for-byte compatible.

**Tech Stack:** Python 3.11, Pydantic v2, NumPy, FastAPI, pytest, vanilla JS UI (no new deps).

**Spec:** `docs/superpowers/specs/2026-06-29-humanity-multi-agent-society-design.md`

**Guiding rules:** Sans LLM · déterministe (seed par agent) · additif & rétrocompatible · réutilise le cycle cognitif. Every new text output stays grounded in internal variables and carries no claim of lived experience.

---

## File Structure

**Create:**
- `core/shared_world.py` — multi-agent grid world (objects + agents + messages)
- `core/communication.py` — `MessageBus`, deferred one-tick delivery
- `core/theory_of_mind.py` — `TheoryOfMind`, per-agent models of others
- `core/social_emotion.py` — emotional contagion + reputation/trust
- `core/society.py` — `SocietyManager` orchestration + façade
- `tests/test_shared_world.py`, `tests/test_communication.py`, `tests/test_theory_of_mind.py`, `tests/test_social_emotion.py`, `tests/test_society.py`, `tests/test_society_api.py`, `tests/test_backward_compat.py`

**Modify:**
- `schemas/models.py` — new models + field extensions (all defaulted)
- `core/constants.py` — extend `WORKSPACE_SOURCES`, add social constants
- `core/motivation.py` — add `affiliate` need
- `core/agent.py` — `agent_id`, social hooks, new coalitions, `trace.social`
- `app/api/routes.py` — `/society/*` endpoints + WebSocket
- `ui/index.html`, `ui/app.js`, `ui/styles.css` — society view

**Invariant after every task:** `pytest -q` is green (existing + new tests).

---

## Task 1: Social schemas

**Files:**
- Modify: `schemas/models.py`
- Test: `tests/test_social_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_social_schemas.py
from schemas.models import (
    AgentView, Message, OtherMind, SocialState, Observation, CycleTrace, SimConfig,
)


def test_social_models_have_safe_defaults():
    av = AgentView(id=2, x=1, y=1, distance=2.0)
    assert av.last_action is None and av.dominant_affect == "neutral" and av.valence == 0.0

    msg = Message(id=1, tick_emitted=3, sender_id=0, content="hi", x=4, y=4, radius=4, ttl=2)
    assert msg.vector == [] and msg.sender_id == 0

    om = OtherMind(agent_id=1)
    assert om.trust == 0.5 and om.familiarity == 0.0 and om.inferred_action is None

    ss = SocialState(agent_id=0)
    assert ss.others == [] and ss.affiliation_pressure == 0.0 and ss.received_count == 0


def test_observation_and_config_extensions_default_empty():
    obs = Observation(tick=0, agent_x=0, agent_y=0, agent_energy=10.0, radius=3, visible=[])
    assert obs.visible_agents == [] and obs.audible_messages == []
    cfg = SimConfig()
    assert cfg.n_agents == 1 and cfg.comm_radius == 4 and cfg.message_ttl == 2
    assert cfg.contagion_rate == 0.15 and cfg.affiliation_drive == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_social_schemas.py -v`
Expected: FAIL with `ImportError` / `AttributeError` (models/fields not defined).

- [ ] **Step 3: Add the models and extensions**

In `schemas/models.py`, add these classes after `WorldObject`:

```python
class AgentView(BaseModel):
    """Another agent as perceived by an observer (grounded social percept)."""
    id: int
    x: int
    y: int
    distance: float
    last_action: ActionType | None = None
    dominant_affect: str = "neutral"   # label of the other's strongest functional affect
    valence: float = 0.0               # other's published mood in [-1, 1]


class Message(BaseModel):
    """A grounded utterance emitted by a VERBALIZE action; delivered next tick."""
    id: int
    tick_emitted: int
    sender_id: int
    content: str                       # grounded summary of the sender's ConsciousMoment
    vector: list[float] = Field(default_factory=list)  # small affect/feature summary
    x: int
    y: int
    radius: int                        # earshot radius from the emission point
    ttl: int                           # ticks the message stays deliverable


class OtherMind(BaseModel):
    """One agent's functional model of another agent (theory of mind, ToM)."""
    agent_id: int
    inferred_action: ActionType | None = None
    inferred_affect: str = "neutral"
    inferred_valence: float = 0.0      # -1..1
    trust: float = 0.5                 # 0..1 reputation/confidence
    familiarity: float = 0.0           # 0..1 grows with exposure
    last_seen_tick: int = -1
    note: str = ""


class SocialState(BaseModel):
    """An agent's social snapshot for the trace/UI."""
    agent_id: int
    others: list[OtherMind] = Field(default_factory=list)
    affiliation_pressure: float = 0.0
    last_emitted: str | None = None
    received_count: int = 0
```

In the existing `Observation` class add two fields:

```python
    visible_agents: list[AgentView] = Field(default_factory=list)
    audible_messages: list["Message"] = Field(default_factory=list)
```

In the existing `CycleTrace` class add:

```python
    social: SocialState | None = None
```

In the existing `SimConfig` class, add to the bottom (before `ConfigPatch`):

```python
    # society (multi-agent, v3)
    n_agents: int = 1                    # 1 => exact legacy single-agent behaviour
    comm_radius: int = 4                 # earshot radius for VERBALIZE messages
    message_ttl: int = 2                 # ticks a message stays deliverable
    contagion_rate: float = 0.15         # EMA weight of others' affect on one's own
    affiliation_drive: float = 1.0       # scales the 'affiliate' goal pressure
    social_seed_stride: int = 1000       # per-agent RNG seed = seed + index*stride
```

In `ConfigPatch`, add the same six fields with `| None = None`:

```python
    n_agents: int | None = None
    comm_radius: int | None = None
    message_ttl: int | None = None
    contagion_rate: float | None = None
    affiliation_drive: float | None = None
    social_seed_stride: int | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_social_schemas.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify no regression & commit**

Run: `pytest -q`
Expected: all existing tests still pass.

```bash
git add schemas/models.py tests/test_social_schemas.py
git commit -m "feat(schemas): add social models and defaulted society config fields"
```

---

## Task 2: Constants — workspace sources & social tuning

**Files:**
- Modify: `core/constants.py`
- Test: `tests/test_social_constants.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_social_constants.py
from core.constants import (
    WORKSPACE_SOURCES, CONTAGION_EMA, TRUST_EMA, FAMILIARITY_EMA,
)


def test_social_sources_registered():
    assert "communication" in WORKSPACE_SOURCES
    assert "social" in WORKSPACE_SOURCES


def test_social_emas_in_unit_range():
    for v in (CONTAGION_EMA, TRUST_EMA, FAMILIARITY_EMA):
        assert 0.0 < v <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_social_constants.py -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Extend constants**

In `core/constants.py`, replace the `WORKSPACE_SOURCES` line with:

```python
WORKSPACE_SOURCES: list[str] = [
    "perception", "memory", "motivation", "prediction_error",
    "interoception", "metacognition", "communication", "social",
]
```

Add at the end of the file:

```python
# === Society (multi-agent, v3) ===
# Smoothing weights for the social layer (bounded EMA updates).
CONTAGION_EMA: float = 0.15     # default; SimConfig.contagion_rate overrides per run
TRUST_EMA: float = 0.25         # how fast reputation moves toward observed reward sign
FAMILIARITY_EMA: float = 0.30   # how fast familiarity saturates with exposure
SOCIAL_PERCEPT_NORM: float = 1.0  # reserved scale for social salience normalization
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_social_constants.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/constants.py tests/test_social_constants.py
git commit -m "feat(constants): register communication/social workspace sources + social EMAs"
```

---

## Task 3: SharedWorld — multi-agent grid

**Files:**
- Create: `core/shared_world.py`
- Test: `tests/test_shared_world.py`

The `SharedWorld` reuses the action-effect constants from `core/constants.py` and the same object dynamics as `core/world.py`, but tracks multiple agent bodies and a message pool. `World` (single-agent) stays untouched.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_shared_world.py
from core.shared_world import SharedWorld
from schemas.models import ActionDecision, ActionType, SimConfig


def _cfg(**kw):
    return SimConfig(grid_size=8, n_objects=4, world_noise=0.0, perception_radius=3,
                     n_agents=3, random_seed=7, **kw)


def test_agents_spawn_distinct_and_observable():
    w = SharedWorld(_cfg())
    assert set(w.agents.keys()) == {0, 1, 2}
    # Each agent observes itself at its own coordinates.
    obs0 = w.observe(0)
    assert obs0.agent_x == w.agents[0].x and obs0.agent_y == w.agents[0].y


def test_observe_lists_other_agents_within_radius_only():
    w = SharedWorld(_cfg())
    # Force agent 1 next to agent 0, agent 2 far away.
    w.agents[0].x, w.agents[0].y = 4, 4
    w.agents[1].x, w.agents[1].y = 5, 4
    w.agents[2].x, w.agents[2].y = 0, 0
    seen = {a.id for a in w.observe(0).visible_agents}
    assert 1 in seen and 2 not in seen and 0 not in seen  # never sees itself


def test_step_moves_only_the_acting_agent():
    w = SharedWorld(_cfg())
    before = (w.agents[2].x, w.agents[2].y)
    dec = ActionDecision(action=ActionType.MOVE, target_id=None, direction=[1, 0],
                         confidence=1.0, rationale="t", candidate_scores={})
    w.step(0, dec)
    assert (w.agents[2].x, w.agents[2].y) == before  # agent 2 unaffected


def test_determinism_same_seed_same_layout():
    a = SharedWorld(_cfg())
    b = SharedWorld(_cfg())
    assert [(o.id, o.x, o.y, o.kind) for o in a.objects.values()] == \
           [(o.id, o.x, o.y, o.kind) for o in b.objects.values()]
    assert {i: (bd.x, bd.y) for i, bd in a.agents.items()} == \
           {i: (bd.x, bd.y) for i, bd in b.agents.items()}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_shared_world.py -v`
Expected: FAIL with `ModuleNotFoundError: core.shared_world`.

- [ ] **Step 3: Implement `SharedWorld`**

```python
# core/shared_world.py
"""Deterministic multi-agent grid world for Humanity's society layer.

FUNCTIONAL NOTE: like core/world.py this is a plain dynamics simulator. It hosts
several agent bodies, shared objects, and a pool of spatial messages. Nothing
here is conscious; it is the shared environment the simulated agents inhabit.
"""
from __future__ import annotations

import numpy as np

from core.constants import (
    ACTION_COSTS, ENERGY_CAP_FACTOR, INTERACT_DANGER_DAMAGE,
    NOVELTY_DECAY_ON_INTERACT, NOVELTY_DECAY_ON_SEE, PASSIVE_ENERGY_DECAY,
    REST_RECOVERY,
)
from schemas.models import (
    ActionDecision, ActionType, AgentView, Message, Observation, SimConfig,
    StepResult, WorldObject,
)

_MOVEMENT_ACTIONS = {ActionType.MOVE, ActionType.EXPLORE, ActionType.APPROACH, ActionType.AVOID}


class AgentBody:
    """Physical state of one agent in the shared world (position + published signal)."""

    def __init__(self, agent_id: int, x: int, y: int, energy: float) -> None:
        self.id = agent_id
        self.x = x
        self.y = y
        self.energy = float(energy)
        self.last_action: ActionType | None = None
        self.dominant_affect: str = "neutral"
        self.valence: float = 0.0

    def publish(self, last_action, dominant_affect, valence) -> None:
        self.last_action = last_action
        self.dominant_affect = str(dominant_affect)
        self.valence = float(valence)


class SharedWorld:
    """Seeded 2D grid hosting N agents, shared objects and spatial messages."""

    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self._build()

    # ----------------------------------------------------------------- setup
    def _build(self) -> None:
        cfg = self.config
        self.rng = np.random.default_rng(cfg.random_seed)
        self.tick: int = 0
        self.objects: dict[int, WorldObject] = {}
        self.seen_counts: dict[int, int] = {}
        self._next_id: int = 0
        for _ in range(cfg.n_objects):
            self._spawn_object()
        # Agents placed deterministically near the centre on distinct cells.
        self.agents: dict[int, AgentBody] = {}
        center = cfg.grid_size // 2
        used: set[tuple[int, int]] = set()
        for idx in range(max(1, int(cfg.n_agents))):
            x = int(np.clip(center + (idx % 3) - 1, 0, cfg.grid_size - 1))
            y = int(np.clip(center + (idx // 3) - 1, 0, cfg.grid_size - 1))
            while (x, y) in used:
                x = int(np.clip(x + 1, 0, cfg.grid_size - 1))
                if (x, y) in used:
                    y = int(np.clip(y + 1, 0, cfg.grid_size - 1))
            used.add((x, y))
            self.agents[idx] = AgentBody(idx, x, y, cfg.initial_energy)
        # Message pool: list of (Message). Delivered to observers next tick.
        self.messages: list[Message] = []
        self._next_msg_id: int = 0

    # --------------------------------------------------------------- objects
    def _energy_cap(self) -> float:
        return float(self.config.initial_energy) * ENERGY_CAP_FACTOR

    def _random_cell(self) -> tuple[int, int]:
        g = self.config.grid_size
        return int(self.rng.integers(0, g)), int(self.rng.integers(0, g))

    def _spawn_object(self, kind: str | None = None) -> WorldObject:
        rng = self.rng
        if kind is None:
            kind = str(rng.choice(["food", "hazard", "tool", "curio"]))
        if kind == "food":
            ev, dn, ut, nv = float(rng.uniform(6, 10)), 0.0, float(rng.uniform(0.1, 0.4)), float(rng.uniform(0.6, 1))
        elif kind == "hazard":
            ev, dn, ut, nv = 0.0, float(rng.uniform(0.5, 0.9)), 0.0, float(rng.uniform(0.5, 1))
        elif kind == "tool":
            ev, dn, ut, nv = float(rng.uniform(0, 2)), float(rng.uniform(0, 0.2)), float(rng.uniform(0.6, 1)), float(rng.uniform(0.5, 1))
        else:
            ev, dn, ut, nv = 0.0, float(rng.uniform(0, 0.1)), float(rng.uniform(0, 0.2)), float(rng.uniform(0.9, 1))
        x, y = self._random_cell()
        obj = WorldObject(id=self._next_id, kind=kind, x=x, y=y,
                          energy_value=round(ev, 4), danger=round(dn, 4),
                          novelty=round(nv, 4), utility=round(ut, 4))
        self.objects[obj.id] = obj
        self.seen_counts[obj.id] = 0
        self._next_id += 1
        return obj

    # ------------------------------------------------------------- messaging
    def post_message(self, sender_id: int, content: str, vector: list[float]) -> Message:
        """Deposit a message at the sender's location, deliverable from next tick."""
        body = self.agents[sender_id]
        msg = Message(id=self._next_msg_id, tick_emitted=self.tick, sender_id=sender_id,
                      content=str(content), vector=[float(v) for v in vector],
                      x=body.x, y=body.y, radius=int(self.config.comm_radius),
                      ttl=int(self.config.message_ttl))
        self.messages.append(msg)
        self._next_msg_id += 1
        return msg

    def purge_messages(self) -> None:
        """Drop messages older than their ttl (measured in ticks since emission)."""
        self.messages = [m for m in self.messages if (self.tick - m.tick_emitted) < m.ttl]

    # ----------------------------------------------------------- perception
    def observe(self, agent_id: int) -> Observation:
        cfg = self.config
        radius = cfg.perception_radius
        noise = cfg.world_noise
        me = self.agents[agent_id]
        visible: list[WorldObject] = []
        for obj in self.objects.values():
            if max(abs(obj.x - me.x), abs(obj.y - me.y)) <= radius:
                if noise > 0.0:
                    dn, nv, ut = self._jitter(obj.danger, noise), self._jitter(obj.novelty, noise), self._jitter(obj.utility, noise)
                else:
                    dn, nv, ut = obj.danger, obj.novelty, obj.utility
                visible.append(WorldObject(id=obj.id, kind=obj.kind, x=obj.x, y=obj.y,
                                           energy_value=obj.energy_value, danger=dn,
                                           novelty=nv, utility=ut))
        # Other agents within perception radius (never myself).
        visible_agents: list[AgentView] = []
        for other in self.agents.values():
            if other.id == agent_id:
                continue
            cheb = max(abs(other.x - me.x), abs(other.y - me.y))
            if cheb <= radius:
                dist = float(np.hypot(other.x - me.x, other.y - me.y))
                visible_agents.append(AgentView(id=other.id, x=other.x, y=other.y,
                                                distance=dist, last_action=other.last_action,
                                                dominant_affect=other.dominant_affect,
                                                valence=other.valence))
        # Messages emitted strictly before this tick, within earshot.
        audible: list[Message] = []
        for m in self.messages:
            if m.sender_id == agent_id or m.tick_emitted >= self.tick:
                continue
            if max(abs(m.x - me.x), abs(m.y - me.y)) <= m.radius:
                audible.append(m)
        return Observation(tick=self.tick, agent_x=me.x, agent_y=me.y,
                           agent_energy=round(float(me.energy), 4), radius=radius,
                           visible=visible, visible_agents=visible_agents,
                           audible_messages=audible)

    def _jitter(self, value: float, noise: float) -> float:
        return round(float(np.clip(value + float(self.rng.normal(0.0, noise)), 0.0, 1.0)), 4)

    # --------------------------------------------------------------- dynamics
    def step(self, agent_id: int, decision: ActionDecision) -> StepResult:
        cfg = self.config
        me = self.agents[agent_id]
        action = decision.action
        events: list[str] = []
        start_energy = float(me.energy)
        me.energy -= ACTION_COSTS.get(action.value, 0.0) + PASSIVE_ENERGY_DECAY

        actual_danger = actual_novelty = actual_energy_value = actual_utility = 0.0
        goal_progress = 0.0
        target = self.objects.get(decision.target_id) if decision.target_id is not None else None

        if action in _MOVEMENT_ACTIONS:
            moved = self._apply_movement(me, action, decision, target, events)
            if moved and target is not None:
                if action == ActionType.APPROACH:
                    goal_progress += 0.2 * (target.utility + min(target.energy_value / 10.0, 1.0))
                if action == ActionType.AVOID:
                    goal_progress += 0.1 * target.danger
        elif action == ActionType.INTERACT:
            goal_progress += self._apply_interact(me, target, events)
            if target is not None:
                actual_energy_value, actual_danger = target.energy_value, target.danger
                actual_utility, actual_novelty = target.utility, target.novelty
        elif action == ActionType.REST:
            me.energy += REST_RECOVERY
            events.append("The agent rests and regains energy.")
        elif action in (ActionType.OBSERVE, ActionType.ANALYZE):
            actual_novelty = self._apply_reveal(target, events)
            if target is not None:
                actual_danger, actual_utility = target.danger, target.utility
        elif action == ActionType.VERBALIZE:
            events.append("The agent verbalizes an internal report (a social message).")

        me.energy = float(np.clip(me.energy, 0.0, self._energy_cap()))
        energy_delta = float(me.energy) - start_energy
        if energy_delta > 0.0:
            goal_progress += min(energy_delta / 10.0, 1.0)

        actual = {
            "danger": round(float(np.clip(actual_danger, 0.0, 1.0)), 4),
            "novelty": round(float(np.clip(actual_novelty, 0.0, 1.0)), 4),
            "goal_progress": round(float(goal_progress), 4),
            "energy_value": round(float(actual_energy_value), 4),
            "utility": round(float(np.clip(actual_utility, 0.0, 1.0)), 4),
        }
        me.last_action = action
        return StepResult(tick=self.tick + 1, action=action, target_id=decision.target_id,
                          energy_delta=round(energy_delta, 4), new_energy=round(float(me.energy), 4),
                          events=events, actual=actual)

    def advance_tick(self) -> None:
        """Advance society time by one tick and expire stale messages."""
        self.tick += 1
        self.purge_messages()

    # --------------------------------------------------------------- helpers
    def _occupied_cells(self, exclude_id: int) -> set[tuple[int, int]]:
        return {(b.x, b.y) for i, b in self.agents.items() if i != exclude_id}

    def _apply_movement(self, me, action, decision, target, events) -> bool:
        dx = dy = 0
        if action == ActionType.APPROACH and target is not None:
            dx, dy = self._sign(target.x - me.x), self._sign(target.y - me.y)
        elif action == ActionType.AVOID and target is not None:
            dx, dy = -self._sign(target.x - me.x), -self._sign(target.y - me.y)
        elif decision.direction is not None and len(decision.direction) == 2:
            dx, dy = self._clamp(decision.direction[0]), self._clamp(decision.direction[1])
        else:
            dx = int(self.rng.integers(-1, 2))
            dy = int(self.rng.integers(-1, 2))
        nx = int(np.clip(me.x + dx, 0, self.config.grid_size - 1))
        ny = int(np.clip(me.y + dy, 0, self.config.grid_size - 1))
        # Deterministic collision rule: cannot step onto another agent's cell.
        if (nx, ny) in self._occupied_cells(me.id):
            events.append("The agent's path is blocked by another agent.")
            return False
        moved = (nx, ny) != (me.x, me.y)
        me.x, me.y = nx, ny
        if moved:
            events.append("The agent moves.")
        return moved

    def _apply_interact(self, me, target, events) -> float:
        if target is None:
            events.append("The agent tries to interact but no target is defined.")
            return 0.0
        if max(abs(target.x - me.x), abs(target.y - me.y)) > 1:
            events.append(f"Interaction ineffective: object {target.id} is too far away.")
            return 0.0
        gp = 0.0
        if target.energy_value > 0.0:
            me.energy += target.energy_value
            gp += min(target.energy_value / 10.0, 1.0)
            events.append(f"The agent interacts with object {target.id} ({target.kind}).")
        if target.danger > 0.0:
            me.energy -= target.danger * INTERACT_DANGER_DAMAGE
            events.append(f"Object {target.id} inflicts damage.")
        if target.utility > 0.0:
            gp += 0.3 * target.utility
        target.novelty = round(float(max(0.0, target.novelty - NOVELTY_DECAY_ON_INTERACT)), 4)
        self.seen_counts[target.id] = self.seen_counts.get(target.id, 0) + 1
        if target.kind == "food" and target.energy_value > 0.0:
            self.objects.pop(target.id, None)
            self.seen_counts.pop(target.id, None)
            events.append(f"Food {target.id} is consumed.")
        return gp

    def _apply_reveal(self, target, events) -> float:
        if target is None:
            events.append("The agent observes its environment.")
            return 0.0
        prior = float(target.novelty)
        target.novelty = round(float(max(0.0, target.novelty - NOVELTY_DECAY_ON_SEE)), 4)
        self.seen_counts[target.id] = self.seen_counts.get(target.id, 0) + 1
        events.append(f"The agent examines object {target.id}.")
        return prior

    @staticmethod
    def _sign(v: int) -> int:
        return 1 if v > 0 else (-1 if v < 0 else 0)

    @staticmethod
    def _clamp(v: int) -> int:
        return 1 if v > 0 else (-1 if v < 0 else 0)

    # ----------------------------------------------------------- snapshot
    def snapshot(self) -> dict:
        return {
            "grid_size": int(self.config.grid_size),
            "tick": int(self.tick),
            "agents": [{"id": b.id, "x": b.x, "y": b.y, "energy": round(b.energy, 4),
                        "last_action": b.last_action.value if b.last_action else None,
                        "affect": b.dominant_affect, "valence": round(b.valence, 4)}
                       for b in self.agents.values()],
            "objects": [o.model_dump() for o in self.objects.values()],
            "messages": [m.model_dump() for m in self.messages],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shared_world.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add core/shared_world.py tests/test_shared_world.py
git commit -m "feat(world): SharedWorld hosting N agents, objects and spatial messages"
```

---

## Task 4: MessageBus — grounded one-tick-deferred communication

**Files:**
- Create: `core/communication.py`
- Test: `tests/test_communication.py`

`MessageBus` builds a grounded message from a `ConsciousMoment` and posts it to the world; delivery (one tick later) and earshot filtering are handled by `SharedWorld.observe`. The bus also turns received messages into a `communication` coalition.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_communication.py
from core.communication import build_message_content, message_coalition
from schemas.models import ConsciousMoment, Message, OtherMind


def _moment():
    return ConsciousMoment(tick=5, contents="Aware of: object 3 (food); affect: curiosity; action: approach.",
                           ignited=True, dominant_source="perception", awareness_level=0.7,
                           valence=0.4, phi_proxy=0.3, free_energy=-0.5, arousal=0.6,
                           summary="t5 summary")


def test_build_message_content_is_grounded_in_the_moment():
    content, vector = build_message_content(0, _moment())
    assert content.startswith("agent 0:")
    assert "curiosity" in content or "object 3" in content
    assert len(vector) == 4 and all(isinstance(v, float) for v in vector)


def test_message_coalition_precision_uses_trust():
    msg = Message(id=1, tick_emitted=4, sender_id=2, content="agent 2: ...",
                  vector=[0.5, 0.2, 0.1, 0.0], x=1, y=1, radius=4, ttl=2)
    trusted = OtherMind(agent_id=2, trust=0.9)
    untrusted = OtherMind(agent_id=2, trust=0.1)
    c_hi = message_coalition(msg, trusted)
    c_lo = message_coalition(msg, untrusted)
    assert c_hi.source == "communication"
    assert c_hi.precision > c_lo.precision
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_communication.py -v`
Expected: FAIL with `ModuleNotFoundError: core.communication`.

- [ ] **Step 3: Implement the bus helpers**

```python
# core/communication.py
"""Grounded inter-agent communication for the society layer.

FUNCTIONAL NOTE: a VERBALIZE action emits a Message whose content is a grounded
summary of the sender's ConsciousMoment — nothing is invented. Messages are
posted to the SharedWorld and delivered (one tick later, within earshot) by
SharedWorld.observe. On receipt a message becomes a 'communication' coalition
that competes for global-workspace access like any other bid. No LLM, no free
text generation; the system is not conscious, sentient, or alive.
"""
from __future__ import annotations

import numpy as np

from schemas.models import Coalition, ConsciousMoment, Message, OtherMind


def build_message_content(sender_id: int, moment: ConsciousMoment | None) -> tuple[str, list[float]]:
    """Build a grounded (content, vector) pair from the sender's conscious moment."""
    if moment is None:
        return (f"agent {sender_id}: (no content)", [0.0, 0.0, 0.0, 0.0])
    content = f"agent {sender_id}: {moment.contents}"
    vector = [
        float(np.clip(moment.awareness_level, 0.0, 1.0)),
        float((np.clip(moment.valence, -1.0, 1.0) + 1.0) / 2.0),
        float(np.clip(moment.phi_proxy, 0.0, 1.0)),
        float(np.clip(moment.arousal, 0.0, 1.0)),
    ]
    return content, vector


def message_coalition(message: Message, other: OtherMind | None) -> Coalition:
    """Turn a received message into a 'communication' coalition bid.

    Activation = the message's salience (mean of its feature vector, a stand-in
    for how strongly it carries affect/awareness). Precision = trust in the
    sender (an untrusted source is weighted down, exactly like low-precision
    sensory evidence under precision-weighting).
    """
    vec = [float(v) for v in (message.vector or [])]
    activation = float(np.clip(np.mean(vec), 0.0, 1.0)) if vec else 0.3
    trust = float(other.trust) if other is not None else 0.5
    return Coalition(
        source="communication",
        content=f"communication: {message.content}",
        activation=float(np.clip(activation, 0.0, 1.0)),
        precision=float(np.clip(trust, 0.0, 1.0)),
        vector=(vec + [0.0, 0.0, 0.0, 0.0])[:4],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_communication.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/communication.py tests/test_communication.py
git commit -m "feat(comm): grounded message content + communication coalition bid"
```

---

## Task 5: TheoryOfMind — per-agent models of others

**Files:**
- Create: `core/theory_of_mind.py`
- Test: `tests/test_theory_of_mind.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_theory_of_mind.py
from core.theory_of_mind import TheoryOfMind
from schemas.models import AgentView, ActionType, Message


def test_familiarity_grows_with_repeated_exposure():
    tom = TheoryOfMind()
    av = AgentView(id=1, x=1, y=1, distance=1.0, last_action=ActionType.APPROACH,
                   dominant_affect="curiosity", valence=0.3)
    tom.update([av], [], tick=0)
    f1 = tom.model_of(1).familiarity
    tom.update([av], [], tick=1)
    f2 = tom.model_of(1).familiarity
    assert 0.0 < f1 < f2 <= 1.0


def test_infers_action_and_valence_from_view():
    tom = TheoryOfMind()
    av = AgentView(id=2, x=2, y=2, distance=2.0, last_action=ActionType.AVOID,
                   dominant_affect="fear", valence=-0.5)
    tom.update([av], [], tick=3)
    m = tom.model_of(2)
    assert m.inferred_action == ActionType.AVOID
    assert m.inferred_affect == "fear" and m.inferred_valence < 0.0
    assert m.last_seen_tick == 3


def test_social_coalition_scales_with_salience():
    tom = TheoryOfMind()
    near_intense = AgentView(id=1, x=1, y=1, distance=1.0, dominant_affect="fear", valence=-0.9)
    far_calm = AgentView(id=2, x=9, y=9, distance=9.0, dominant_affect="neutral", valence=0.0)
    tom.update([near_intense, far_calm], [], tick=0, grid_size=12)
    c = tom.social_coalition(grid_size=12)
    assert c is not None and c.source == "social"
    assert 0.0 <= c.activation <= 1.0


def test_no_others_yields_no_social_coalition():
    tom = TheoryOfMind()
    tom.update([], [], tick=0)
    assert tom.social_coalition(grid_size=12) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_theory_of_mind.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `TheoryOfMind`**

```python
# core/theory_of_mind.py
"""Theory of Mind (ToM): a functional model of other agents' states.

FUNCTIONAL NOTE: each agent maintains an OtherMind per congener, inferring the
other's likely action and affect from observed behaviour and messages. These are
bookkeeping estimates over observed variables — not access to anyone's experience.
The most socially salient other produces a 'social' coalition that competes for
global-workspace access. The system is not conscious, sentient, or alive.
"""
from __future__ import annotations

import numpy as np

from core.constants import FAMILIARITY_EMA
from schemas.models import AgentView, Coalition, Message, OtherMind


class TheoryOfMind:
    """Maintains and updates an OtherMind per observed agent."""

    def __init__(self) -> None:
        self._models: dict[int, OtherMind] = {}
        self._last_views: list[AgentView] = []

    def model_of(self, agent_id: int) -> OtherMind:
        return self._models.setdefault(agent_id, OtherMind(agent_id=agent_id))

    def all_models(self) -> list[OtherMind]:
        return sorted(self._models.values(), key=lambda m: m.agent_id)

    def update(self, views: list[AgentView], messages: list[Message],
               tick: int, grid_size: int = 12) -> None:
        """Refresh ToM models from this tick's observed agents and messages."""
        self._last_views = list(views)
        for av in views:
            m = self.model_of(av.id)
            m.inferred_action = av.last_action
            m.inferred_affect = av.dominant_affect
            m.inferred_valence = float(np.clip(av.valence, -1.0, 1.0))
            m.familiarity = float(np.clip(
                (1.0 - FAMILIARITY_EMA) * m.familiarity + FAMILIARITY_EMA * 1.0, 0.0, 1.0))
            m.last_seen_tick = int(tick)
            m.note = (f"agent {av.id}: action={av.last_action.value if av.last_action else 'unknown'}, "
                      f"affect={av.dominant_affect}, valence={m.inferred_valence:.2f}")
        # A message is weak evidence the sender is socially active.
        for msg in messages:
            m = self.model_of(msg.sender_id)
            m.familiarity = float(np.clip(
                (1.0 - FAMILIARITY_EMA) * m.familiarity + FAMILIARITY_EMA * 0.6, 0.0, 1.0))

    def _salience(self, av: AgentView, grid_size: int) -> float:
        """Social salience: closer + more affectively intense => more salient."""
        proximity = 1.0 - float(np.clip(av.distance / max(1.0, float(grid_size)), 0.0, 1.0))
        intensity = float(np.clip(abs(av.valence), 0.0, 1.0))
        return float(np.clip(0.6 * proximity + 0.4 * intensity, 0.0, 1.0))

    def social_coalition(self, grid_size: int = 12) -> Coalition | None:
        """Build a 'social' coalition from the most salient currently-visible other."""
        if not self._last_views:
            return None
        top = max(self._last_views, key=lambda av: self._salience(av, grid_size))
        sal = self._salience(top, grid_size)
        m = self.model_of(top.id)
        return Coalition(
            source="social",
            content=f"social: agent {top.id} ({m.inferred_affect})",
            activation=float(np.clip(sal, 0.0, 1.0)),
            precision=float(np.clip(m.familiarity, 0.0, 1.0)),
            vector=[float((m.inferred_valence + 1.0) / 2.0), float(m.familiarity),
                    float(m.trust), float(sal)],
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_theory_of_mind.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add core/theory_of_mind.py tests/test_theory_of_mind.py
git commit -m "feat(tom): theory-of-mind models + social coalition bid"
```

---

## Task 6: SocialEmotion — contagion & reputation

**Files:**
- Create: `core/social_emotion.py`
- Test: `tests/test_social_emotion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_social_emotion.py
from core.social_emotion import apply_contagion, update_trust
from schemas.models import AgentView, EmotionState, OtherMind


def test_contagion_moves_affect_toward_fearful_neighbour():
    own = EmotionState(fear=0.0, curiosity=0.2)
    neighbour = AgentView(id=1, x=1, y=1, distance=1.0, dominant_affect="fear", valence=-0.8)
    out = apply_contagion(own, [neighbour], {1: OtherMind(agent_id=1, trust=1.0)}, rate=0.5)
    assert out.fear > own.fear  # picked up the neighbour's fear


def test_contagion_is_noop_without_neighbours():
    own = EmotionState(fear=0.3, curiosity=0.4)
    out = apply_contagion(own, [], {}, rate=0.5)
    assert out == own


def test_trust_rises_on_positive_reward_near_other():
    om = OtherMind(agent_id=1, trust=0.5)
    update_trust(om, reward=1.0, rate=0.25)
    assert om.trust > 0.5
    update_trust(om, reward=-1.0, rate=0.25)
    assert om.trust < 0.625  # moved back down
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_social_emotion.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement social affect**

```python
# core/social_emotion.py
"""Social affect: emotional contagion and reputation/trust.

FUNCTIONAL NOTE: contagion nudges an agent's functional affect scalars toward the
affect it perceives in nearby others (weighted by trust); trust is a reputation
scalar updated by the sign of the agent's own reward while engaged with another.
These are bounded control variables, not feelings. The system is not conscious.
"""
from __future__ import annotations

import numpy as np

from schemas.models import AgentView, EmotionState, OtherMind

# Which affect channel each affect-label maps onto for contagion.
_AFFECT_CHANNEL = {
    "fear": "fear", "curiosity": "curiosity", "satisfaction": "satisfaction",
    "fatigue": "fatigue", "confusion": "confusion",
}


def apply_contagion(own: EmotionState, views: list[AgentView],
                    others: dict[int, OtherMind], rate: float) -> EmotionState:
    """Return a new EmotionState nudged toward neighbours' affect (EMA, bounded).

    For each visible other, its dominant affect label contributes to the matching
    channel, weighted by trust and proximity. With no neighbours this is a no-op
    (returns the input unchanged).
    """
    if not views:
        return own
    channels = {"fear": 0.0, "curiosity": 0.0, "satisfaction": 0.0,
                "fatigue": 0.0, "confusion": 0.0}
    weight_sum = 0.0
    for av in views:
        ch = _AFFECT_CHANNEL.get(av.dominant_affect)
        if ch is None:
            continue
        trust = float(others.get(av.id).trust) if others.get(av.id) else 0.5
        proximity = 1.0 - float(np.clip(av.distance / 12.0, 0.0, 1.0))
        w = float(np.clip(trust * (0.5 + 0.5 * proximity), 0.0, 1.0))
        # Intensity of the other's affect proxied by |valence|, min 0.3 so a
        # labelled affect always transmits something.
        channels[ch] += w * max(0.3, float(np.clip(abs(av.valence), 0.0, 1.0)))
        weight_sum += w
    if weight_sum <= 0.0:
        return own
    a = float(np.clip(rate, 0.0, 1.0))

    def blend(cur: float, target: float) -> float:
        return float(np.clip((1.0 - a) * cur + a * float(np.clip(target, 0.0, 1.0)), 0.0, 1.0))

    return EmotionState(
        fear=blend(own.fear, channels["fear"]),
        curiosity=blend(own.curiosity, channels["curiosity"]),
        satisfaction=blend(own.satisfaction, channels["satisfaction"]),
        fatigue=blend(own.fatigue, channels["fatigue"]),
        confusion=blend(own.confusion, channels["confusion"]),
    )


def update_trust(other: OtherMind, reward: float, rate: float) -> None:
    """EMA-update an OtherMind's trust toward 1.0 on positive reward, 0.0 on negative."""
    target = 1.0 if reward > 0 else (0.0 if reward < 0 else other.trust)
    a = float(np.clip(rate, 0.0, 1.0))
    other.trust = float(np.clip((1.0 - a) * other.trust + a * target, 0.0, 1.0))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_social_emotion.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/social_emotion.py tests/test_social_emotion.py
git commit -m "feat(social): emotional contagion + reputation/trust"
```

---

## Task 7: Motivation — the `affiliate` need

**Files:**
- Modify: `core/motivation.py`
- Test: `tests/test_affiliation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_affiliation.py
from core.motivation import MotivationSystem
from schemas.models import EmotionState, SelfModelState, SimConfig, ActionType


def _self():
    labels = [a.value for a in ActionType]
    return SelfModelState(identity="x", age_ticks=0, energy=100.0, confidence=0.5, mood=0.0,
                          preferences={l: 0.5 for l in labels}, active_goals=[],
                          capability_beliefs={l: 0.5 for l in labels}, coherence=1.0, narrative="n")


def test_affiliate_pressure_present_and_scales_with_drive():
    cfg = SimConfig(affiliation_drive=2.0)
    m = MotivationSystem(cfg)
    goals = m.evaluate(_self(), EmotionState(), [], 0.0, 0.0, cfg, n_visible_agents=0)
    aff = next(g for g in goals if g.need == "affiliate")
    # Isolated agent (0 visible) feels affiliation pressure, scaled by the drive.
    assert aff.pressure > 0.0


def test_affiliate_pressure_drops_when_others_present():
    cfg = SimConfig(affiliation_drive=1.0)
    m = MotivationSystem(cfg)
    alone = next(g for g in m.evaluate(_self(), EmotionState(), [], 0.0, 0.0, cfg, n_visible_agents=0) if g.need == "affiliate")
    social = next(g for g in m.evaluate(_self(), EmotionState(), [], 0.0, 0.0, cfg, n_visible_agents=3) if g.need == "affiliate")
    assert social.pressure < alone.pressure
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_affiliation.py -v`
Expected: FAIL with `TypeError` (`evaluate` has no `n_visible_agents`) / missing `affiliate` goal.

- [ ] **Step 3: Add the `affiliate` need (backward-compatible signature)**

In `core/motivation.py`, change the `evaluate` signature to accept an optional count:

```python
    def evaluate(
        self,
        self_model: SelfModelState,
        emotion: EmotionState,
        percepts: list[Percept],
        prediction_error: float,
        uncertainty: float,
        config: SimConfig,
        n_visible_agents: int = 0,
    ) -> list[GoalPressure]:
```

Then, just before the final `return [` list, compute the affiliation pressure:

```python
        # affiliate: pressure to be near others; high when isolated, relieved by
        # company. Scaled by the affiliation drive. Zero drive => zero pressure.
        isolation = 1.0 / (1.0 + float(max(0, n_visible_agents)))
        affiliate = max(0.0, float(config.affiliation_drive) * isolation)
```

And add this `GoalPressure` to the returned list (append as the last element):

```python
            GoalPressure(
                need="affiliate",
                pressure=float(affiliate),
                description=(f"Seek social contact ({n_visible_agents} agent(s) visible)."),
            ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_affiliation.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify no regression & commit**

Run: `pytest -q`
Expected: existing motivation/agent tests still pass (the new arg is optional, default 0).

```bash
git add core/motivation.py tests/test_affiliation.py
git commit -m "feat(motivation): add affiliate (social) goal pressure"
```

---

## Task 8: Wire the social layer into CognitiveAgent

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_agent_social_hooks.py`

The agent gains an optional `agent_id` and an optional shared world. When given a shared world it observes through it, runs ToM, injects `communication`/`social` coalitions, applies contagion, emits messages on `VERBALIZE`, and fills `trace.social`. With no shared world (legacy path) every hook is a no-op.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agent_social_hooks.py
from core.agent import CognitiveAgent
from core.shared_world import SharedWorld
from schemas.models import SimConfig


def test_agent_in_shared_world_produces_social_trace():
    cfg = SimConfig(grid_size=8, n_objects=4, world_noise=0.0, n_agents=2, random_seed=11)
    world = SharedWorld(cfg)
    a0 = CognitiveAgent(cfg, agent_id=0, shared_world=world)
    a1 = CognitiveAgent(cfg, agent_id=1, shared_world=world)
    # Put them adjacent so they perceive each other.
    world.agents[0].x, world.agents[0].y = 4, 4
    world.agents[1].x, world.agents[1].y = 5, 4
    trace = a0.cognitive_cycle()
    assert trace.social is not None and trace.social.agent_id == 0


def test_legacy_agent_has_no_social_trace():
    cfg = SimConfig(grid_size=8, n_objects=4, world_noise=0.0)
    a = CognitiveAgent(cfg)  # no agent_id / shared world => legacy single-agent path
    trace = a.cognitive_cycle()
    assert trace.social is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_social_hooks.py -v`
Expected: FAIL (`CognitiveAgent.__init__` takes no `agent_id`).

- [ ] **Step 3: Implement the hooks**

In `core/agent.py`:

(a) Add imports near the other `core` imports:

```python
from core.communication import build_message_content, message_coalition
from core.shared_world import SharedWorld
from core.social_emotion import apply_contagion, update_trust
from core.theory_of_mind import TheoryOfMind
from schemas.models import AgentView, SocialState  # add to the existing schemas import block
```

(b) Change the constructor to accept the social context:

```python
    def __init__(self, config: SimConfig, *, agent_id: int = 0,
                 shared_world: "SharedWorld | None" = None) -> None:
        self.config = config
        self.agent_id = int(agent_id)
        self._shared_world = shared_world
        self._build(config)
```

(c) In `_build`, after `self._dialogue = IntrospectiveDialogue()`, add:

```python
        # Society layer (active only when a shared world is attached).
        self.theory_of_mind = TheoryOfMind()
        self._last_social: SocialState | None = None
        self._last_visible_agents: list[AgentView] = []
```

(d) In `cognitive_cycle`, replace step 1 (`observation = self.world.observe()`) with a source-aware observe, and capture visible agents + messages:

```python
        # 1) Observe — from the shared world when in a society, else the solo world.
        if self._shared_world is not None:
            observation = self._shared_world.observe(self.agent_id)
        else:
            observation = self.world.observe()
        visible_agents = list(observation.visible_agents)
        audible_messages = list(observation.audible_messages)
        self._last_visible_agents = visible_agents
```

(e) Pass the visible-agent count to motivation — change the `self.motivation.evaluate(...)` call in step 3 to add the kwarg:

```python
        goals = self.motivation.evaluate(
            self_state, self.last_emotion, percepts, prev_error, uncertainty, cfg,
            n_visible_agents=len(visible_agents),
        )
```

(f) After percepts/goals are computed and BEFORE building coalitions (step 6b), update ToM:

```python
        # Theory of mind: refresh models of visible others + their messages.
        if self._shared_world is not None:
            self.theory_of_mind.update(visible_agents, audible_messages,
                                       tick=observation.tick, grid_size=cfg.grid_size)
```

(g) In `_build_coalitions`, after the metacognition coalition block and before `return coalitions`, add the social/communication bids:

```python
        # --- social: the most salient visible other (theory of mind). ---
        social_coalition = self.theory_of_mind.social_coalition(grid_size=cfg.grid_size)
        if social_coalition is not None:
            coalitions.append(social_coalition)

        # --- communication: the most salient received message. ---
        if self._shared_world is not None and self._last_visible_agents is not None:
            best_msg = None
            best_sal = -1.0
            for msg in self._last_audible_messages:
                sal = sum(msg.vector) if msg.vector else 0.3
                if sal > best_sal:
                    best_sal, best_msg = sal, msg
            if best_msg is not None:
                other = self.theory_of_mind.model_of(best_msg.sender_id)
                coalitions.append(message_coalition(best_msg, other))
```

Store the audible messages so `_build_coalitions` can see them — in step (d)'s block add:

```python
        self._last_audible_messages = audible_messages
```

and initialise `self._last_audible_messages: list = []` in `_build` next to `_last_visible_agents`.

(h) Apply contagion right AFTER the emotion update (step 12 produces `emotion`); insert:

```python
        # Emotional contagion from visible others (no-op when alone).
        if self._shared_world is not None and visible_agents:
            others = {m.agent_id: m for m in self.theory_of_mind.all_models()}
            emotion = apply_contagion(emotion, visible_agents, others, rate=cfg.contagion_rate)
            # Reputation: nudge trust of nearby others by this tick's reward sign.
            reward_sign = float(result.energy_delta) + float(result.actual.get("goal_progress", 0.0))
            for av in visible_agents:
                if av.distance <= 1.5:
                    update_trust(self.theory_of_mind.model_of(av.id), reward_sign, rate=0.25)
```

(i) Use the shared world for the action step. Replace step 10 (`result = self.world.step(decision)`) with:

```python
        if self._shared_world is not None:
            result = self._shared_world.step(self.agent_id, decision)
        else:
            result = self.world.step(decision)
```

(j) After the conscious moment is bound (step 14) and the self-model updated, publish the social signal and emit a message on VERBALIZE. Insert just before assembling the trace (step 19):

```python
        # Publish this agent's social signal so others can perceive it.
        if self._shared_world is not None:
            affects = {"fear": emotion.fear, "curiosity": emotion.curiosity,
                       "satisfaction": emotion.satisfaction, "fatigue": emotion.fatigue,
                       "confusion": emotion.confusion}
            dom_affect = max(affects, key=affects.get)
            self._shared_world.agents[self.agent_id].publish(
                decision.action, dom_affect, float(self_state_after.mood))
            # VERBALIZE => emit a grounded message (delivered next tick).
            last_emitted = None
            if decision.action == ActionType.VERBALIZE:
                content, vector = build_message_content(self.agent_id, conscious_moment)
                self._shared_world.post_message(self.agent_id, content, vector)
                last_emitted = content
            self._last_social = SocialState(
                agent_id=self.agent_id,
                others=self.theory_of_mind.all_models(),
                affiliation_pressure=float(next((g.pressure for g in goals if g.need == "affiliate"), 0.0)),
                last_emitted=last_emitted,
                received_count=len(audible_messages),
            )
```

(k) Add `social=self._last_social` to the `CycleTrace(...)` constructor (step 19).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_agent_social_hooks.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Verify no regression & commit**

Run: `pytest -q`
Expected: ALL existing tests still pass (legacy path untouched: `social is None`, solo world used).

```bash
git add core/agent.py tests/test_agent_social_hooks.py
git commit -m "feat(agent): additive social hooks (ToM, coalitions, contagion, messages)"
```

---

## Task 9: SocietyManager — deterministic orchestration + façade

**Files:**
- Create: `core/society.py`
- Modify: `core/agent.py` (make `get_manager` return a society façade)
- Test: `tests/test_society.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_society.py
from core.society import SocietyManager
from schemas.models import SimConfig


def test_society_ticks_all_agents_and_is_deterministic():
    cfg = SimConfig(grid_size=8, n_objects=4, world_noise=0.0, n_agents=3, random_seed=5)
    a = SocietyManager(cfg)
    b = SocietyManager(cfg)
    ta = [t.tick for t in a.tick()]
    tb = [t.tick for t in b.tick()]
    assert len(ta) == 3 and ta == tb  # one trace per agent, identical across runs


def test_society_of_one_matches_solo_energy_trajectory():
    cfg = SimConfig(grid_size=10, n_objects=6, world_noise=0.0, n_agents=1, random_seed=9)
    soc = SocietyManager(cfg)
    for _ in range(5):
        soc.tick()
    # The single agent in a society of 1 must have a populated trace with no social state.
    trace = soc.agents[0].last_trace
    assert trace is not None and trace.social is not None  # society always sets social
    assert soc.world.tick == 5


def test_verbalize_message_is_heard_next_tick():
    cfg = SimConfig(grid_size=6, n_objects=2, world_noise=0.0, n_agents=2, random_seed=3)
    soc = SocietyManager(cfg)
    soc.world.agents[0].x, soc.world.agents[0].y = 3, 3
    soc.world.agents[1].x, soc.world.agents[1].y = 3, 3  # same earshot
    # Force agent 0 to emit by posting directly, then tick: agent 1 should hear it.
    soc.world.post_message(0, "agent 0: hello", [0.5, 0.5, 0.2, 0.3])
    soc.world.advance_tick()  # message now belongs to a prior tick
    obs1 = soc.world.observe(1)
    assert any("hello" in m.content for m in obs1.audible_messages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_society.py -v`
Expected: FAIL with `ModuleNotFoundError: core.society`.

- [ ] **Step 3: Implement `SocietyManager`**

```python
# core/society.py
"""Society orchestration: owns the SharedWorld and N CognitiveAgents.

FUNCTIONAL NOTE: ticks every agent once per society tick in deterministic id
order against a shared world, collecting one CycleTrace per agent. A society of 1
reproduces the single-agent instrument. Nothing here is conscious.
"""
from __future__ import annotations

import asyncio

from core.agent import CognitiveAgent
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

    # ------------------------------------------------------------- ticking
    def tick(self) -> list[CycleTrace]:
        """Run one society tick: each agent cycles once, in ascending id order."""
        traces: list[CycleTrace] = []
        for aid in sorted(self.agents):
            traces.append(self.agents[aid].cognitive_cycle())
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
```

(b) In `core/agent.py`, keep `SimulationManager` but make the module singleton a society façade. Replace `get_manager` with:

```python
def get_manager() -> "SocietyManager":
    """Return the process-wide SocietyManager (society of `config.n_agents`)."""
    global _MANAGER
    if _MANAGER is None:
        from core.society import SocietyManager
        _MANAGER = SocietyManager()
    return _MANAGER
```

> Because `SocietyManager` always wires `social`, the existing `/state` etc. read agent 0 via the façade accessors added in Task 10. `SimulationManager` remains importable for any direct single-agent use and its own tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_society.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add core/society.py core/agent.py tests/test_society.py
git commit -m "feat(society): SocietyManager orchestration + society singleton"
```

---

## Task 10: API — `/society/*` endpoints + façade for `/agent/*`

**Files:**
- Modify: `app/api/routes.py`
- Test: `tests/test_society_api.py`, `tests/test_backward_compat.py`

The legacy `/agent/*`, `/state`, `/tick`, `/metrics` endpoints must keep working by targeting agent 0 of the society. Add `/society/*` for the multi-agent view.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_society_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_society_config_then_state_lists_agents():
    client.post("/society/config", json={"n_agents": 3, "random_seed": 4, "world_noise": 0.0})
    client.post("/society/tick")
    body = client.get("/society").json()
    assert body["n_agents"] == 3 and len(body["agents"]) == 3
    assert "relations" in body and "edges" in body["relations"]


def test_society_per_agent_consciousness():
    client.post("/society/config", json={"n_agents": 2, "random_seed": 4})
    client.post("/society/tick")
    r = client.get("/society/agent/1/consciousness")
    assert r.status_code == 200 and "disclaimer" in r.json()


def test_unknown_agent_is_404():
    client.post("/society/config", json={"n_agents": 1, "random_seed": 4})
    assert client.get("/society/agent/99/consciousness").status_code == 404
```

```python
# tests/test_backward_compat.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_legacy_endpoints_still_work():
    client.post("/society/config", json={"n_agents": 1, "random_seed": 1})
    assert client.post("/tick").status_code == 200
    s = client.get("/state").json()
    assert "metrics" in s and "disclaimer" in s
    assert client.get("/agent/self-model").status_code == 200
    assert client.get("/agent/consciousness").status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_society_api.py tests/test_backward_compat.py -v`
Expected: FAIL (no `/society` routes; legacy handlers call methods the façade lacks).

- [ ] **Step 3: Update the routes**

In `app/api/routes.py`:

(a) Add a small accessor near `_manager()`:

```python
from fastapi import APIRouter, HTTPException, Query
from core.society import SocietyManager


def _agent0():
    """Legacy single-agent accessor: agent 0 of the society façade."""
    return _manager().agent(0)
```

(b) Rewrite the legacy handlers that previously used `_manager().agent` to use `_agent0()` and the society for ticking. Specifically:

- `/tick`: `return (await _manager().async_tick())[0]`  (agent 0's trace)
- `/state`: build from the society — return `_society_state_legacy()` (below).
- `/reset`, `/run`, `/pause`, `/config`: delegate to `_manager()` (`SocietyManager`).
- `/agent/self-model`, `/agent/memory`, `/agent/introspection`, `/agent/consciousness`, `/agent/workspace`, `/agent/stream`, `/agent/goal`, `/agent/ask`, `/agent/inject`, `/agent/attend`, `/agent/perturb`: replace `_manager().agent` with `_agent0()`; for `ask/inject/attend/perturb` call the method directly on `_agent0()` (they are synchronous on `CognitiveAgent`).
- `/metrics`: `return _agent0().metrics()`
- `/trace`: `Path(_agent0().trace_logger.path())`

Add the legacy state helper:

```python
def _society_state_legacy() -> dict:
    """Legacy /state shape, sourced from agent 0 of the society."""
    mgr = _manager()
    ag = mgr.agent(0)
    metrics = ag.metrics()
    intro = ag._last_introspection
    ws = ag.workspace_state()
    return {
        "world": mgr.world.snapshot(),
        "metrics": metrics.model_dump(),
        "running": bool(mgr.running),
        "introspection_summary": intro.self_state if intro else "No introspective report generated yet.",
        "self_model": ag.self_model_state().model_dump(),
        "working_memory_load": float(ag.working_memory.load()),
        "phi_proxy": float(metrics.phi_proxy),
        "free_energy": float(metrics.free_energy),
        "awareness_level": float(metrics.awareness_level),
        "ignition": bool(metrics.ignition),
        "broadcast_strength": float(metrics.broadcast_strength),
        "winner_source": ws.winner_source,
        "arousal": float(metrics.arousal),
    }
```

(c) Add the society endpoints at the end of the file:

```python
@router.get("/society")
async def get_society() -> dict:
    state = _manager().state()
    state["disclaimer"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.post("/society/tick")
async def post_society_tick() -> dict:
    traces = await _manager().async_tick()
    return {"traces": [t.model_dump() for t in traces]}


@router.post("/society/run")
async def post_society_run(req: RunRequest) -> dict:
    await _manager().run(req)
    return {"running": True}


@router.post("/society/pause")
async def post_society_pause() -> dict:
    _manager().pause()
    return {"running": False}


@router.post("/society/config")
async def post_society_config(patch: ConfigPatch) -> dict:
    mgr = _manager()
    mgr.reset(patch)
    state = mgr.state()
    state["disclaimer"] = DISCLAIMER_EN
    return state


@router.get("/society/relations")
async def get_society_relations() -> dict:
    return _manager().relations()


@router.get("/society/messages")
async def get_society_messages() -> dict:
    return {"messages": [m.model_dump() for m in _manager().world.messages]}


def _require_agent(agent_id: int):
    mgr = _manager()
    if agent_id not in mgr.agents:
        raise HTTPException(status_code=404, detail=f"agent {agent_id} not found")
    return mgr.agent(agent_id)


@router.get("/society/agent/{agent_id}/consciousness")
async def get_society_agent_consciousness(agent_id: int) -> dict:
    state = _require_agent(agent_id).consciousness_state()
    state["disclaimer"] = DISCLAIMER_EN
    state["framing"] = THEORY_FRAMING_EN
    return state


@router.get("/society/agent/{agent_id}/self-model", response_model=SelfModelState)
async def get_society_agent_self_model(agent_id: int) -> SelfModelState:
    return _require_agent(agent_id).self_model_state()


@router.get("/society/agent/{agent_id}/introspection", response_model=IntrospectionReport)
async def get_society_agent_introspection(agent_id: int) -> IntrospectionReport:
    return _require_agent(agent_id).introspect()


@router.get("/society/agent/{agent_id}/workspace", response_model=WorkspaceState)
async def get_society_agent_workspace(agent_id: int) -> WorkspaceState:
    return _require_agent(agent_id).workspace_state()
```

(d) WebSocket stream — add near the bottom (import `WebSocket`, `WebSocketDisconnect` from `fastapi`):

```python
from fastapi import WebSocket, WebSocketDisconnect


@router.websocket("/ws/society")
async def ws_society(ws: WebSocket) -> None:
    """Push the society state after each tick (1 message per ~250ms)."""
    await ws.accept()
    import asyncio
    try:
        while True:
            await ws.send_json(_manager().state())
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_society_api.py tests/test_backward_compat.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Verify full suite & commit**

Run: `pytest -q`
Expected: green.

```bash
git add app/api/routes.py tests/test_society_api.py tests/test_backward_compat.py
git commit -m "feat(api): /society endpoints + WebSocket; legacy routes via society façade"
```

---

## Task 11: UI — society view

**Files:**
- Modify: `ui/index.html`, `ui/app.js`, `ui/styles.css`
- Manual verification (no automated UI test; covered by API tests).

- [ ] **Step 1: Add a society panel to `index.html`**

Insert a new `<section>` after the World panel (`panel-world`):

```html
    <!-- ===================== SOCIETY ===================== -->
    <section class="panel panel-society" aria-labelledby="soc-title">
      <div class="panel-head">
        <h2 id="soc-title">Society</h2>
        <span class="src">GET /society · multi-agent</span>
      </div>
      <div class="soc-controls">
        <label class="tps-field" title="Number of agents (POST /society/config)">
          <span>agents</span>
          <input id="input-nagents" type="number" min="1" max="8" step="1" value="1" />
        </label>
        <button id="btn-society-apply" class="btn btn-quiet">Apply</button>
        <span id="soc-selected" class="micro">viewing agent 0</span>
      </div>
      <canvas id="society-canvas" width="560" height="560" aria-label="Society world"></canvas>
      <div id="society-relations" class="rows"></div>
    </section>
```

- [ ] **Step 2: Add society rendering to `app.js`**

Append (adapt to the file's existing fetch/render helpers and `API` base):

```javascript
// ---- Society view ----------------------------------------------------------
let SOC_SELECTED = 0;

async function refreshSociety() {
  let data;
  try {
    data = await fetch(`${API}/society`).then(r => r.json());
  } catch (e) { return; }
  drawSociety(data.world, SOC_SELECTED);
  renderRelations(data.relations, data.agents);
}

function drawSociety(world, selected) {
  const cv = document.getElementById('society-canvas');
  if (!cv || !world) return;
  const ctx = cv.getContext('2d');
  const g = world.grid_size, cell = cv.width / g;
  ctx.clearRect(0, 0, cv.width, cv.height);
  const KIND = { food: '#5ec98a', hazard: '#e0596b', tool: '#7c9cf2', curio: '#c79cf2' };
  (world.objects || []).forEach(o => {
    ctx.fillStyle = KIND[o.kind] || '#888';
    ctx.fillRect(o.x * cell + cell * 0.3, o.y * cell + cell * 0.3, cell * 0.4, cell * 0.4);
  });
  (world.agents || []).forEach(a => {
    ctx.beginPath();
    ctx.arc(a.x * cell + cell / 2, a.y * cell + cell / 2, cell * 0.32, 0, 7);
    ctx.fillStyle = a.id === selected ? '#ffd479' : '#eceff4';
    ctx.fill();
    ctx.fillStyle = '#11131a';
    ctx.font = `${Math.floor(cell * 0.4)}px sans-serif`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(String(a.id), a.x * cell + cell / 2, a.y * cell + cell / 2);
  });
}

function renderRelations(rel, agents) {
  const box = document.getElementById('society-relations');
  if (!box || !rel) return;
  box.innerHTML = (rel.edges || [])
    .map(e => `<div class="row"><span class="mono">${e.from}→${e.to}</span>
               <span class="micro">trust ${e.trust.toFixed(2)} · ${e.affect}</span></div>`)
    .join('') || '<div class="micro">No relations yet.</div>';
}

document.getElementById('btn-society-apply')?.addEventListener('click', async () => {
  const n = parseInt(document.getElementById('input-nagents').value, 10) || 1;
  await fetch(`${API}/society/config`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ n_agents: n }),
  });
  refreshSociety();
});

document.getElementById('society-canvas')?.addEventListener('click', (ev) => {
  // Click an agent to select it (selection drives the per-agent panels).
  fetch(`${API}/society`).then(r => r.json()).then(d => {
    const cv = ev.currentTarget, g = d.world.grid_size, cell = cv.width / g;
    const rect = cv.getBoundingClientRect();
    const gx = Math.floor((ev.clientX - rect.left) / cell);
    const gy = Math.floor((ev.clientY - rect.top) / cell);
    const hit = (d.world.agents || []).find(a => a.x === gx && a.y === gy);
    if (hit) { SOC_SELECTED = hit.id;
      document.getElementById('soc-selected').textContent = `viewing agent ${hit.id}`; }
    refreshSociety();
  });
});
```

Then call `refreshSociety()` from the existing polling loop (wherever `refreshAll()`/`tick()` polls run), so the society view updates alongside the rest.

- [ ] **Step 3: Add minimal styles to `styles.css`**

```css
.panel-society .soc-controls { display: flex; gap: .75rem; align-items: center; margin-bottom: .6rem; }
#society-canvas { width: 100%; border-radius: var(--radius, 10px); background: var(--bg2, #11131a); }
.panel-society .row { display: flex; justify-content: space-between; padding: .15rem .25rem; }
```

- [ ] **Step 4: Manual verification**

Run: `python run.py`, open `http://127.0.0.1:8000`, set agents to 3, click **Apply**, press **Step** a few times. Expect 3 numbered agents on the society canvas, a relations list that fills in as they meet, and clicking an agent updates "viewing agent N".

- [ ] **Step 5: Commit**

```bash
git add ui/index.html ui/app.js ui/styles.css
git commit -m "feat(ui): society view — multi-agent canvas + relations + selection"
```

---

## Task 12: Integration & regression sweep

**Files:**
- Test: `tests/test_society_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_society_integration.py
from core.society import SocietyManager
from schemas.models import ActionType, SimConfig


def test_three_agents_run_deterministically_for_many_ticks():
    cfg = SimConfig(grid_size=10, n_objects=8, world_noise=0.0, n_agents=3, random_seed=21)
    a, b = SocietyManager(cfg), SocietyManager(cfg)
    for _ in range(20):
        a.tick(); b.tick()
    sa = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in a.world.agents.items()}
    sb = {i: (bd.x, bd.y, round(bd.energy, 3)) for i, bd in b.world.agents.items()}
    assert sa == sb  # fully reproducible society


def test_contagion_changes_a_listeners_emotion_over_time():
    cfg = SimConfig(grid_size=6, n_objects=2, world_noise=0.0, n_agents=2,
                    random_seed=2, contagion_rate=0.5)
    soc = SocietyManager(cfg)
    soc.world.agents[0].x, soc.world.agents[0].y = 3, 3
    soc.world.agents[1].x, soc.world.agents[1].y = 3, 3
    # Make agent 0 visibly fearful so agent 1 can catch it.
    soc.world.agents[0].publish(ActionType.AVOID, "fear", -0.8)
    before = soc.agents[1].last_emotion.fear
    for _ in range(3):
        soc.tick()
    after = soc.agents[1].last_emotion.fear
    assert after >= before  # listener's fear did not decrease while exposed


def test_society_of_one_keeps_full_legacy_suite_green():
    # Sanity: a 1-agent society runs a cycle and produces a complete trace.
    soc = SocietyManager(SimConfig(n_agents=1, world_noise=0.0, random_seed=1))
    trace = soc.tick()[0]
    assert trace.metrics is not None and trace.workspace is not None
```

- [ ] **Step 2: Run the whole suite**

Run: `pytest -q`
Expected: all tests pass (legacy + new).

- [ ] **Step 3: Commit**

```bash
git add tests/test_society_integration.py
git commit -m "test(society): determinism, contagion, and society-of-one integration"
```

- [ ] **Step 4: Update the README**

Add a short "Society (multi-agent)" section to `README.md` documenting: `n_agents` config, `/society/*` endpoints, the WebSocket stream, and the determinism guarantee. Then:

```bash
git add README.md
git commit -m "docs: document the multi-agent society layer"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** SharedWorld (§4.2 → T3), Communication (§4.3 → T4), Theory of Mind (§4.4 → T5), Social affect + reputation + affiliate need (§4.5 → T6/T7), cycle integration (§4.6 → T8), SocietyManager + façade (§4.7 → T9), API + WebSocket (§4.8 → T10), UI (§4.9 → T11), determinism/back-compat (§4.10 → T8/T9/T10/T12), data flow (§5 → T8/T9), error handling (§6 → T10 404 + collision in T3), testing (§7 → every task + T12). No gaps.
- **Placeholder scan:** none — every code step shows complete code; edit-in-place steps name exact anchors.
- **Type consistency:** `Message`, `OtherMind`, `AgentView`, `SocialState`, `SharedWorld.observe/step/advance_tick/post_message`, `TheoryOfMind.update/social_coalition/model_of/all_models`, `apply_contagion/update_trust`, `build_message_content/message_coalition`, `SocietyManager.tick/agent/relations/state` are used identically across tasks.
- **Architectural risk caught:** object/agent id-namespace collision avoided — agents are not `target_id`s; affiliation routes through movement direction and the `social` coalition.

---

## Out of scope (Phase 1)

LLM/natural-language generation, agent death/reproduction, learned policy, dreams/consolidation, scientific test battery — all deferred to Phases 2–4 per the spec.
