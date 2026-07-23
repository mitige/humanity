"""Matched Phase-8 gender-experience counterfactual battery."""
from __future__ import annotations

from core.test_battery import ConsciousnessTestBattery
from schemas.models import GenderBatteryResult


def test_gender_battery_is_deterministic_and_has_exact_matched_arms() -> None:
    battery = ConsciousnessTestBattery()
    left = battery.gender_experience_test(
        seed=13, ticks=10, preset_id="nonbinary"
    )
    right = battery.gender_experience_test(
        seed=13, ticks=10, preset_id="nonbinary"
    )
    assert isinstance(left, GenderBatteryResult)
    assert left == right
    assert set(left.arms) == {
        "supportive",
        "hostile",
        "expression_allowed",
        "expression_constrained",
        "euphoria_sensitive",
        "dysphoria_sensitive",
        "isolated",
        "community_connected",
    }
    assert all(len(arm.curve) == 10 for arm in left.arms.values())


def test_matched_pairs_hold_profiles_constant_where_required() -> None:
    result = ConsciousnessTestBattery().gender_experience_test(
        seed=4, ticks=12, preset_id="transfeminine_late"
    )
    assert result.comparisons["supportive_vs_hostile"][
        "same_private_profile"
    ] is True
    assert result.comparisons["expression_allowed_vs_constrained"][
        "same_private_profile"
    ] is True
    assert result.comparisons["community_vs_isolation"][
        "same_private_profile"
    ] is True


def test_battery_exposes_expected_model_consequences_without_causal_claims() -> None:
    result = ConsciousnessTestBattery().gender_experience_test(
        seed=3, ticks=12, preset_id="nonbinary"
    )
    support = result.comparisons["supportive_vs_hostile"]
    assert support["fulfillment_delta"] > 0.0
    assert support["external_stress_delta"] < 0.0
    assert support["internalization_delta"] < 0.0

    expression = result.comparisons[
        "expression_allowed_vs_constrained"
    ]
    assert expression["expression_congruence_delta"] > 0.0
    assert expression["stress_delta"] < 0.0

    sensitivities = result.comparisons[
        "euphoria_vs_dysphoria_sensitivity"
    ]
    assert sensitivities["euphoria_delta"] > 0.0
    assert sensitivities["dysphoria_delta"] < 0.0

    community = result.comparisons["community_vs_isolation"]
    assert community["resilience_delta"] > 0.0
    text = f"{result.interpretation} {result.disclaimer}".lower()
    assert "not estimates of causal effects" in text
    assert "cannot diagnose" in text
    assert "not a diagnostic" in text


def test_every_curve_is_finite_and_bounded() -> None:
    result = ConsciousnessTestBattery().gender_experience_test(
        seed=8, ticks=8, preset_id="euphoria_led"
    )
    bounded = {
        "congruence",
        "expression_congruence",
        "dysphoria",
        "euphoria",
        "fulfillment",
        "external_stress",
        "internalized_transphobia",
        "resilience",
        "accentuation",
        "transition_progress",
    }
    for arm in result.arms.values():
        for row in arm.curve:
            assert bounded <= set(row)
            assert all(0.0 <= float(row[key]) <= 1.0 for key in bounded)

