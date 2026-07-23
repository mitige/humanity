"""Configurable, identity-neutral life-course progression for Phase 8."""
from __future__ import annotations

from dataclasses import dataclass, field

from schemas.models import (
    GenderAxes,
    GenderEventRequest,
    GenderEventType,
    GenderLifeStage,
    LifeCoursePlan,
    LifeCourseStage,
)


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def axes_values(axes: GenderAxes) -> dict[str, float]:
    """Flatten built-in and custom axes into one independent coordinate map."""
    return {
        "feminine": float(axes.feminine),
        "masculine": float(axes.masculine),
        "androgynous": float(axes.androgynous),
        **{name: float(value) for name, value in axes.custom.items()},
    }


def axes_from_values(values: dict[str, float]) -> GenderAxes:
    return GenderAxes(
        feminine=_clip01(values.get("feminine", 0.0)),
        masculine=_clip01(values.get("masculine", 0.0)),
        androgynous=_clip01(values.get("androgynous", 0.0)),
        custom={
            name: _clip01(value)
            for name, value in values.items()
            if name not in {"feminine", "masculine", "androgynous"}
        },
    )


def move_axes(current: GenderAxes, target: GenderAxes, rate: float) -> GenderAxes:
    """Move each coordinate independently toward ``target`` by an EMA rate."""
    current_values = axes_values(current)
    target_values = axes_values(target)
    names = current_values.keys() | target_values.keys()
    return axes_from_values(
        {
            name: current_values.get(name, 0.0)
            + float(rate)
            * (target_values.get(name, 0.0) - current_values.get(name, 0.0))
            for name in names
        }
    )


def mean_axis_distance(left: GenderAxes, right: GenderAxes) -> float:
    left_values = axes_values(left)
    right_values = axes_values(right)
    names = left_values.keys() | right_values.keys()
    if not names:
        return 0.0
    return float(
        sum(abs(left_values.get(name, 0.0) - right_values.get(name, 0.0))
            for name in names)
        / len(names)
    )


@dataclass(slots=True)
class LifecycleUpdate:
    stage: GenderLifeStage
    stage_index: int
    tick_in_stage: int
    body: dict[str, GenderAxes]
    events: list[GenderEventRequest] = field(default_factory=list)


class GenderLifecycle:
    """Stateful stage clock whose body changes never decide identity."""

    def __init__(
        self,
        plan: LifeCoursePlan,
        *,
        initial_body: dict[str, GenderAxes] | None = None,
    ) -> None:
        self.plan = plan.model_copy(deep=True)
        self.stage_index = 0
        self.tick_in_stage = 0
        self.body = {
            name: axes.model_copy(deep=True)
            for name, axes in (initial_body or {}).items()
        }

    @property
    def stage(self) -> LifeCourseStage:
        return self.plan.stages[self.stage_index]

    def advance(self, *, target_id: int = 0) -> LifecycleUpdate:
        """Advance exactly one semantic tick and expose all generated changes."""
        events: list[GenderEventRequest] = []
        if (
            self.tick_in_stage >= self.stage.duration_ticks
            and self.stage_index < len(self.plan.stages) - 1
        ):
            self.stage_index += 1
            self.tick_in_stage = 0
            events.append(
                GenderEventRequest(
                    target_id=target_id,
                    type=GenderEventType.LIFE_STAGE_CHANGE,
                    domain=self.stage.stage.value,
                    intensity=1.0,
                    context_code="configured_life_course",
                )
            )

        for domain, target in self.stage.body_targets.items():
            current = self.body.get(domain, GenderAxes())
            updated = move_axes(current, target, self.stage.body_change_rate)
            distance = mean_axis_distance(current, updated)
            self.body[domain] = updated
            if distance > 1e-9:
                event_type = (
                    GenderEventType.VOICE_CHANGE
                    if domain == "voice"
                    else GenderEventType.BODY_CHANGE
                )
                events.append(
                    GenderEventRequest(
                        target_id=target_id,
                        type=event_type,
                        domain=domain,
                        intensity=_clip01(distance * 4.0),
                        context_code="configured_life_course",
                    )
                )

        self.tick_in_stage += 1
        return LifecycleUpdate(
            stage=self.stage.stage,
            stage_index=self.stage_index,
            tick_in_stage=self.tick_in_stage,
            body={
                name: axes.model_copy(deep=True)
                for name, axes in self.body.items()
            },
            events=events,
        )

    def replace_body(self, domain: str, axes: GenderAxes) -> None:
        """Synchronise an abstract transition effect back into lifecycle state."""
        self.body[domain] = axes.model_copy(deep=True)

