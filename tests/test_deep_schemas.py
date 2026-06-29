from schemas.models import (
    CircadianState, SleepState, ImaginationState, CuriosityState, AgencyState,
    CycleTrace, Metrics, SimConfig,
)
from core.constants import WORKSPACE_SOURCES


def test_states_have_safe_defaults():
    assert SleepState(is_sleeping=False, fatigue=0.0).dream is None
    assert ImaginationState().best_first_action is None
    assert CuriosityState().boredom == 0.0
    assert AgencyState().agency == 0.0
    assert CircadianState(phase=0.0, daylight=1.0, is_night=False, period=50).daylight == 1.0


def test_config_defaults_disable_phase2():
    cfg = SimConfig()
    for flag in ("circadian_enabled", "sleep_enabled", "dream_enabled",
                 "imagination_enabled", "curiosity_enabled", "agency_enabled"):
        assert getattr(cfg, flag) is False
    assert cfg.circadian_period == 50 and cfg.imagination_horizon == 3


def test_imagination_and_dream_workspace_sources():
    assert "imagination" in WORKSPACE_SOURCES and "dream" in WORKSPACE_SOURCES
