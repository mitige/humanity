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

    # --------------------------------------------------------- world stimulus
    def inject_object(self, kind: str, x: int | None = None, y: int | None = None,
                      intensity: float = 1.0, near_agent: int = 0) -> WorldObject:
        """Inject a new object into the SHARED world (bottom-up stimulus).

        Properties scale with ``intensity``. Placed at ``(x, y)`` clamped to the
        grid, or — when either coordinate is None — at a free cell next to
        ``near_agent`` (falling back to that agent's own cell)."""
        intensity = float(np.clip(float(intensity), 0.0, 5.0))
        kind = str(kind)
        if kind == "food":
            energy_value = float(np.clip(6.0 * intensity, 0.0, 10.0)); danger = 0.0
            utility = float(np.clip(0.2 * intensity, 0.0, 0.4)); novelty = float(np.clip(0.8 * intensity, 0.0, 1.0))
        elif kind in ("hazard", "danger"):
            energy_value = 0.0; danger = float(np.clip(0.6 * intensity, 0.6, 0.9))
            utility = 0.0; novelty = float(np.clip(0.8 * intensity, 0.0, 1.0))
        elif kind == "tool":
            energy_value = float(np.clip(1.0 * intensity, 0.0, 2.0)); danger = float(np.clip(0.1 * intensity, 0.0, 0.2))
            utility = float(np.clip(0.8 * intensity, 0.6, 1.0)); novelty = float(np.clip(0.7 * intensity, 0.0, 1.0))
        else:  # curio / unknown -> inert novelty
            energy_value = 0.0; danger = float(np.clip(0.05 * intensity, 0.0, 0.1))
            utility = float(np.clip(0.1 * intensity, 0.0, 0.2)); novelty = float(np.clip(0.9 * intensity, 0.8, 1.0))
        if x is None or y is None:
            px, py = self._free_cell_near(near_agent)
        else:
            g = self.config.grid_size
            px = int(np.clip(int(x), 0, g - 1)); py = int(np.clip(int(y), 0, g - 1))
        obj = WorldObject(id=self._next_id, kind=kind, x=px, y=py,
                          energy_value=round(energy_value, 4), danger=round(danger, 4),
                          novelty=round(novelty, 4), utility=round(utility, 4))
        self.objects[obj.id] = obj
        self.seen_counts[obj.id] = 0
        self._next_id += 1
        return obj

    def _free_cell_near(self, agent_id: int) -> tuple[int, int]:
        """Return a free cell adjacent to ``agent_id`` (else that agent's own cell)."""
        g = self.config.grid_size
        me = self.agents.get(agent_id) or next(iter(self.agents.values()))
        occupied = {(o.x, o.y) for o in self.objects.values()} | {(b.x, b.y) for b in self.agents.values()}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = int(np.clip(me.x + dx, 0, g - 1)); ny = int(np.clip(me.y + dy, 0, g - 1))
                if (nx, ny) not in occupied:
                    return nx, ny
        return int(me.x), int(me.y)

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
