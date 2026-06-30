"""Self-opacity: higher-order awareness of what escaped access/control."""
from core.agent import CognitiveAgent
from core.self_opacity import assess_self_opacity
from schemas.models import SimConfig


def _agent(**kw):
    kw.setdefault("world_noise", 0.0)
    kw.setdefault("persist_memory", False)
    kw.setdefault("trace_logging", False)
    return CognitiveAgent(SimConfig(**kw))


def test_self_opacity_off_by_default_and_trace_none():
    assert SimConfig().self_opacity_enabled is False
    tr = _agent().cognitive_cycle()
    assert tr.self_opacity is None


def test_self_opacity_present_and_bounded_when_enabled():
    tr = _agent(self_opacity_enabled=True).cognitive_cycle()
    so = tr.self_opacity
    assert so is not None
    for v in (so.uncontrolled_fraction, so.subliminal_share, so.unanticipated):
        assert 0.0 <= v <= 1.0
    assert so.uncaused is None              # agency off => no self-causation term
    assert "access or control" in so.report


def test_self_opacity_includes_uncaused_when_agency_on():
    tr = _agent(self_opacity_enabled=True, agency_enabled=True).cognitive_cycle()
    so = tr.self_opacity
    assert so.uncaused is not None and 0.0 <= so.uncaused <= 1.0
    # headline = mean of the three available terms
    expected = (so.subliminal_share + so.unanticipated + so.uncaused) / 3.0
    assert abs(so.uncontrolled_fraction - expected) < 1e-9


def test_self_opacity_pure_function_grounded_in_workspace():
    tr = _agent().cognitive_cycle()
    so = assess_self_opacity(workspace=tr.workspace, prediction_error=0.8, agency=0.0)
    assert abs(so.unanticipated - 0.8) < 1e-9
    assert abs(so.uncaused - 1.0) < 1e-9                       # 1 - agency(0)
    assert abs(so.subliminal_share - (1.0 - tr.workspace.broadcast_strength)) < 1e-9
