"""Regression tests for the ignition / graded-awareness fix.

Before the fix, the workspace gated ignition on a softmax-NORMALIZED share that
was structurally capped (~0.35) below the threshold (0.55), so the agent ignited
0% of the time and the attention schema reported "conscious of nothing" on every
tick. These tests pin the corrected behaviour:

  * under the DEFAULT config the agent ignites *sometimes* (rate strictly in
    (0, 1) — neither never nor always);
  * the attention schema always reflects the current dominant content while a
    coalition wins (subliminal != nothing).
"""
from __future__ import annotations

from core.agent import CognitiveAgent
from schemas.models import SimConfig


def test_default_ignition_rate_is_healthy() -> None:
    """Default-config ignition rate must be strictly between 0% and 100%."""
    agent = CognitiveAgent(SimConfig())
    ignited = 0
    aware_of_nothing = 0
    n = 80
    for _ in range(n):
        trace = agent.cognitive_cycle()
        if trace.workspace.ignited:
            ignited += 1
        if "no content available" in trace.attention_schema.aware_of:
            aware_of_nothing += 1
    rate = ignited / n
    assert 0.0 < rate < 1.0, f"ignition rate should be in (0,1), got {rate:.2%}"
    assert aware_of_nothing == 0, (
        f"attention schema reported 'nothing' on {aware_of_nothing}/{n} ticks "
        "while a coalition was winning"
    )


def test_aware_of_reflects_dominant_content() -> None:
    """While coalitions compete there is always a dominant content (a focus)."""
    agent = CognitiveAgent(SimConfig())
    trace = agent.cognitive_cycle()
    assert trace.workspace.winner_source is not None
    assert "no content available" not in trace.attention_schema.aware_of
