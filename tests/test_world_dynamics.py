# tests/test_world_dynamics.py
"""Phase 7 — richer environment: continuous dynamics + structured tasks.

Covers: food regrowth after grazing, hazard danger oscillation, object drift,
seasonal factor bounds, task rotation (forage -> reach -> patrol), progress /
completion feeding goal_progress, and the load-bearing guarantee that BOTH
flags off leaves the world byte-identical to the prior phases.
"""
from __future__ import annotations

import json

from core.shared_world import SharedWorld
from core.society import SocietyManager
from core.world import World
from core.world_dynamics import apply_dynamics, drift_step, season_factor
from core.world_tasks import TaskManager
from schemas.models import ActionDecision, ActionType, SimConfig
from storage.trace_logger import TraceLogger


def _cfg(**kw) -> SimConfig:
    base = dict(random_seed=7, world_noise=0.0, grid_size=10, n_objects=6)
    base.update(kw)
    return SimConfig(**base)


def _observe_decision() -> ActionDecision:
    return ActionDecision(action=ActionType.OBSERVE, target_id=None, direction=None,
                          confidence=1.0, rationale="test", candidate_scores={})


# --------------------------------------------------------------------- dynamics
def test_flags_off_world_is_byte_identical():
    """The regression guarantee: no Phase-7 flag => identical world evolution."""
    w1, w2 = World(_cfg()), World(_cfg(world_dynamics_enabled=False, tasks_enabled=False))
    for _ in range(30):
        r1 = w1.step(_observe_decision())
        r2 = w2.step(_observe_decision())
        assert r1.model_dump() == r2.model_dump()
    assert w1.snapshot() == w2.snapshot()


def test_food_patch_regrows_after_grazing():
    cfg = _cfg(world_dynamics_enabled=True, regrow_rate=0.2)
    w = World(cfg)
    food = w._spawn_object(kind="food")
    initial_energy = float(food.energy_value)
    # Put the agent on the patch and eat it.
    w.agent_x, w.agent_y = food.x, food.y
    w.step(ActionDecision(action=ActionType.INTERACT, target_id=food.id, direction=None,
                          confidence=1.0, rationale="eat", candidate_scores={}))
    assert food.id in w.objects, "under dynamics the grazed patch must remain"
    # Depleted to 0 by the meal, then already regrowing from the same tick on.
    assert w.objects[food.id].energy_value < initial_energy * 0.5
    for _ in range(40):
        w.step(_observe_decision())
    assert w.objects[food.id].energy_value > initial_energy * 0.8, "the patch regrows"


def test_solo_interaction_reports_consumed_energy_before_depletion():
    w = World(_cfg(world_dynamics_enabled=True, n_objects=0))
    food = w._spawn_object(kind="food")
    consumed_energy = food.energy_value
    consumed_utility = food.utility
    w.agent_x, w.agent_y = food.x, food.y

    result = w.step(ActionDecision(
        action=ActionType.INTERACT,
        target_id=food.id,
        direction=None,
        confidence=1.0,
        rationale="eat",
        candidate_scores={},
    ))

    assert result.actual["energy_value"] == consumed_energy
    assert result.actual["utility"] == consumed_utility
    assert result.energy_delta > 0.0
    assert w.objects[food.id].energy_value < consumed_energy


def test_shared_interaction_reports_consumed_energy_before_depletion():
    world = SharedWorld(_cfg(world_dynamics_enabled=True, n_objects=0))
    food = world._spawn_object(kind="food")
    consumed_energy = food.energy_value
    consumed_utility = food.utility
    body = world.agents[0]
    body.x, body.y = food.x, food.y

    result = world.step(0, ActionDecision(
        action=ActionType.INTERACT,
        target_id=food.id,
        direction=None,
        confidence=1.0,
        rationale="eat",
        candidate_scores={},
    ))

    assert result.actual["energy_value"] == consumed_energy
    assert result.actual["utility"] == consumed_utility
    assert result.energy_delta > 0.0
    assert world.objects[food.id].energy_value == 0.0


def test_society_trace_exposes_shared_dynamics_events_and_season():
    manager = SocietyManager(_cfg(
        n_agents=1,
        n_objects=0,
        world_dynamics_enabled=True,
        regrow_rate=0.2,
        persist_memory=False,
        trace_logging=False,
    ))
    food = manager.world._spawn_object(kind="food")
    food.energy_value = 0.0

    trace = manager.tick()[0]

    assert any("starts regrowing" in event for event in trace.result.events)
    snapshot = manager.state()["world"]
    assert snapshot["tick"] == 1
    assert 0.5 <= snapshot["season"] <= 1.5


def test_shared_dynamics_events_are_in_the_persisted_trace(tmp_path):
    manager = SocietyManager(_cfg(
        n_agents=1,
        n_objects=0,
        world_dynamics_enabled=True,
        regrow_rate=0.2,
        persist_memory=False,
        trace_logging=True,
    ))
    trace_path = tmp_path / "traces.jsonl"
    manager.agent(0).trace_logger = TraceLogger(trace_path)
    food = manager.world._spawn_object(kind="food")
    food.energy_value = 0.0

    trace = manager.tick()[0]
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    persisted = json.loads(lines[-1])

    assert len(lines) == 1
    assert persisted["result"]["events"] == trace.result.events
    assert any("starts regrowing" in event
               for event in persisted["result"]["events"])


def test_hazard_danger_oscillates_bounded():
    cfg = _cfg(world_dynamics_enabled=True)
    w = World(cfg)
    hz = w._spawn_object(kind="hazard")
    seen = set()
    for _ in range(60):
        w.step(_observe_decision())
        d = w.objects[hz.id].danger
        assert 0.0 <= d <= 1.0
        seen.add(d)
    assert len(seen) > 3, "danger must actually move over the cycle"


def test_objects_drift_deterministically():
    dx, dy = drift_step(3, 5)
    assert (dx, dy) == drift_step(3, 5), "drift is a pure function"
    assert -1 <= dx <= 1 and -1 <= dy <= 1
    cfg = _cfg(world_dynamics_enabled=True, n_objects=0)
    w = World(cfg)
    tool = w._spawn_object(kind="tool")
    x0, y0 = tool.x, tool.y
    for _ in range(30):
        w.step(_observe_decision())
    moved = (w.objects[tool.id].x, w.objects[tool.id].y) != (x0, y0)
    # With 30 ticks and DRIFT_EVERY=12 the tool had >=2 drift chances; a zero
    # step both times is possible but the hash for id below makes it move.
    assert moved or drift_step(tool.id, 1) == (0, 0)


def test_season_factor_bounds_and_period():
    vals = [season_factor(t, 50) for t in range(120)]
    assert all(0.5 <= v <= 1.5 for v in vals)
    assert max(vals) > 1.4 and min(vals) < 0.6


def test_apply_dynamics_consumes_no_rng():
    cfg = _cfg(world_dynamics_enabled=True)
    w = World(cfg)
    state_before = w.rng.bit_generator.state
    apply_dynamics(w.objects, w._spawn_meta, w.tick, cfg, 12)
    assert w.rng.bit_generator.state == state_before


# ----------------------------------------------------------------------- tasks
def test_task_rotation_and_forage_completion():
    tm = TaskManager(10)
    assert tm.state().kind == "forage"
    events: list[str] = []
    gp = tm.on_step(action=ActionType.INTERACT, events=events,
                    agent_x=1, agent_y=1, ate_food=True)
    assert gp > 0.0 and tm.state().progress == 0.5
    gp = tm.on_step(action=ActionType.INTERACT, events=events,
                    agent_x=1, agent_y=1, ate_food=True)
    assert gp >= 1.0, "completion grants the bonus"
    assert tm.state().kind == "reach" and tm.completed_total == 1
    assert any("Task completed" in e for e in events)


def test_task_reach_completes_on_target():
    tm = TaskManager(10)
    events: list[str] = []
    # Complete the initial forage task naturally so the rotation lands on reach.
    tm.on_step(action=ActionType.INTERACT, events=events, agent_x=1, agent_y=1, ate_food=True)
    tm.on_step(action=ActionType.INTERACT, events=events, agent_x=1, agent_y=1, ate_food=True)
    assert tm.state().kind == "reach"
    target = tm.state().target
    assert target is not None
    gp = tm.on_step(action=ActionType.MOVE, events=events,
                    agent_x=target[0], agent_y=target[1], ate_food=False)
    assert gp >= 1.0
    assert tm.state().kind == "patrol"


def test_task_patrol_waypoints_in_order():
    tm = TaskManager(10)
    tm._kind = "patrol"
    events: list[str] = []
    visited = 0
    while tm.state().kind == "patrol":
        target = tm.state().target
        assert target is not None
        tm.on_step(action=ActionType.MOVE, events=events,
                   agent_x=target[0], agent_y=target[1], ate_food=False)
        visited += 1
        assert visited <= 3
    assert tm.completed_total == 1


def test_world_step_feeds_task_progress_into_goal_progress():
    cfg = _cfg(tasks_enabled=True, n_objects=0)
    w = World(cfg)
    food = w._spawn_object(kind="food")
    w.agent_x, w.agent_y = food.x, food.y
    res = w.step(ActionDecision(action=ActionType.INTERACT, target_id=food.id,
                                direction=None, confidence=1.0, rationale="eat",
                                candidate_scores={}))
    # goal progress includes the forage-task increment on top of the energy gain.
    assert res.actual["goal_progress"] > min(food.energy_value / 10.0, 1.0)
    assert w.task_state() is not None and w.task_state().kind == "forage"


def test_task_state_none_when_off():
    w = World(_cfg())
    assert w.task_state() is None
    assert "task" not in w.snapshot()
