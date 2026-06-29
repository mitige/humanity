"""Tests for the Higher-Order Theories (HOT) / metacognition module.

These exercise ``core.metacognition.Metacognition.update``: meta_confidence
stays within [0, 1]; high errors depress prediction_reliability and
meta_confidence; and error_monitor tracks the current prediction error.
"""
from __future__ import annotations

import pytest

from core.metacognition import Metacognition
from schemas.models import SimConfig, WorkspaceState


def _cfg() -> SimConfig:
    """Deterministic config for the HOT tests."""
    return SimConfig(random_seed=42, world_noise=0.0)


def _workspace(ignited: bool = False) -> WorkspaceState:
    """A minimal workspace outcome for the metacognitive update."""
    return WorkspaceState(
        ignited=ignited,
        threshold=0.55,
        winner_source="perception" if ignited else None,
        winner_content="objet 1 (food)" if ignited else None,
        broadcast_strength=0.6 if ignited else 0.1,
        competition=[],
        broadcast_vector=[],
    )


def test_meta_confidence_in_unit_interval() -> None:
    """meta_confidence is bounded to [0, 1] across a sweep of inputs."""
    mc = Metacognition()
    cfg = _cfg()
    ws = _workspace()
    for pe, unc, conf in [
        (0.0, 0.0, 0.0),
        (0.5, 0.5, 0.5),
        (1.0, 1.0, 1.0),
        (0.9, 0.1, 0.7),
        (0.2, 0.8, 0.3),
    ]:
        state = mc.update(
            prediction_error=pe,
            uncertainty=unc,
            workspace=ws,
            confidence=conf,
            recent_errors=[],
            config=cfg,
        )
        assert 0.0 <= state.meta_confidence <= 1.0
        assert 0.0 <= state.perception_reliability <= 1.0
        assert 0.0 <= state.prediction_reliability <= 1.0
        assert 0.0 <= state.error_monitor <= 1.0


def test_high_errors_lower_reliability_and_meta_confidence() -> None:
    """High prediction errors depress prediction_reliability and meta_confidence."""
    mc = Metacognition()
    cfg = _cfg()
    ws = _workspace()

    low_error = mc.update(
        prediction_error=0.0,
        uncertainty=0.0,
        workspace=ws,
        confidence=0.8,
        recent_errors=[0.0, 0.0, 0.0],
        config=cfg,
    )
    high_error = mc.update(
        prediction_error=0.9,
        uncertainty=0.9,
        workspace=ws,
        confidence=0.2,
        recent_errors=[0.9, 0.95, 0.92],
        config=cfg,
    )

    assert high_error.prediction_reliability < low_error.prediction_reliability
    assert high_error.meta_confidence < low_error.meta_confidence


def test_error_monitor_tracks_prediction_error() -> None:
    """error_monitor equals the (clamped) current prediction error."""
    mc = Metacognition()
    cfg = _cfg()
    ws = _workspace()

    state = mc.update(
        prediction_error=0.42,
        uncertainty=0.3,
        workspace=ws,
        confidence=0.5,
        recent_errors=[],
        config=cfg,
    )
    assert state.error_monitor == pytest.approx(0.42, abs=1e-9)

    # Out-of-range errors are clamped into [0, 1].
    clamped = mc.update(
        prediction_error=1.7,
        uncertainty=0.3,
        workspace=ws,
        confidence=0.5,
        recent_errors=[],
        config=cfg,
    )
    assert clamped.error_monitor == 1.0


def test_higher_order_report_represents_first_order_state() -> None:
    """The HOT report is framed as a representation of a first-order state."""
    mc = Metacognition()
    state = mc.update(
        prediction_error=0.1,
        uncertainty=0.1,
        workspace=_workspace(ignited=True),
        confidence=0.7,
        recent_errors=[0.1],
        config=_cfg(),
    )
    report = state.higher_order_report
    assert "represents" in report
    assert "meta-confidence" in report
    assert "HOT" in report
    # When ignited, the report is about the broadcast content.
    assert "objet 1 (food)" in report
