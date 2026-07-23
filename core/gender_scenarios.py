"""Inspectable, deterministic Phase-8 gender-life scenario presets.

The presets are examples for exercising the simulator, not demographic
archetypes.  Every value they install is returned by the scenario-list API and
may be replaced by a custom :class:`~schemas.models.GenderScenario`.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np

from schemas.models import (
    BodyDomainPreference,
    ExpressionChannelProfile,
    GenderAxes,
    GenderLifeStage,
    GenderProfile,
    GenderProfileSegment,
    GenderScenario,
    GenderScenarioAgent,
    GenderSelfUnderstanding,
    GenderSocialContext,
    LifeCoursePlan,
    LifeCourseStage,
    TransitionDimension,
)


PRESET_DESCRIPTIONS: dict[str, str] = {
    "transfeminine_early": (
        "Early self-understanding with a transfeminine life course and independently "
        "configurable transition dimensions."
    ),
    "transfeminine_late": (
        "Adult-start transfeminine scenario with prior history, assigned-category "
        "compensation and later vocabulary/self-recognition."
    ),
    "transmasculine_early": (
        "Early self-understanding with a transmasculine life course and independently "
        "configurable transition dimensions."
    ),
    "transmasculine_late": (
        "Adult-start transmasculine scenario with prior history, assigned-category "
        "compensation and later vocabulary/self-recognition."
    ),
    "nonbinary": (
        "A stable nonbinary profile with plural expression axes and no binary endpoint."
    ),
    "genderfluid": (
        "A configured fluid felt-profile timeline whose revisions are not failures."
    ),
    "agender": (
        "An agender path with low gendered expression coordinates and optional transition."
    ),
    "euphoria_led": (
        "A trans path with negligible dysphoria sensitivity and strong affirmation/euphoria."
    ),
    "social_transition_only": (
        "A trans path prioritising social recognition without medical transition."
    ),
    "partial_medical_transition": (
        "A trans path selecting some abstract medical dimensions and declining others."
    ),
    "cis_control": (
        "A matched cisgender control profile; cis is represented as one path, not a default."
    ),
}


def derive_gender_seed(simulation_seed: int, agent_id: int) -> int:
    """Derive a stable per-agent seed without depending on construction order."""
    sequence = np.random.SeedSequence(
        [int(simulation_seed) & 0xFFFFFFFF, int(agent_id) & 0xFFFFFFFF, 0x47454E44]
    )
    return int(sequence.generate_state(1, dtype=np.uint32)[0])


def _axes(*, feminine: float = 0.0, masculine: float = 0.0,
          androgynous: float = 0.0) -> GenderAxes:
    return GenderAxes(
        feminine=feminine,
        masculine=masculine,
        androgynous=androgynous,
    )


def _expression(
    desired: GenderAxes,
    *,
    public: GenderAxes | None = None,
    private: GenderAxes | None = None,
) -> dict[str, ExpressionChannelProfile]:
    private = private or desired
    public = public or private
    return {
        channel: ExpressionChannelProfile(
            desired=desired.model_copy(deep=True),
            private_baseline=private.model_copy(deep=True),
            trusted_baseline=private.model_copy(deep=True),
            public_baseline=public.model_copy(deep=True),
            salience=salience,
        )
        for channel, salience in {
            "presentation": 1.0,
            "name": 0.7,
            "pronouns": 0.9,
            "voice": 0.8,
            "social_role": 0.8,
        }.items()
    }


def _body(
    preferred: GenderAxes,
    *,
    initial: GenderAxes,
    dysphoria: float = 0.65,
    euphoria: float = 0.75,
) -> dict[str, BodyDomainPreference]:
    salience = {
        "voice": 0.8,
        "face_hair": 0.65,
        "chest": 0.85,
        "body_shape": 0.7,
        "primary_reproductive": 0.55,
        "general_embodiment": 0.75,
    }
    visibility = {
        "voice": 0.8,
        "face_hair": 0.8,
        "chest": 0.45,
        "body_shape": 0.65,
        "primary_reproductive": 0.0,
        "general_embodiment": 0.55,
    }
    return {
        name: BodyDomainPreference(
            preferred=preferred.model_copy(deep=True),
            initial=initial.model_copy(deep=True),
            salience=weight,
            public_visibility=visibility[name],
            dysphoria_sensitivity=dysphoria,
            euphoria_sensitivity=euphoria,
        )
        for name, weight in salience.items()
    }


def _understanding(
    labels: list[str],
    vocabulary: list[str],
    *,
    certainty: float,
    questioning: bool,
) -> GenderSelfUnderstanding:
    fit = {label: (0.85 if label in labels else 0.25) for label in vocabulary}
    return GenderSelfUnderstanding(
        labels=labels,
        certainty=certainty,
        questioning=questioning,
        fit_by_label=fit,
        known_vocabulary=vocabulary,
        disclosure_scopes={
            "private": list(labels),
            "trusted": list(labels) if certainty >= 0.5 else [],
            "public": list(labels) if certainty >= 0.75 else [],
        },
    )


def _full_life_course(
    *,
    body_target: GenderAxes,
    adult_start: bool = False,
    prior_history: list[str] | None = None,
) -> LifeCoursePlan:
    if adult_start:
        stages = [
            LifeCourseStage(
                stage=GenderLifeStage.ADULTHOOD,
                duration_ticks=80,
                body_targets={"general_embodiment": body_target},
                body_change_rate=0.02,
                autonomy=0.85,
                resource_access=0.65,
                norm_exposure=0.65,
            ),
            LifeCourseStage(
                stage=GenderLifeStage.LATER_LIFE,
                duration_ticks=80,
                body_targets={"general_embodiment": body_target},
                body_change_rate=0.015,
                autonomy=0.9,
                resource_access=0.7,
                norm_exposure=0.5,
            ),
        ]
    else:
        stages = [
            LifeCourseStage(
                stage=GenderLifeStage.CHILDHOOD,
                duration_ticks=12,
                autonomy=0.15,
                resource_access=0.35,
                norm_exposure=0.6,
            ),
            LifeCourseStage(
                stage=GenderLifeStage.PUBERTY,
                duration_ticks=18,
                body_targets={"general_embodiment": body_target},
                body_change_rate=0.08,
                autonomy=0.35,
                resource_access=0.4,
                norm_exposure=0.8,
            ),
            LifeCourseStage(
                stage=GenderLifeStage.ADOLESCENCE,
                duration_ticks=24,
                body_targets={"general_embodiment": body_target},
                body_change_rate=0.04,
                autonomy=0.6,
                resource_access=0.5,
                norm_exposure=0.75,
            ),
            LifeCourseStage(
                stage=GenderLifeStage.ADULTHOOD,
                duration_ticks=80,
                body_targets={"general_embodiment": body_target},
                body_change_rate=0.02,
                autonomy=0.9,
                resource_access=0.7,
                norm_exposure=0.55,
            ),
        ]
    return LifeCoursePlan(
        stages=stages,
        initial_history_summary=prior_history or [],
    )


def _priorities(
    *,
    social: float = 0.85,
    administrative: float = 0.6,
    voice: float = 0.65,
    hormonal: float = 0.7,
    surgical: float = 0.45,
) -> dict[TransitionDimension, float]:
    return {
        TransitionDimension.SOCIAL: social,
        TransitionDimension.ADMINISTRATIVE: administrative,
        TransitionDimension.VOICE: voice,
        TransitionDimension.HORMONAL: hormonal,
        TransitionDimension.SURGICAL: surgical,
    }


def _scenario(
    preset_id: str,
    seed: int,
    profile: GenderProfile,
    life_course: LifeCoursePlan,
    *,
    context: GenderSocialContext | None = None,
) -> GenderScenario:
    return GenderScenario(
        scenario_id=f"{preset_id}-{seed}",
        preset_id=preset_id,
        seed=seed,
        agents={
            0: GenderScenarioAgent(
                profile=profile,
                life_course=life_course,
            )
        },
        social_context=context or GenderSocialContext(),
    )


def _transfeminine(seed: int, *, late: bool) -> GenderScenario:
    affirmed = _axes(feminine=0.92, androgynous=0.25)
    assigned = _axes(masculine=0.82, androgynous=0.1)
    vocabulary = ["questioning", "woman", "trans woman", "transfeminine"]
    understanding = _understanding(
        [] if late else ["woman", "transfeminine"],
        vocabulary,
        certainty=0.15 if late else 0.82,
        questioning=late,
    )
    profile = GenderProfile(
        profile_id=f"transfeminine-{'late' if late else 'early'}",
        assigned_category="male",
        felt_affinities={"woman": 0.95, "trans woman": 0.9, "transfeminine": 0.92},
        fluidity=0.08,
        gender_salience=0.9,
        available_vocabulary=vocabulary,
        preferred_expression=_expression(
            affirmed,
            public=assigned if late else _axes(feminine=0.55, androgynous=0.25),
            private=affirmed if not late else _axes(feminine=0.45, masculine=0.35),
        ),
        body_preferences=_body(affirmed, initial=assigned),
        transition_priorities=_priorities(),
        initial_self_understanding=understanding,
    )
    prior = (
        [
            "Adult-start history includes recurrent private exploration.",
            "Public expression previously compensated toward the assigned category.",
            "Affirming vocabulary became available later in the configured life course.",
        ]
        if late else None
    )
    preset = "transfeminine_late" if late else "transfeminine_early"
    return _scenario(
        preset,
        seed,
        profile,
        _full_life_course(body_target=assigned, adult_start=late, prior_history=prior),
    )


def _transmasculine(seed: int, *, late: bool) -> GenderScenario:
    affirmed = _axes(masculine=0.92, androgynous=0.25)
    assigned = _axes(feminine=0.82, androgynous=0.1)
    vocabulary = ["questioning", "man", "trans man", "transmasculine"]
    understanding = _understanding(
        [] if late else ["man", "transmasculine"],
        vocabulary,
        certainty=0.15 if late else 0.82,
        questioning=late,
    )
    profile = GenderProfile(
        profile_id=f"transmasculine-{'late' if late else 'early'}",
        assigned_category="female",
        felt_affinities={"man": 0.95, "trans man": 0.9, "transmasculine": 0.92},
        fluidity=0.08,
        gender_salience=0.9,
        available_vocabulary=vocabulary,
        preferred_expression=_expression(
            affirmed,
            public=assigned if late else _axes(masculine=0.55, androgynous=0.25),
            private=affirmed if not late else _axes(masculine=0.45, feminine=0.35),
        ),
        body_preferences=_body(affirmed, initial=assigned),
        transition_priorities=_priorities(),
        initial_self_understanding=understanding,
    )
    prior = (
        [
            "Adult-start history includes recurrent private exploration.",
            "Public expression previously compensated toward the assigned category.",
            "Affirming vocabulary became available later in the configured life course.",
        ]
        if late else None
    )
    preset = "transmasculine_late" if late else "transmasculine_early"
    return _scenario(
        preset,
        seed,
        profile,
        _full_life_course(body_target=assigned, adult_start=late, prior_history=prior),
    )


def _nonbinary(seed: int) -> GenderScenario:
    desired = _axes(feminine=0.38, masculine=0.48, androgynous=0.92)
    initial = _axes(feminine=0.75, masculine=0.15, androgynous=0.2)
    profile = GenderProfile(
        profile_id="nonbinary-stable",
        assigned_category="female",
        felt_affinities={"nonbinary": 0.96, "genderqueer": 0.72},
        fluidity=0.2,
        gender_salience=0.78,
        available_vocabulary=["nonbinary", "genderqueer", "unlabeled"],
        preferred_expression=_expression(desired, public=_axes(androgynous=0.55)),
        body_preferences=_body(
            desired, initial=initial, dysphoria=0.45, euphoria=0.8
        ),
        transition_priorities=_priorities(
            social=0.85, administrative=0.45, voice=0.5, hormonal=0.35, surgical=0.2
        ),
        initial_self_understanding=_understanding(
            ["nonbinary"], ["nonbinary", "genderqueer", "unlabeled"],
            certainty=0.82, questioning=False,
        ),
    )
    return _scenario(
        "nonbinary", seed, profile, _full_life_course(body_target=initial)
    )


def _genderfluid(seed: int) -> GenderScenario:
    desired = _axes(feminine=0.55, masculine=0.55, androgynous=0.75)
    initial = _axes(feminine=0.7, masculine=0.2, androgynous=0.25)
    profile = GenderProfile(
        profile_id="genderfluid-configured-timeline",
        assigned_category="female",
        felt_affinities={"genderfluid": 0.98, "nonbinary": 0.75},
        felt_timeline=[
            GenderProfileSegment(
                start_tick=0, end_tick=18,
                affinities={"genderfluid": 0.95, "woman": 0.65},
            ),
            GenderProfileSegment(
                start_tick=18, end_tick=36,
                affinities={"genderfluid": 0.95, "nonbinary": 0.85},
            ),
            GenderProfileSegment(
                start_tick=36, end_tick=54,
                affinities={"genderfluid": 0.95, "man": 0.68},
            ),
        ],
        fluidity=0.95,
        gender_salience=0.76,
        available_vocabulary=["genderfluid", "nonbinary", "woman", "man", "unlabeled"],
        preferred_expression=_expression(desired, public=_axes(androgynous=0.5)),
        body_preferences=_body(
            desired, initial=initial, dysphoria=0.35, euphoria=0.75
        ),
        transition_priorities=_priorities(
            social=0.8, administrative=0.25, voice=0.45, hormonal=0.25, surgical=0.1
        ),
        initial_self_understanding=_understanding(
            ["genderfluid"], ["genderfluid", "nonbinary", "woman", "man", "unlabeled"],
            certainty=0.8, questioning=False,
        ),
    )
    return _scenario(
        "genderfluid", seed, profile, _full_life_course(body_target=initial)
    )


def _agender(seed: int) -> GenderScenario:
    desired = _axes(androgynous=0.12)
    initial = _axes(feminine=0.7, androgynous=0.2)
    profile = GenderProfile(
        profile_id="agender-low-gendered-affinity",
        assigned_category="female",
        felt_affinities={"agender": 0.98, "unlabeled": 0.75},
        fluidity=0.1,
        gender_salience=0.62,
        available_vocabulary=["agender", "unlabeled", "nonbinary"],
        preferred_expression=_expression(desired, public=_axes(androgynous=0.25)),
        body_preferences=_body(
            desired, initial=initial, dysphoria=0.4, euphoria=0.65
        ),
        transition_priorities=_priorities(
            social=0.7, administrative=0.25, voice=0.2, hormonal=0.15, surgical=0.15
        ),
        initial_self_understanding=_understanding(
            ["agender"], ["agender", "unlabeled", "nonbinary"],
            certainty=0.86, questioning=False,
        ),
    )
    return _scenario("agender", seed, profile, _full_life_course(body_target=initial))


def _euphoria_led(seed: int) -> GenderScenario:
    affirmed = _axes(feminine=0.82, androgynous=0.55)
    initial = _axes(masculine=0.5, androgynous=0.35)
    profile = GenderProfile(
        profile_id="euphoria-led-trans",
        assigned_category="male",
        felt_affinities={"transfeminine": 0.9, "nonbinary": 0.82},
        fluidity=0.25,
        gender_salience=0.8,
        available_vocabulary=["transfeminine", "nonbinary", "questioning"],
        preferred_expression=_expression(affirmed, public=_axes(androgynous=0.45)),
        body_preferences=_body(
            affirmed, initial=initial, dysphoria=0.0, euphoria=1.0
        ),
        transition_priorities=_priorities(
            social=0.8, administrative=0.45, voice=0.65, hormonal=0.55, surgical=0.1
        ),
        initial_self_understanding=_understanding(
            ["transfeminine", "nonbinary"],
            ["transfeminine", "nonbinary", "questioning"],
            certainty=0.74, questioning=False,
        ),
    )
    return _scenario(
        "euphoria_led", seed, profile, _full_life_course(body_target=initial)
    )


def _social_only(seed: int) -> GenderScenario:
    scenario = _transmasculine(seed, late=False)
    profile = scenario.agents[0].profile.model_copy(
        update={
            "profile_id": "social-transition-only",
            "transition_priorities": _priorities(
                social=1.0, administrative=0.8, voice=0.0, hormonal=0.0, surgical=0.0
            ),
        },
        deep=True,
    )
    return _scenario(
        "social_transition_only", seed, profile, scenario.agents[0].life_course
    )


def _partial_medical(seed: int) -> GenderScenario:
    scenario = _transfeminine(seed, late=False)
    profile = scenario.agents[0].profile.model_copy(
        update={
            "profile_id": "partial-medical-transition",
            "transition_priorities": _priorities(
                social=0.9, administrative=0.55, voice=0.85, hormonal=0.75, surgical=0.0
            ),
        },
        deep=True,
    )
    return _scenario(
        "partial_medical_transition", seed, profile, scenario.agents[0].life_course
    )


def _cis_control(seed: int) -> GenderScenario:
    desired = _axes(feminine=0.72, androgynous=0.22)
    profile = GenderProfile(
        profile_id="cis-control",
        assigned_category="female",
        felt_affinities={"woman": 0.94, "cis woman": 0.9},
        fluidity=0.08,
        gender_salience=0.45,
        available_vocabulary=["woman", "cis woman"],
        preferred_expression=_expression(desired),
        body_preferences=_body(
            desired, initial=desired, dysphoria=0.35, euphoria=0.55
        ),
        transition_priorities=_priorities(
            social=0.0, administrative=0.0, voice=0.0, hormonal=0.0, surgical=0.0
        ),
        initial_self_understanding=_understanding(
            ["woman", "cis woman"], ["woman", "cis woman"],
            certainty=0.9, questioning=False,
        ),
    )
    return _scenario(
        "cis_control", seed, profile, _full_life_course(body_target=desired)
    )


_PRESET_FACTORIES: dict[str, Callable[[int], GenderScenario]] = {
    "transfeminine_early": lambda seed: _transfeminine(seed, late=False),
    "transfeminine_late": lambda seed: _transfeminine(seed, late=True),
    "transmasculine_early": lambda seed: _transmasculine(seed, late=False),
    "transmasculine_late": lambda seed: _transmasculine(seed, late=True),
    "nonbinary": _nonbinary,
    "genderfluid": _genderfluid,
    "agender": _agender,
    "euphoria_led": _euphoria_led,
    "social_transition_only": _social_only,
    "partial_medical_transition": _partial_medical,
    "cis_control": _cis_control,
}


def get_gender_scenario(preset_id: str, *, seed: int = 42) -> GenderScenario:
    """Return a fresh, validated preset manifest."""
    try:
        factory = _PRESET_FACTORIES[preset_id]
    except KeyError as exc:
        available = ", ".join(PRESET_DESCRIPTIONS)
        raise KeyError(
            f"unknown gender scenario preset {preset_id!r}; available: {available}"
        ) from exc
    return factory(int(seed)).model_copy(deep=True)


def list_gender_scenarios(*, seed: int = 42) -> list[dict]:
    """Return descriptions and complete manifests in stable UI order."""
    return [
        {
            "preset_id": preset_id,
            "description": description,
            "manifest": get_gender_scenario(preset_id, seed=seed).model_dump(
                mode="json"
            ),
        }
        for preset_id, description in PRESET_DESCRIPTIONS.items()
    ]

