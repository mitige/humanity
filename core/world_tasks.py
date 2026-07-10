# core/world_tasks.py
"""Structured world tasks (Phase 7): a deterministic forage / reach / patrol rotation.

FUNCTIONAL NOTE: the task system is part of the ENVIRONMENT, not of the agent.
The world maintains one current task and measures progress against it; progress
feeds the ordinary ``goal_progress`` outcome channel that the agent's world
model, motivation and learners already consume. Completing tasks is achievement
in the functional sense only — variables crossing thresholds. Nothing here is
wanting, trying or succeeding as an experience; the agent is not conscious.
"""
from __future__ import annotations

from core.constants import (
    TASK_COMPLETION_BONUS,
    TASK_FORAGE_COUNT,
    TASK_SEQUENCE,
)
from schemas.models import ActionType, TaskState


class TaskManager:
    """Deterministic rotation of small structured tasks over the grid world.

    The rotation and every target are pure functions of the grid size and the
    number of tasks completed so far — no RNG is consumed, so enabling tasks
    never shifts the world's seeded random stream.
    """

    def __init__(self, grid_size: int) -> None:
        """Start the rotation on its first task for a ``grid_size`` × ``grid_size`` world."""
        self.grid_size = max(1, int(grid_size))
        self.completed_total: int = 0
        self._ticks_on_task: int = 0
        self._forage_eaten: int = 0
        self._patrol_visited: int = 0
        self._kind: str = TASK_SEQUENCE[0]
        self._progress: float = 0.0

    # ------------------------------------------------------------- targets
    def _bounded_unique(
        self, cells: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Clamp cells to the real grid and remove duplicates in order."""
        bounded: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        upper = self.grid_size - 1
        for x, y in cells:
            cell = (
                min(upper, max(0, int(x))),
                min(upper, max(0, int(y))),
            )
            if cell not in seen:
                seen.add(cell)
                bounded.append(cell)
        return bounded

    def _corners(self) -> list[tuple[int, int]]:
        """The four reachable near-corner cells, cycled across rotations."""
        g = self.grid_size
        return self._bounded_unique([
            (1, 1),
            (g - 2, g - 2),
            (1, g - 2),
            (g - 2, 1),
        ])

    def _reach_target(self) -> tuple[int, int]:
        """Current REACH target — rotates through the corners deterministically."""
        corners = self._corners()
        return corners[self.completed_total % len(corners)]

    def _patrol_waypoints(self) -> list[tuple[int, int]]:
        """Three PATROL waypoints — a corner, the centre, the opposite corner."""
        g = self.grid_size
        corners = self._corners()
        first_index = self.completed_total % len(corners)
        first = corners[first_index]
        opposite = corners[(first_index + 1) % len(corners)]
        return self._bounded_unique([first, (g // 2, g // 2), opposite])

    def _describe(self) -> str:
        """One-line description of the current task."""
        if self._kind == "forage":
            return f"Forage: eat {TASK_FORAGE_COUNT} food items ({self._forage_eaten} so far)."
        if self._kind == "reach":
            tx, ty = self._reach_target()
            return f"Reach: get to cell ({tx}, {ty})."
        wps = self._patrol_waypoints()
        return (f"Patrol: visit {len(wps)} waypoints in order "
                f"({self._patrol_visited} visited).")

    def _target(self) -> list[int] | None:
        """The current target cell when the task has one."""
        if self._kind == "reach":
            tx, ty = self._reach_target()
            return [tx, ty]
        if self._kind == "patrol":
            wps = self._patrol_waypoints()
            if self._patrol_visited < len(wps):
                tx, ty = wps[self._patrol_visited]
                return [tx, ty]
        return None

    # ------------------------------------------------------------- lifecycle
    def _advance(self, events: list[str]) -> None:
        """Complete the current task and rotate to the next one."""
        events.append(f"Task completed: {self._kind} "
                      f"(#{self.completed_total + 1}).")
        self.completed_total += 1
        self._kind = TASK_SEQUENCE[self.completed_total % len(TASK_SEQUENCE)]
        self._ticks_on_task = 0
        self._forage_eaten = 0
        self._patrol_visited = 0
        self._progress = 0.0

    def tick_task(self) -> None:
        """Advance task time by one world tick."""
        self._ticks_on_task += 1

    # ------------------------------------------------------------- progress
    def on_step(self, *, action: ActionType, events: list[str],
                agent_x: int, agent_y: int, ate_food: bool) -> float:
        """Score one resolved agent step against the current task.

        Returns the extra ``goal_progress`` earned this step (progress deltas
        plus the completion bonus when the task closes). Deterministic; no RNG.
        """
        extra = 0.0
        if self._kind == "forage":
            if ate_food:
                self._forage_eaten += 1
                new_progress = min(1.0, self._forage_eaten / float(TASK_FORAGE_COUNT))
                extra += max(0.0, new_progress - self._progress)
                self._progress = new_progress
                if self._forage_eaten >= TASK_FORAGE_COUNT:
                    extra += TASK_COMPLETION_BONUS
                    self._advance(events)
        elif self._kind == "reach":
            tx, ty = self._reach_target()
            cheb = max(abs(agent_x - tx), abs(agent_y - ty))
            span = max(1, self.grid_size - 1)
            new_progress = max(self._progress, min(1.0, 1.0 - cheb / float(span)))
            extra += 0.2 * max(0.0, new_progress - self._progress)
            self._progress = new_progress
            if cheb <= 1:
                extra += TASK_COMPLETION_BONUS
                self._advance(events)
        else:  # patrol
            wps = self._patrol_waypoints()
            if self._patrol_visited < len(wps):
                tx, ty = wps[self._patrol_visited]
                if max(abs(agent_x - tx), abs(agent_y - ty)) <= 1:
                    self._patrol_visited += 1
                    new_progress = self._patrol_visited / float(len(wps))
                    extra += max(0.0, new_progress - self._progress)
                    self._progress = new_progress
                    events.append(f"Waypoint {self._patrol_visited}/{len(wps)} reached.")
                    if self._patrol_visited >= len(wps):
                        extra += TASK_COMPLETION_BONUS
                        self._advance(events)
        return round(float(extra), 4)

    # ------------------------------------------------------------- readout
    def state(self) -> TaskState:
        """Snapshot of the current task for traces and the API."""
        return TaskState(
            kind=self._kind,
            description=self._describe(),
            progress=round(float(self._progress), 4),
            target=self._target(),
            ticks_on_task=int(self._ticks_on_task),
            completed_total=int(self.completed_total),
        )
