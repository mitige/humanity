"""Deterministic grid world for Humanity.

FUNCTIONAL note: this module is a plain physics/dynamics simulator. It produces
the observations and action results that downstream cognitive modules consume.
Nothing here is conscious; it is the environment the simulated agent inhabits.
"""
from __future__ import annotations

import math

import numpy as np

from schemas.models import (
    ActionDecision,
    ActionType,
    Observation,
    SimConfig,
    StepResult,
    WorldObject,
)
from core.constants import (
    ACTION_COSTS,
    DRIFT_EVERY,
    ENERGY_CAP_FACTOR,
    INTERACT_DANGER_DAMAGE,
    NOVELTY_DECAY_ON_INTERACT,
    NOVELTY_DECAY_ON_SEE,
    PASSIVE_ENERGY_DECAY,
    REST_RECOVERY,
)
from core.world_dynamics import apply_dynamics, season_factor
from core.world_tasks import TaskManager

# Movement actions that displace the agent on the grid.
_MOVEMENT_ACTIONS = {
    ActionType.MOVE,
    ActionType.EXPLORE,
    ActionType.APPROACH,
    ActionType.AVOID,
}


class World:
    """Seeded 2D grid environment hosting the agent and a set of objects.

    Deterministic given ``config.random_seed``: the same seed always yields the
    same object layout and the same sequence of random events.
    """

    def __init__(self, config: SimConfig) -> None:
        """Build the world from config, place the agent, and spawn objects."""
        self.config = config
        self._build()

    # ----------------------------------------------------------------- setup
    def _build(self) -> None:
        """(Re)initialize all mutable state from ``self.config``."""
        cfg = self.config
        self.rng = np.random.default_rng(cfg.random_seed)
        self.tick: int = 0
        # Agent starts at the grid center.
        center = cfg.grid_size // 2
        self.agent_x: int = center
        self.agent_y: int = center
        self.agent_energy: float = float(cfg.initial_energy)
        self.objects: dict[int, WorldObject] = {}
        self.seen_counts: dict[int, int] = {}
        self._next_id: int = 0
        # Phase 7 — spawn-time metadata for continuous dynamics (max food energy,
        # base hazard danger). Pure copies at spawn: costs no RNG, so prior-phase
        # runs stay byte-identical whether or not the dynamics flag is on.
        self._spawn_meta: dict[int, dict] = {}
        # Phase 7 — structured tasks (rotation lives in the ENVIRONMENT).
        self.task_manager: TaskManager | None = (
            TaskManager(cfg.grid_size) if cfg.tasks_enabled else None)
        self._last_ate_food: bool = False
        for _ in range(cfg.n_objects):
            self._spawn_object()

    def _energy_cap(self) -> float:
        """Maximum allowed energy."""
        return float(self.config.initial_energy) * ENERGY_CAP_FACTOR

    def _random_cell(self) -> tuple[int, int]:
        """Pick a random valid grid cell."""
        g = self.config.grid_size
        x = int(self.rng.integers(0, g))
        y = int(self.rng.integers(0, g))
        return x, y

    def _spawn_object(self, kind: str | None = None) -> WorldObject:
        """Create one object with kind-appropriate attributes and register it.

        Attribute ranges follow the contract so that dynamics stay interesting:
        food gives energy, hazards are dangerous, tools are useful, curios are
        novel but inert.
        """
        rng = self.rng
        if kind is None:
            kind = str(rng.choice(["food", "hazard", "tool", "curio"]))
        if kind == "food":
            energy_value = float(rng.uniform(6.0, 10.0))
            danger = 0.0
            utility = float(rng.uniform(0.1, 0.4))
            novelty = float(rng.uniform(0.6, 1.0))
        elif kind == "hazard":
            energy_value = 0.0
            danger = float(rng.uniform(0.5, 0.9))
            utility = 0.0
            novelty = float(rng.uniform(0.5, 1.0))
        elif kind == "tool":
            energy_value = float(rng.uniform(0.0, 2.0))
            danger = float(rng.uniform(0.0, 0.2))
            utility = float(rng.uniform(0.6, 1.0))
            novelty = float(rng.uniform(0.5, 1.0))
        else:  # curio
            energy_value = 0.0
            danger = float(rng.uniform(0.0, 0.1))
            utility = float(rng.uniform(0.0, 0.2))
            novelty = float(rng.uniform(0.9, 1.0))
        x, y = self._random_cell()
        obj = WorldObject(
            id=self._next_id,
            kind=kind,
            x=x,
            y=y,
            energy_value=round(energy_value, 4),
            danger=round(danger, 4),
            novelty=round(novelty, 4),
            utility=round(utility, 4),
        )
        self.objects[obj.id] = obj
        self.seen_counts[obj.id] = 0
        self._spawn_meta[obj.id] = {"max_energy": float(energy_value),
                                    "base_danger": float(danger)}
        self._next_id += 1
        return obj

    def inject_object(
        self,
        kind: str,
        x: int | None = None,
        y: int | None = None,
        intensity: float = 1.0,
    ) -> WorldObject:
        """Inject a new object into the world (world-stimulus interaction).

        Properties are scaled by ``intensity`` so a caller can dial up the
        danger / energy_value / novelty of the injected stimulus. The object is
        assigned a fresh unique id and placed at ``(x, y)`` clamped to the grid,
        or, when either coordinate is ``None``, at a free cell adjacent to the
        agent (falling back to the agent's own cell if none is free). This is a
        grounded bottom-up perturbation of the environment: it adds a real
        :class:`WorldObject` that subsequent ``observe`` calls will surface to
        perception, where it can drive attentional capture and ignition.
        """
        intensity = float(np.clip(float(intensity), 0.0, 5.0))
        kind = str(kind)
        if kind == "food":
            energy_value = float(np.clip(6.0 * intensity, 0.0, 10.0))
            danger = 0.0
            utility = float(np.clip(0.2 * intensity, 0.0, 0.4))
            novelty = float(np.clip(0.8 * intensity, 0.0, 1.0))
        elif kind in ("hazard", "danger"):
            energy_value = 0.0
            danger = float(np.clip(0.6 * intensity, 0.6, 0.9))
            utility = 0.0
            novelty = float(np.clip(0.8 * intensity, 0.0, 1.0))
        elif kind == "tool":
            energy_value = float(np.clip(1.0 * intensity, 0.0, 2.0))
            danger = float(np.clip(0.1 * intensity, 0.0, 0.2))
            utility = float(np.clip(0.8 * intensity, 0.6, 1.0))
            novelty = float(np.clip(0.7 * intensity, 0.0, 1.0))
        else:  # curio (or unknown kind treated as inert novelty)
            energy_value = 0.0
            danger = float(np.clip(0.05 * intensity, 0.0, 0.1))
            utility = float(np.clip(0.1 * intensity, 0.0, 0.2))
            novelty = float(np.clip(0.9 * intensity, 0.8, 1.0))

        if x is None or y is None:
            px, py = self._free_cell_near_agent()
        else:
            g = self.config.grid_size
            px = int(np.clip(int(x), 0, g - 1))
            py = int(np.clip(int(y), 0, g - 1))

        obj = WorldObject(
            id=self._next_id,
            kind=kind,
            x=px,
            y=py,
            energy_value=round(energy_value, 4),
            danger=round(danger, 4),
            novelty=round(novelty, 4),
            utility=round(utility, 4),
        )
        self.objects[obj.id] = obj
        self.seen_counts[obj.id] = 0
        self._spawn_meta[obj.id] = {"max_energy": float(energy_value),
                                    "base_danger": float(danger)}
        self._next_id += 1
        return obj

    def _free_cell_near_agent(self) -> tuple[int, int]:
        """Return a free cell adjacent to the agent (else the agent's own cell)."""
        g = self.config.grid_size
        occupied = {(o.x, o.y) for o in self.objects.values()}
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = int(np.clip(self.agent_x + dx, 0, g - 1))
                ny = int(np.clip(self.agent_y + dy, 0, g - 1))
                if (nx, ny) not in occupied:
                    return nx, ny
        return int(self.agent_x), int(self.agent_y)

    # ----------------------------------------------------------- perception
    def observe(self) -> Observation:
        """Return objects within Chebyshev radius, with noisy sensor readings.

        Gaussian jitter (scaled by ``world_noise``) is applied to the
        danger/novelty/utility *readings* only; stored objects are not mutated.
        """
        cfg = self.config
        radius = cfg.perception_radius
        noise = cfg.world_noise
        visible: list[WorldObject] = []
        for obj in self.objects.values():
            cheb = max(abs(obj.x - self.agent_x), abs(obj.y - self.agent_y))
            if cheb <= radius:
                if noise > 0.0:
                    danger = self._jitter(obj.danger, noise)
                    novelty = self._jitter(obj.novelty, noise)
                    utility = self._jitter(obj.utility, noise)
                else:
                    danger, novelty, utility = obj.danger, obj.novelty, obj.utility
                visible.append(
                    WorldObject(
                        id=obj.id,
                        kind=obj.kind,
                        x=obj.x,
                        y=obj.y,
                        energy_value=obj.energy_value,
                        danger=danger,
                        novelty=novelty,
                        utility=utility,
                    )
                )
        return Observation(
            tick=self.tick,
            agent_x=self.agent_x,
            agent_y=self.agent_y,
            agent_energy=round(float(self.agent_energy), 4),
            radius=radius,
            visible=visible,
        )

    def _jitter(self, value: float, noise: float) -> float:
        """Apply gaussian noise to a 0..1 reading and clip back into range."""
        jittered = value + float(self.rng.normal(0.0, noise))
        return round(float(np.clip(jittered, 0.0, 1.0)), 4)

    # --------------------------------------------------------------- dynamics
    def step(self, decision: ActionDecision) -> StepResult:
        """Apply one action, mutate world state, and return the outcome.

        Energy bookkeeping, movement, interaction effects, novelty decay, and
        stochastic world events are all resolved here. ``actual`` reports what
        was experienced this tick for the world-model error signal.
        """
        cfg = self.config
        action = decision.action
        events: list[str] = []
        start_energy = float(self.agent_energy)
        self._last_ate_food = False

        # 1) Fixed costs: action cost + passive decay.
        cost = ACTION_COSTS.get(action.value, 0.0)
        self.agent_energy -= cost + PASSIVE_ENERGY_DECAY

        # Per-tick "actual" channels experienced by the agent.
        actual_danger = 0.0
        actual_novelty = 0.0
        actual_energy_value = 0.0
        actual_utility = 0.0
        goal_progress = 0.0

        target = self.objects.get(decision.target_id) if decision.target_id is not None else None

        # 2) Resolve action-specific effects.
        if action in _MOVEMENT_ACTIONS:
            moved = self._apply_movement(action, decision, target, events)
            if moved and target is not None:
                # Approaching a useful/energetic object counts as goal progress.
                if action == ActionType.APPROACH:
                    goal_progress += 0.2 * (target.utility + min(target.energy_value / 10.0, 1.0))
                if action == ActionType.AVOID:
                    goal_progress += 0.1 * target.danger
        elif action == ActionType.INTERACT:
            consumed_energy = target.energy_value if target is not None else 0.0
            consumed_utility = target.utility if target is not None else 0.0
            goal_progress += self._apply_interact(
                target, events
            )
            if target is not None:
                actual_energy_value = consumed_energy
                actual_danger = target.danger
                actual_utility = consumed_utility
                actual_novelty = target.novelty
        elif action == ActionType.REST:
            self.agent_energy += REST_RECOVERY
            events.append("The agent rests and regains energy.")
        elif action in (ActionType.OBSERVE, ActionType.ANALYZE):
            actual_novelty = self._apply_reveal(target, events)
            if target is not None:
                actual_danger = target.danger
                actual_utility = target.utility
        elif action == ActionType.VERBALIZE:
            events.append("The agent verbalizes an internal report (neutral for the world).")

        # 3) Energy gained this tick contributes to goal progress.
        # 4) Stochastic world events governed by world_noise.
        self._maybe_random_event(events)

        # Phase 7 (gated) — structured task scoring on the resolved step.
        if self.task_manager is not None:
            goal_progress += self.task_manager.on_step(
                action=action, events=events,
                agent_x=self.agent_x, agent_y=self.agent_y,
                ate_food=self._last_ate_food)
            self.task_manager.tick_task()

        # 5) Clamp energy.
        self.agent_energy = float(np.clip(self.agent_energy, 0.0, self._energy_cap()))

        energy_delta = float(self.agent_energy) - start_energy
        if energy_delta > 0.0:
            goal_progress += min(energy_delta / 10.0, 1.0)

        # 6) Advance time.
        self.tick += 1

        # Phase 7 (gated) — continuous dynamics: regrowth, hazard cycles, drift.
        # Pure functions of (tick, id, spawn metadata): consumes no RNG.
        if cfg.world_dynamics_enabled:
            events.extend(apply_dynamics(
                self.objects, getattr(self, "_spawn_meta", {}),
                self.tick, cfg, DRIFT_EVERY))

        actual = {
            "danger": round(float(np.clip(actual_danger, 0.0, 1.0)), 4),
            "novelty": round(float(np.clip(actual_novelty, 0.0, 1.0)), 4),
            "goal_progress": round(float(goal_progress), 4),
            "energy_value": round(float(actual_energy_value), 4),
            "utility": round(float(np.clip(actual_utility, 0.0, 1.0)), 4),
        }
        return StepResult(
            tick=self.tick,
            action=action,
            target_id=decision.target_id,
            energy_delta=round(energy_delta, 4),
            new_energy=round(float(self.agent_energy), 4),
            events=events,
            actual=actual,
        )

    def _apply_movement(
        self,
        action: ActionType,
        decision: ActionDecision,
        target: WorldObject | None,
        events: list[str],
    ) -> bool:
        """Move the agent one cell; clamp to grid. Returns True if it moved."""
        dx, dy = 0, 0
        if action == ActionType.APPROACH and target is not None:
            dx = self._sign(target.x - self.agent_x)
            dy = self._sign(target.y - self.agent_y)
            events.append(f"The agent approaches object {target.id} ({target.kind}).")
        elif action == ActionType.AVOID and target is not None:
            dx = -self._sign(target.x - self.agent_x)
            dy = -self._sign(target.y - self.agent_y)
            events.append(f"The agent moves away from object {target.id} ({target.kind}).")
        elif decision.direction is not None and len(decision.direction) == 2:
            dx = self._clamp_step(int(decision.direction[0]))
            dy = self._clamp_step(int(decision.direction[1]))
            events.append("The agent moves in the chosen direction.")
        else:
            # MOVE/EXPLORE without an explicit direction: head toward the most
            # novel / least-explored cell heuristically (a nearby novel object,
            # else a random step).
            dx, dy = self._explore_direction()
            events.append("The agent explores toward a less familiar area.")

        new_x = int(np.clip(self.agent_x + dx, 0, self.config.grid_size - 1))
        new_y = int(np.clip(self.agent_y + dy, 0, self.config.grid_size - 1))
        moved = (new_x, new_y) != (self.agent_x, self.agent_y)
        self.agent_x, self.agent_y = new_x, new_y
        return moved

    def _explore_direction(self) -> tuple[int, int]:
        """Heuristic step toward the nearest novel/unexplored object, else random."""
        best: WorldObject | None = None
        best_score = -1.0
        for obj in self.objects.values():
            seen = self.seen_counts.get(obj.id, 0)
            # Favor high novelty and low familiarity.
            score = obj.novelty / (1.0 + seen)
            if score > best_score:
                best_score = score
                best = obj
        if best is not None and (best.x, best.y) != (self.agent_x, self.agent_y):
            return self._sign(best.x - self.agent_x), self._sign(best.y - self.agent_y)
        # Fall back to a deterministic random step.
        dx = int(self.rng.integers(-1, 2))
        dy = int(self.rng.integers(-1, 2))
        return dx, dy

    def _apply_interact(self, target: WorldObject | None, events: list[str]) -> float:
        """Resolve INTERACT against ``target`` if the agent is on/adjacent to it.

        Gains the object's energy, takes danger damage, decays its novelty, and
        consumes food objects. Returns the goal-progress contribution.
        """
        if target is None:
            events.append("The agent tries to interact but no target is defined.")
            return 0.0
        cheb = max(abs(target.x - self.agent_x), abs(target.y - self.agent_y))
        if cheb > 1:
            events.append(
                f"Interaction ineffective: object {target.id} is too far away."
            )
            return 0.0

        goal_progress = 0.0
        if target.energy_value > 0.0:
            self.agent_energy += target.energy_value
            goal_progress += min(target.energy_value / 10.0, 1.0)
            events.append(
                f"The agent interacts with object {target.id} ({target.kind}) "
                f"and gains {target.energy_value:.1f} energy."
            )
        if target.danger > 0.0:
            damage = target.danger * INTERACT_DANGER_DAMAGE
            self.agent_energy -= damage
            events.append(
                f"Object {target.id} ({target.kind}) inflicts {damage:.1f} damage."
            )
        if target.utility > 0.0:
            goal_progress += 0.3 * target.utility

        # Novelty decays through interaction.
        target.novelty = round(float(max(0.0, target.novelty - NOVELTY_DECAY_ON_INTERACT)), 4)
        self.seen_counts[target.id] = self.seen_counts.get(target.id, 0) + 1

        # Food is consumed once eaten. Under Phase-7 continuous dynamics the
        # patch stays in place, depleted, and regrows toward its spawn maximum;
        # otherwise (prior-phase behaviour) the object disappears outright.
        if target.kind == "food" and target.energy_value > 0.0:
            self._last_ate_food = True
            if self.config.world_dynamics_enabled:
                target.energy_value = 0.0
                target.utility = round(float(target.utility * 0.5), 4)
                events.append(f"Food patch {target.id} is grazed down (it will regrow).")
            else:
                self.objects.pop(target.id, None)
                self.seen_counts.pop(target.id, None)
                self._spawn_meta.pop(target.id, None)
                events.append(f"Food {target.id} is consumed and disappears.")
        return goal_progress

    def _apply_reveal(self, target: WorldObject | None, events: list[str]) -> float:
        """OBSERVE/ANALYZE: reveal a target, decay its novelty, return that novelty."""
        if target is None:
            events.append("The agent observes its environment.")
            return 0.0
        prior_novelty = float(target.novelty)
        target.novelty = round(float(max(0.0, target.novelty - NOVELTY_DECAY_ON_SEE)), 4)
        self.seen_counts[target.id] = self.seen_counts.get(target.id, 0) + 1
        events.append(
            f"The agent examines object {target.id} ({target.kind})."
        )
        return prior_novelty

    def _maybe_random_event(self, events: list[str]) -> None:
        """Occasionally spawn a new object or flare a hazard's danger.

        Frequency scales with ``world_noise`` and is driven by the seeded RNG so
        the world stays deterministic.
        """
        noise = self.config.world_noise
        if noise <= 0.0:
            return
        # Phase 7 (gated) — seasonal abundance modulates spawn probability and
        # the richness of newly spawned food (same number of RNG draws either way).
        season = (season_factor(self.tick, self.config.season_period)
                  if self.config.world_dynamics_enabled else 1.0)
        # Spawn probability and flare probability both scale with noise.
        if float(self.rng.random()) < noise * 0.25 * season:
            obj = self._spawn_object()
            if self.config.world_dynamics_enabled and obj.kind == "food":
                obj.energy_value = round(float(min(10.0, obj.energy_value * season)), 4)
                self._spawn_meta[obj.id]["max_energy"] = float(obj.energy_value)
            events.append(
                f"A new object {obj.id} ({obj.kind}) appears in the world."
            )
        if float(self.rng.random()) < noise * 0.25:
            hazards = [o for o in self.objects.values() if o.kind == "hazard"]
            if hazards:
                idx = int(self.rng.integers(0, len(hazards)))
                hz = hazards[idx]
                hz.danger = round(float(min(1.0, hz.danger + float(self.rng.uniform(0.05, 0.2)))), 4)
                events.append(
                    f"The danger level of object {hz.id} (hazard) suddenly increases."
                )

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _sign(value: int) -> int:
        """Return the step direction (-1, 0, 1) for an axis delta."""
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    @staticmethod
    def _clamp_step(value: int) -> int:
        """Clamp a direction component to {-1, 0, 1}."""
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    # ----------------------------------------------------------- lifecycle
    def reset(self) -> None:
        """Rebuild the world from the stored config (re-seeds the RNG)."""
        self._build()

    def set_config(self, config: SimConfig) -> None:
        """Replace the config and rebuild the world."""
        self.config = config
        self._build()

    def snapshot(self) -> dict:
        """Return a JSON-serializable view of the world for UI/state."""
        snap = {
            "grid_size": int(self.config.grid_size),
            "tick": int(self.tick),
            "agent": {
                "x": int(self.agent_x),
                "y": int(self.agent_y),
                "energy": round(float(self.agent_energy), 4),
            },
            "objects": [obj.model_dump() for obj in self.objects.values()],
        }
        # Phase 7 (gated) — environment extras for the UI (absent when off).
        if self.config.world_dynamics_enabled:
            snap["season"] = round(float(
                season_factor(self.tick, self.config.season_period)), 4)
        if self.task_manager is not None:
            snap["task"] = self.task_manager.state().model_dump()
        return snap

    def task_state(self):
        """Current TaskState, or ``None`` when the task system is off."""
        return self.task_manager.state() if self.task_manager is not None else None
