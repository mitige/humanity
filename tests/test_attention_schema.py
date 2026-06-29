"""Tests for the Attention Schema Theory (AST) module.

These exercise ``core.attention_schema.AttentionSchema.update``: ``aware_of``
reflects the ignited workspace winner; ``awareness_level`` mirrors the workspace
broadcast strength; ``attributed_self`` is framed explicitly as a self-MODEL of
attention; and ``stability`` stays within [0, 1].
"""
from __future__ import annotations

from core.attention_schema import AttentionSchema
from schemas.models import SimConfig, WorkspaceState


def _cfg() -> SimConfig:
    """Deterministic config for the AST tests."""
    return SimConfig(random_seed=42, world_noise=0.0)


def _ignited(content: str = "objet 3 (food)", strength: float = 0.72) -> WorkspaceState:
    """An ignited workspace outcome with a named winner."""
    return WorkspaceState(
        ignited=True,
        threshold=0.55,
        winner_source="perception",
        winner_content=content,
        broadcast_strength=strength,
        competition=[],
        broadcast_vector=[1.0, 0.0],
    )


def _subliminal(strength: float = 0.05) -> WorkspaceState:
    """A subliminal (non-ignited) workspace outcome."""
    return WorkspaceState(
        ignited=False,
        threshold=0.55,
        winner_source=None,
        winner_content=None,
        broadcast_strength=strength,
        competition=[],
        broadcast_vector=[],
    )


def test_aware_of_reflects_ignited_winner() -> None:
    """When ignited, aware_of is the globally-broadcast winner content."""
    schema = AttentionSchema()
    ws = _ignited(content="objet 7 (tool)")
    state = schema.update(ws, ["perception"], _cfg())
    assert state.aware_of == "objet 7 (tool)"


def test_subliminal_with_content_still_reports_dominant_content() -> None:
    """Graded awareness: not ignited but a winner exists => aware_of is that
    content (a current focus), flagged subliminal in the self-attribution."""
    schema = AttentionSchema()
    ws = WorkspaceState(
        ignited=False,
        threshold=0.32,
        winner_source="perception",
        winner_content="objet 2 (curio)",
        broadcast_strength=0.08,
        competition=[],
        broadcast_vector=[],
    )
    state = schema.update(ws, [], _cfg())
    # The content is still the focus (subliminal != nothing) ...
    assert state.aware_of == "objet 2 (curio)"
    # ... but the access qualifier marks it as subliminal.
    assert "subliminal" in state.attributed_self


def test_empty_competition_reports_no_content() -> None:
    """Only a genuinely empty competition (no winner) yields 'no content'."""
    schema = AttentionSchema()
    state = schema.update(_subliminal(), [], _cfg())  # winner_content=None
    assert "no content available" in state.aware_of


def test_awareness_level_equals_broadcast_strength() -> None:
    """awareness_level mirrors the workspace broadcast strength exactly."""
    schema = AttentionSchema()
    ws = _ignited(strength=0.63)
    state = schema.update(ws, ["perception", "perception"], _cfg())
    assert state.awareness_level == ws.broadcast_strength


def test_attributed_self_uses_self_model_framing() -> None:
    """attributed_self is explicitly framed as a self-MODEL of attention (AST)."""
    schema = AttentionSchema()
    ws = _ignited()
    state = schema.update(ws, ["perception"], _cfg())
    text = state.attributed_self
    # It must read as a model of attention, not as lived experience, and cite AST.
    assert "attention schema" in text
    assert "models" in text
    assert "AST" in text
    # The thing modelled-as-aware-of appears in the self-attribution sentence.
    assert state.aware_of in text


def test_stability_in_unit_interval() -> None:
    """stability stays within [0, 1] for matching, mismatching and empty buffers."""
    schema = AttentionSchema()
    cfg = _cfg()
    ws = _ignited()

    # Empty buffer => no evidence of instability => maximal stability.
    empty = schema.update(ws, [], cfg)
    assert empty.stability == 1.0

    # All recent winners match the current winner_source => fully stable.
    stable = schema.update(ws, ["perception", "perception", "perception"], cfg)
    assert stable.stability == 1.0

    # Partial match => a proper fraction in [0, 1].
    mixed = schema.update(ws, ["perception", "memory", "motivation", "perception"], cfg)
    assert 0.0 <= mixed.stability <= 1.0
    assert mixed.stability == 0.5
