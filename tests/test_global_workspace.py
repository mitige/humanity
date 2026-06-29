"""Tests for the Global Workspace Theory (GWT) competition mechanism.

These exercise ``core.global_workspace.GlobalWorkspace``: a clearly-dominant
high (activation * precision) coalition crosses the ignition threshold and wins;
a field of low/equal bids stays subliminal with an attenuated broadcast; and the
post-competition activations always form a normalized (softmax) distribution.
"""
from __future__ import annotations

import pytest

from core.constants import SUBLIMINAL_FACTOR
from core.global_workspace import GlobalWorkspace
from schemas.models import SimConfig


def _ws(**overrides) -> SimConfig:
    """A SimConfig with deterministic, default consciousness parameters."""
    cfg = SimConfig(random_seed=42, world_noise=0.0)
    return cfg.model_copy(update=overrides) if overrides else cfg


def test_dominant_coalition_ignites_and_wins() -> None:
    """A dominant activation*precision bid ignites and is the winner (GWT)."""
    cfg = _ws()
    gw = GlobalWorkspace(cfg)
    coalitions = [
        gw.make_coalition("perception", "salient object", 0.95, 0.95, [1.0, 0.0, 0.0]),
        gw.make_coalition("memory", "weak memory", 0.10, 0.50, [0.0, 1.0, 0.0]),
        gw.make_coalition("motivation", "weak need", 0.08, 0.40, [0.0, 0.0, 1.0]),
    ]
    ws = gw.compete(coalitions, cfg)

    assert ws.ignited is True
    assert ws.winner_source == "perception"
    assert ws.winner_content == "salient object"
    # The top normalized activation must clear the configured ignition cutoff.
    assert ws.broadcast_strength >= cfg.ignition_threshold
    # When ignited, the broadcast vector is the winner's vector verbatim.
    assert ws.broadcast_vector == [1.0, 0.0, 0.0]


def test_low_equal_bids_stay_subliminal_and_attenuate_broadcast() -> None:
    """All-low/equal activations => no dominance => not ignited; broadcast attenuated.

    Ignition now depends on the winner's absolute drive AND its dominance over
    rivals. Four identical bids have zero dominance, so the ignition score is tiny
    and the broadcast is that score cut by SUBLIMINAL_FACTOR (a subliminal trace).
    """
    cfg = _ws()
    gw = GlobalWorkspace(cfg)
    coalitions = [
        gw.make_coalition("perception", "A", 0.2, 0.5, [0.1, 0.2, 0.3]),
        gw.make_coalition("memory", "B", 0.2, 0.5, [0.1, 0.2, 0.3]),
        gw.make_coalition("motivation", "C", 0.2, 0.5, [0.1, 0.2, 0.3]),
        gw.make_coalition("interoception", "D", 0.2, 0.5, [0.1, 0.2, 0.3]),
    ]
    ws = gw.compete(coalitions, cfg)

    assert ws.ignited is False
    # Identical bids => zero relative dominance => sub-threshold ignition score.
    assert ws.dominance == pytest.approx(0.0, abs=1e-6)
    assert ws.ignition_score < cfg.ignition_threshold
    # Subliminal broadcast is the ignition score attenuated by SUBLIMINAL_FACTOR.
    assert ws.broadcast_strength == pytest.approx(ws.ignition_score * SUBLIMINAL_FACTOR, abs=1e-6)
    # Post-competition activations still form a softmax distribution (sum=1).
    assert sum(c.activation for c in ws.competition) == pytest.approx(1.0, abs=1e-6)


def test_post_competition_activations_form_normalized_distribution() -> None:
    """After competition, coalition activations are a softmax distribution (sum=1)."""
    cfg = _ws()
    gw = GlobalWorkspace(cfg)
    coalitions = [
        gw.make_coalition("perception", "A", 0.9, 0.8, [1.0, 0.0]),
        gw.make_coalition("memory", "B", 0.4, 0.6, [0.0, 1.0]),
        gw.make_coalition("motivation", "C", 0.3, 0.5, [0.5, 0.5]),
        gw.make_coalition("prediction_error", "D", 0.6, 0.9, [0.2, 0.2]),
    ]
    ws = gw.compete(coalitions, cfg)

    activations = [c.activation for c in ws.competition]
    # Each normalized activation is a valid probability in [0, 1] ...
    assert all(0.0 <= a <= 1.0 for a in activations)
    # ... and the whole field sums to 1 (a proper distribution).
    assert sum(activations) == pytest.approx(1.0, abs=1e-6)


def test_empty_competition_is_null_subliminal_state() -> None:
    """No coalitions => a non-ignited, zero-broadcast null state (no crash)."""
    cfg = _ws()
    gw = GlobalWorkspace(cfg)
    ws = gw.compete([], cfg)

    assert ws.ignited is False
    assert ws.winner_source is None
    assert ws.broadcast_strength == 0.0
    assert ws.competition == []


def test_recent_winners_ring_buffer_tracks_sources() -> None:
    """The workspace records winning sources for downstream stability metrics."""
    cfg = _ws()
    gw = GlobalWorkspace(cfg)
    for _ in range(3):
        coalitions = [
            gw.make_coalition("perception", "win", 0.95, 0.95, [1.0]),
            gw.make_coalition("memory", "lose", 0.05, 0.2, [0.0]),
        ]
        gw.compete(coalitions, cfg)
    recent = gw.recent_winners(3)
    assert recent == ["perception", "perception", "perception"]
