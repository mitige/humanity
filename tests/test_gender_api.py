"""Phase-8 HTTP, checkpoint and export contracts."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from core.gender_scenarios import get_gender_scenario  # noqa: E402
from core.society import SocietyManager  # noqa: E402
from schemas.models import SimConfig  # noqa: E402


@pytest.fixture()
def live_client():
    import core.agent as agent_module

    manager = SocietyManager(
        SimConfig(
            random_seed=27,
            world_noise=0.0,
            n_objects=0,
            persist_memory=False,
            trace_logging=False,
        )
    )
    agent_module._MANAGER = manager
    with TestClient(app) as client:
        try:
            yield client, manager
        finally:
            manager.pause()
            agent_module._MANAGER = None


def test_default_gender_endpoint_is_explicitly_empty(live_client) -> None:
    client, _ = live_client
    response = client.get("/agent/gender")
    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "configured": False,
        "state": None,
        "disclaimer": response.json()["disclaimer"],
    }
    assert response.json()["disclaimer"]


def test_scenario_listing_contains_all_complete_manifests(live_client) -> None:
    client, _ = live_client
    response = client.get("/gender/scenarios?seed=5")
    assert response.status_code == 200
    scenarios = response.json()["scenarios"]
    assert len(scenarios) == 11
    assert {item["preset_id"] for item in scenarios} >= {
        "transfeminine_early",
        "transmasculine_late",
        "genderfluid",
        "agender",
        "euphoria_led",
        "cis_control",
    }
    assert all(item["manifest"]["seed"] == 5 for item in scenarios)
    assert all(item["manifest"]["agents"] for item in scenarios)


def test_applying_preset_is_full_reset_and_returns_initial_state(
    live_client,
) -> None:
    client, manager = live_client
    manager.tick()
    manager.tick()
    response = client.post(
        "/gender/scenario",
        json={"preset_id": "euphoria_led", "seed": 9},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "full_reset"
    assert body["reset"] is True
    assert body["initialized_tick"] == 1
    assert body["agents"]["0"]["configured"] is True
    assert body["agents"]["0"]["state"]["affect"]["dysphoria"] == 0.0
    assert manager.config.gender_experience_enabled is True
    assert manager.config.random_seed == 9
    assert manager.world.tick == 1


def test_invalid_or_unknown_scenario_does_not_mutate_live_run(
    live_client,
) -> None:
    client, manager = live_client
    manager.tick()
    before = (manager.world, manager.world.tick, manager.config)
    invalid = client.post(
        "/gender/scenario",
        json={
            "preset_id": "nonbinary",
            "scenario": get_gender_scenario("agender").model_dump(
                mode="json"
            ),
        },
    )
    assert invalid.status_code == 422
    assert (manager.world, manager.world.tick, manager.config) == before

    unknown = client.post(
        "/gender/scenario",
        json={"preset_id": "does-not-exist", "seed": 1},
    )
    assert unknown.status_code == 404
    assert (manager.world, manager.world.tick, manager.config) == before


def test_unconfigured_mutation_returns_grounded_conflict(live_client) -> None:
    client, _ = live_client
    response = client.post(
        "/agent/gender/event",
        json={
            "type": "affirmation",
            "domain": "general",
            "context_code": "test",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["accepted"] is False


def test_hostile_free_text_is_rejected_before_queueing(live_client) -> None:
    client, manager = live_client
    assert client.post(
        "/gender/scenario",
        json={"preset_id": "nonbinary", "seed": 2},
    ).status_code == 200
    ledger_before = manager.agent(0).gender_experience.event_ledger
    response = client.post(
        "/agent/gender/event",
        json={
            "type": "invalidation",
            "domain": "public",
            "context_code": "test",
            "note": "custom hostile dialogue",
        },
    )
    assert response.status_code == 422
    assert manager.agent(0).gender_experience.event_ledger == ledger_before


def test_event_and_intent_are_queued_for_the_next_tick(live_client) -> None:
    client, _ = live_client
    client.post(
        "/gender/scenario",
        json={"preset_id": "partial_medical_transition", "seed": 2},
    )
    event_response = client.post(
        "/agent/gender/event",
        json={
            "type": "affirmation",
            "domain": "general",
            "intensity": 1.0,
            "context_code": "trusted_support",
        },
    )
    intent_response = client.post(
        "/agent/gender/intent",
        json={
            "type": "seek_voice_work",
            "domain": "voice",
            "urgency": 0.9,
            "transition_dimension": "voice",
        },
    )
    assert event_response.status_code == 200
    assert intent_response.status_code == 200
    scheduled = event_response.json()["scheduled_tick"]
    trace = client.post("/tick").json()
    assert trace["tick"] == scheduled
    gender = trace["gender_experience"]
    assert event_response.json()["event"]["event_id"] in gender[
        "recent_event_ids"
    ]
    assert gender["transitions"]["voice"]["progress"] > 0.0


def test_debug_is_private_while_ordinary_and_society_views_are_safe(
    live_client,
) -> None:
    client, _ = live_client
    client.post(
        "/gender/scenario",
        json={"preset_id": "transfeminine_late", "seed": 3},
    )
    ordinary = client.get("/agent/gender").json()
    debug = client.get("/agent/gender/debug")
    society = client.get("/society/gender")
    assert debug.status_code == 200
    assert society.status_code == 200
    assert "profile" in debug.json()
    assert "assigned_category" in str(debug.json())
    assert "assigned_category" not in str(ordinary)
    assert "body_preferences" not in str(ordinary)
    assert "assigned_category" not in str(society.json())
    assert "body_preferences" not in str(society.json())


def test_public_and_private_exports_require_explicit_opt_in(
    live_client,
) -> None:
    client, _ = live_client
    no_scenario = client.get("/export/gender-scenario")
    assert no_scenario.status_code == 409
    client.post(
        "/gender/scenario",
        json={"preset_id": "genderfluid", "seed": 4},
    )
    public = client.get("/export/gender-scenario").json()
    private = client.get(
        "/export/gender-scenario?include_private=true"
    ).json()
    assert public["contains_private_profiles"] is False
    assert "felt_affinities" not in str(public)
    assert "body_preferences" not in str(public)
    assert private["contains_private_profiles"] is True
    assert "felt_affinities" in str(private)
    assert "body_preferences" in str(private)


def test_gender_battery_is_offline_and_does_not_mutate_live_tick(
    live_client,
) -> None:
    client, manager = live_client
    before = manager.world.tick
    response = client.post(
        "/battery/gender-experience",
        json={"preset_id": "euphoria_led", "seed": 6, "ticks": 8},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["test"] == "gender_experience"
    assert len(body["arms"]) == 8
    assert "not estimates of causal effects" in body[
        "interpretation"
    ].lower()
    assert manager.world.tick == before


def test_active_gender_checkpoint_resumes_next_ticks_exactly(
    tmp_path, monkeypatch,
) -> None:
    from core import checkpoint

    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path)
    scenario = get_gender_scenario("genderfluid", seed=17)
    source = SocietyManager(
        SimConfig(
            n_objects=0,
            world_noise=0.0,
            persist_memory=False,
            trace_logging=False,
        )
    )
    source.install_gender_scenario(scenario)
    for _ in range(8):
        source.tick()
    checkpoint.save(source, "gender-active")
    expected = [
        [trace.model_dump(mode="json") for trace in source.tick()]
        for _ in range(5)
    ]
    expected_ledger = source.agent(0).gender_experience.event_ledger
    expected_society = source.gender_society.state()

    resumed = SocietyManager(
        SimConfig(persist_memory=False, trace_logging=False)
    )
    checkpoint.load(resumed, "gender-active")
    actual = [
        [trace.model_dump(mode="json") for trace in resumed.tick()]
        for _ in range(5)
    ]
    assert actual == expected
    assert resumed.agent(0).gender_experience.event_ledger == expected_ledger
    assert resumed.gender_society.state() == expected_society
    assert resumed.gender_scenario_manifest == scenario

