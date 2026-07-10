# tests/test_planning.py
"""Unit tests for core/planning.py — Phase 7 policy-tree search over EFE."""
from __future__ import annotations

from types import SimpleNamespace

from core.planning import _MAX_POLICIES, Planner
from core.world_model import WorldModel
from schemas.models import ActionType, Observation, Percept, SimConfig


def _config(horizon: int = 3) -> SimConfig:
    """A SimConfig with planning enabled and a fixed horizon/discount."""
    return SimConfig(planning_enabled=True, planning_horizon=horizon,
                     planning_discount=0.7)


def _obs(energy: float = 100.0) -> Observation:
    """A minimal observation (the planner never touches `visible` directly)."""
    return Observation(tick=0, agent_x=5, agent_y=5, agent_energy=energy,
                       radius=3, visible=[])


def _food(dx: int = 3, energy_value: float = 10.0) -> Percept:
    """A nutritious, safe food percept `dx` cells away on the x axis."""
    return Percept(object_id=1, kind="food", dx=dx, dy=0, distance=float(abs(dx)),
                   danger=0.0, novelty=0.4, utility=0.5, energy_value=energy_value)


def _far_food_candidates(food: Percept) -> list[tuple[ActionType, Percept | None]]:
    """A realistic candidate set around a distant food object."""
    return [
        (ActionType.APPROACH, food),
        (ActionType.INTERACT, food),
        (ActionType.OBSERVE, food),
        (ActionType.EXPLORE, None),
        (ActionType.REST, None),
    ]


def test_tree_beats_greedy_approach_before_interact() -> None:
    """Food 3 cells away: greedy picks INTERACT, the tree starts with APPROACH."""
    config = _config(horizon=3)
    wm = WorldModel(config)
    food = _food(dx=3)
    candidates = _far_food_candidates(food)

    # Greedy (imagination-style) argmax over raw one-step predictions picks the
    # out-of-range INTERACT because the prediction is grounded in the percept.
    preds = [(wm.predict(_obs(), a, t).value, a) for a, t in candidates]
    greedy_action = max(preds, key=lambda p: p[0])[1]
    assert greedy_action == ActionType.INTERACT

    state = Planner().plan(wm, _obs(), candidates, current_energy=100.0,
                           initial_energy=100.0, config=config)
    assert state.chosen_first == "approach"
    assert state.best_sequence[0] == "approach"
    # The winning policy actually reaches and consumes the food.
    assert "interact" in state.best_sequence
    # Positive discounted value => negative best EFE.
    assert state.best_efe < 0.0
    assert "not deliberation" in state.report


def test_horizon_respected() -> None:
    """The best sequence has exactly planning_horizon steps."""
    for horizon in (2, 3, 4):
        config = _config(horizon=horizon)
        wm = WorldModel(config)
        state = Planner().plan(wm, _obs(), _far_food_candidates(_food()),
                               current_energy=100.0, initial_energy=100.0,
                               config=config)
        assert state.horizon == horizon
        assert len(state.best_sequence) == horizon


def test_low_energy_plans_rest() -> None:
    """Low energy and nothing valuable nearby: REST appears in the best plan."""
    config = _config(horizon=3)
    wm = WorldModel(config)
    candidates: list[tuple[ActionType, Percept | None]] = [
        (ActionType.REST, None),
        (ActionType.OBSERVE, None),
        (ActionType.EXPLORE, None),
    ]
    state = Planner().plan(wm, _obs(energy=15.0), candidates,
                           current_energy=15.0, initial_energy=100.0,
                           config=config)
    assert "rest" in state.best_sequence
    assert state.chosen_first == "rest"


def test_determinism_same_inputs_same_plan() -> None:
    """Two identical calls return byte-identical PlanningStates."""
    config = _config(horizon=3)
    wm = WorldModel(config)
    food = _food(dx=3)
    kwargs = dict(current_energy=80.0, initial_energy=100.0, config=config)
    a = Planner().plan(wm, _obs(80.0), _far_food_candidates(food), **kwargs)
    b = Planner().plan(wm, _obs(80.0), _far_food_candidates(food), **kwargs)
    assert a.model_dump() == b.model_dump()


def test_n_policies_positive_and_bounded() -> None:
    """The number of complete sequences is positive and honors the hard cap."""
    for horizon in (2, 3, 4):
        config = _config(horizon=horizon)
        wm = WorldModel(config)
        state = Planner().plan(wm, _obs(), _far_food_candidates(_food()),
                               current_energy=100.0, initial_energy=100.0,
                               config=config)
        assert state.n_policies > 0
        assert state.n_policies <= _MAX_POLICIES


def test_horizon_four_cap_gives_every_ranked_root_a_path_to_win() -> None:
    """A cap must not starve later roots, including the fourth-ranked root."""
    targets = [
        Percept(object_id=i, kind="food", dx=5, dy=0, distance=5.0,
                danger=0.0, novelty=0.1, utility=0.1, energy_value=1.0)
        for i in range(1, 5)
    ]
    candidates = [
        (ActionType.OBSERVE, targets[0]),
        (ActionType.ANALYZE, targets[1]),
        (ActionType.APPROACH, targets[2]),
        (ActionType.AVOID, targets[3]),
    ]
    first_actions = [action.value for action, _ in candidates]

    class RankedRootsModel:
        def predict(self, observation, action, target):
            del observation, action
            # Root rank is 1 > 2 > 3 > 4. Deep scoring is supplied below.
            return SimpleNamespace(value=5.0 - float(target.object_id))

    class FutureRewardPlanner(Planner):
        def __init__(self, winning_root: int) -> None:
            self.winning_root = winning_root

        def _step(self, world_model, observation, action, target, state,
                  denom, cap, cache):
            del world_model, observation, action, target, denom, cap, cache
            root_id = state.target.object_id
            score = 10.0 if root_id == self.winning_root else 0.0
            return score, state

    config = _config(horizon=4)
    for winning_root in range(1, 5):
        state = FutureRewardPlanner(winning_root).plan(
            RankedRootsModel(), _obs(), candidates,
            current_energy=100.0, initial_energy=100.0, config=config,
        )
        assert state.n_policies == _MAX_POLICIES
        assert state.chosen_first == first_actions[winning_root - 1]


def test_empty_candidates_neutral_state() -> None:
    """No candidates: a neutral PlanningState, no crash."""
    config = _config(horizon=3)
    wm = WorldModel(config)
    state = Planner().plan(wm, _obs(), [], current_energy=100.0,
                           initial_energy=100.0, config=config)
    assert state.best_sequence == []
    assert state.chosen_first is None
    assert state.n_policies == 0
    assert state.best_efe == 0.0
    assert state.horizon == 3
    assert "not conscious" in state.report
