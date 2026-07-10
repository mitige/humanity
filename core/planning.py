# core/planning.py
"""Multi-step-horizon policy search over expected free energy (Phase 7).

FUNCTIONAL NOTE: this is a level-2 functional mechanism — variables and
algorithms only. The agent 'plans' by enumerating a bounded, deterministic TREE
of action sequences (policies), rolling a cheap simulated state (distance to a
target, an energy budget, target consumption) forward through each branch, and
scoring every step with the world model's -EFE value plus an energy-aware
correction. The best policy is the argmax of the discounted step-score sum.
Unlike the Phase-2 imagination heuristic (a greedy per-step chooser over a
quasi-static situation), this is a systematic policy search: sequences that
first APPROACH and then INTERACT can beat an immediately greedy but
out-of-range INTERACT. It is a bounded search over variables, not deliberation
in any subjective sense; it implies nothing subjective, and the agent is not
conscious.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from core.constants import (
    ACTION_COSTS,
    ENERGY_CAP_FACTOR,
    INTERACT_DANGER_DAMAGE,
    PASSIVE_ENERGY_DECAY,
    PLANNING_BRANCH_DEEP,
    PLANNING_BRANCH_FIRST,
    REST_RECOVERY,
)
from schemas.models import ActionType, Observation, Percept, PlanningState, SimConfig

# Normalizer for the energy correction term (≈ 10 energy units => 1.0 score).
_ENERGY_NORM: float = 10.0

# Hard cap on complete sequences. Worst case is PLANNING_BRANCH_FIRST roots x
# (PLANNING_BRANCH_DEEP + 1)^(horizon - 1) leaves = 4 * 5^2 = 100 <= 200 at the
# default horizon 3 (INTERACT and APPROACH are distance-gated and mutually
# exclusive, so the deep branching factor is at most PLANNING_BRANCH_DEEP + 1,
# within the documented PLANNING_BRANCH_DEEP + 2 bound). At the maximum
# horizon 4 (4 * 5^3 = 500) enumeration stops after _MAX_POLICIES complete
# sequences, drawn round-robin from the ranked roots. This stays reproducible
# without starving a later root whose longer-term value is better.
_MAX_POLICIES: int = 200

# Actions whose prediction is grounded in the target percept (world model).
_TARGET_DIRECTED: frozenset[ActionType] = frozenset(
    {
        ActionType.APPROACH,
        ActionType.INTERACT,
        ActionType.AVOID,
        ActionType.OBSERVE,
        ActionType.ANALYZE,
    }
)

# Fixed deterministic action set for depths >= 2, truncated to the configured
# branching factor (currently PLANNING_BRANCH_DEEP == 4 keeps all four).
_DEEP_BASE: list[ActionType] = [
    ActionType.OBSERVE,
    ActionType.EXPLORE,
    ActionType.REST,
    ActionType.ANALYZE,
][:PLANNING_BRANCH_DEEP]


@dataclass(frozen=True)
class _SimState:
    """Cheap simulated branch state: target distance, energy, live target."""

    dist: int | None            # Chebyshev distance to the target (None = target-free)
    energy: float               # simulated energy budget
    target: Percept | None      # the branch's target percept (None once consumed)


class Planner:
    """Bounded deterministic policy-tree search minimizing discounted EFE."""

    def plan(self, world_model, observation: Observation,
             candidates: list[tuple[ActionType, Percept | None]],
             current_energy: float, initial_energy: float,
             config: SimConfig) -> PlanningState:
        """Search action sequences up to ``config.planning_horizon`` steps.

        Returns the best policy (lowest discounted EFE == highest discounted
        value) as a :class:`PlanningState`. Fully deterministic: stable sorts,
        fixed expansion order, lexicographic tie-breaks.
        """
        horizon = max(2, int(config.planning_horizon))
        discount = float(config.planning_discount)
        denom = max(1.0, float(initial_energy))
        cap = denom * ENERGY_CAP_FACTOR
        pred_cache: dict[tuple[str, int | None], float] = {}

        if not candidates:
            return PlanningState(
                best_sequence=[], best_efe=0.0, horizon=horizon,
                n_policies=0, chosen_first=None,
                report=(
                    "Policy search found no candidates to expand; no policy "
                    "was formed. This is a bounded search over variables, not "
                    "deliberation; the agent is not conscious."
                ),
            )

        # ------------------------------------------------- first-step pruning
        # Rank every candidate by the raw model prediction (target passed
        # as-is) and keep the top PLANNING_BRANCH_FIRST as branch roots.
        root_values: list[float] = []
        for action, target in candidates:
            root_values.append(
                self._predict_value(world_model, observation, action, target, pred_cache)
            )
        order = sorted(
            range(len(candidates)),
            key=lambda i: (
                -root_values[i],
                candidates[i][0].value,
                -1 if candidates[i][1] is None else candidates[i][1].object_id,
            ),
        )
        roots = order[:PLANNING_BRANCH_FIRST]

        # ----------------------------------------- fair bounded tree search
        best_value: float | None = None
        best_names: list[str] = []
        n_policies = 0

        def _policies(state: _SimState, depth: int, names: list[str],
                      acc: float) -> Iterator[tuple[list[str], float]]:
            """Yield one root's complete policies in deterministic DFS order."""
            if depth >= horizon:
                yield list(names), acc
                return
            options: list[tuple[ActionType, Percept | None]] = [
                (a, None) for a in _DEEP_BASE
            ]
            if state.target is not None and state.dist is not None:
                if state.dist <= 1:
                    options.append((ActionType.INTERACT, state.target))
                else:
                    options.append((ActionType.APPROACH, state.target))
            for action, tgt in options:
                score, nxt = self._step(
                    world_model, observation, action, tgt, state,
                    denom, cap, pred_cache,
                )
                yield from _policies(
                    nxt,
                    depth + 1,
                    names + [action.value],
                    acc + (discount ** depth) * score,
                )

        root_searches: list[Iterator[tuple[list[str], float]]] = []
        for idx in roots:
            action, target = candidates[idx]
            dist = max(abs(int(target.dx)), abs(int(target.dy))) if target is not None else None
            # Clamp the root energy into [0, cap] so the _SimState invariant
            # holds from step 0 and an out-of-range current_energy cannot
            # inflate the eff_delta correction on the first transition.
            energy0 = float(min(cap, max(0.0, float(current_energy))))
            state0 = _SimState(dist=dist, energy=energy0, target=target)
            score0, state1 = self._step(
                world_model, observation, action, target, state0,
                denom, cap, pred_cache,
            )
            root_searches.append(_policies(state1, 1, [action.value], score0))

        # Take one complete sequence from every live root per round. At horizons
        # whose full tree fits under the cap this remains exhaustive; at horizon
        # four it gives every top-K root equal opportunity before truncation.
        while root_searches and n_policies < _MAX_POLICIES:
            next_round: list[Iterator[tuple[list[str], float]]] = []
            for search in root_searches:
                if n_policies >= _MAX_POLICIES:
                    break
                try:
                    names, acc = next(search)
                except StopIteration:
                    continue
                n_policies += 1
                if (best_value is None or acc > best_value
                        or (acc == best_value and names < best_names)):
                    best_value = acc
                    best_names = names
                next_round.append(search)
            root_searches = next_round

        best_sequence = list(best_names)
        best_efe = round(-float(best_value), 4) if best_value is not None else 0.0
        chosen_first = best_sequence[0] if best_sequence else None
        seq_label = " -> ".join(best_sequence) if best_sequence else "(none)"
        report = (
            f"Policy search evaluated {n_policies} sequences at horizon {horizon}; "
            f"best policy {seq_label} with discounted EFE {best_efe}. This is a "
            "bounded search over variables, not deliberation; the agent is not "
            "conscious."
        )
        return PlanningState(
            best_sequence=best_sequence,
            best_efe=best_efe,
            horizon=horizon,
            n_policies=int(n_policies),
            chosen_first=chosen_first,
            report=report,
        )

    # ------------------------------------------------------------- internals
    @staticmethod
    def _predict_value(world_model, observation: Observation, action: ActionType,
                       target: Percept | None,
                       cache: dict[tuple[str, int | None], float]) -> float:
        """Cached ``world_model.predict(...).value`` for one (action, target)."""
        key = (action.value, None if target is None else int(target.object_id))
        if key not in cache:
            cache[key] = float(world_model.predict(observation, action, target).value)
        return cache[key]

    def _step(self, world_model, observation: Observation, action: ActionType,
              target: Percept | None, state: _SimState,
              denom: float, cap: float,
              cache: dict[tuple[str, int | None], float]) -> tuple[float, _SimState]:
        """Score one simulated step and return (step_score, next_state).

        The prediction target is gated: INTERACT is only grounded in its
        percept when the simulated distance is <= 1 (an out-of-range INTERACT
        is scored on priors alone, which is what lets APPROACH-then-INTERACT
        policies win).
        """
        in_range = state.dist is not None and state.dist <= 1
        pred_target: Percept | None = None
        if target is not None and action in _TARGET_DIRECTED:
            if action == ActionType.INTERACT:
                pred_target = target if in_range else None
            else:
                pred_target = target
        value = self._predict_value(world_model, observation, action, pred_target, cache)

        # Deterministic simulated transition.
        delta = -(float(ACTION_COSTS[action.value]) + PASSIVE_ENERGY_DECAY)
        new_dist = state.dist
        new_target = state.target
        if action == ActionType.APPROACH and state.target is not None and state.dist is not None:
            new_dist = max(0, state.dist - 1)
        elif action == ActionType.AVOID and state.target is not None and state.dist is not None:
            new_dist = state.dist + 1
        elif action == ActionType.INTERACT and state.target is not None and in_range:
            delta += float(state.target.energy_value) - float(state.target.danger) * INTERACT_DANGER_DAMAGE
            if state.target.energy_value > 0.0:
                new_target = None       # consumed in simulation
                new_dist = None
        elif action == ActionType.REST:
            delta += REST_RECOVERY
        new_energy = float(min(cap, max(0.0, state.energy + delta)))
        eff_delta = new_energy - state.energy

        energy_frac = max(0.0, min(1.0, state.energy / denom))
        score = value + (1.0 - energy_frac) * (eff_delta / _ENERGY_NORM)
        return score, _SimState(dist=new_dist, energy=new_energy, target=new_target)
