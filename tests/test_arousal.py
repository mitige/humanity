"""Tests for the arousal (vigilance) + ignition dynamics (v2.1).

These pin the behaviour of the global-workspace ignition dynamic once it became
arousal-gated, dominance-weighted and hysteresis-aware:

  * arousal is a bounded [0, 1] scalar that RISES after a salient world-stimulus
    (a danger object entering view) and after a queued ``surprise`` perturbation;
  * higher arousal LOWERS the effective ignition threshold (rising vigilance makes
    conscious access easier) and is therefore at-least-as-likely to ignite the same
    field of coalitions — with a borderline field, it strictly flips ignition on;
  * ignition needs a clearly-DOMINANT strong winner: a runaway bid ignites, a flat
    field of equal bids does not (dominance, not just raw strength, matters);
  * HYSTERESIS: a coalition matching ``maintenance_source`` (whatever was broadcast
    last tick) gets a maintenance boost, so a borderline rival can be sustained as
    the winner with a higher effective drive (a "train of thought");
  * cross-cycle, the default-config ignition rate stays strictly in (0, 1) and the
    attention schema never reports the empty-field string while a winner exists.

All construction uses fixed seeds and ``GlobalWorkspace`` directly where possible;
no sleeps, no background loops. The cross-cycle test complements (does not replace)
``tests/test_ignition_fix.py`` — both are expected to live side by side.
"""
from __future__ import annotations

import pytest

from core.agent import CognitiveAgent
from core.constants import AROUSAL_CEIL, AROUSAL_FLOOR
from core.global_workspace import GlobalWorkspace
from schemas.models import PerturbRequest, SimConfig, WorldStimulus


def _cfg(**overrides) -> SimConfig:
    """A deterministic SimConfig (fixed seed, no world noise) for the GWT tests."""
    cfg = SimConfig(random_seed=42, world_noise=0.0)
    return cfg.model_copy(update=overrides) if overrides else cfg


# --------------------------------------------------------------------------- #
# 1) arousal is bounded and rises with salient drivers
# --------------------------------------------------------------------------- #
def test_arousal_stays_in_unit_interval_over_cycles() -> None:
    """Arousal is always reported within the [0, 1] vigilance band."""
    agent = CognitiveAgent(SimConfig(random_seed=42))
    for _ in range(10):
        trace = agent.cognitive_cycle()
        assert AROUSAL_FLOOR <= trace.workspace.arousal <= AROUSAL_CEIL
        assert AROUSAL_FLOOR <= trace.metrics.arousal <= AROUSAL_CEIL


def test_arousal_rises_after_danger_world_stimulus() -> None:
    """Injecting a danger object into view raises arousal over the next cycles."""
    agent = CognitiveAgent(SimConfig(random_seed=42))
    before = agent.cognitive_cycle().workspace.arousal

    # Bottom-up perturbation: a high-intensity hazard right next to the agent so
    # perception surfaces it on the following observe() and vigilance climbs.
    agent.world_stimulus(
        WorldStimulus(
            kind="hazard",
            x=agent.world.agent_x + 1,
            y=agent.world.agent_y,
            intensity=3.0,
        )
    )
    after = [agent.cognitive_cycle().workspace.arousal for _ in range(2)]

    assert max(after) > before, (
        f"danger stimulus should raise arousal above {before:.3f}, got {after}"
    )
    assert all(AROUSAL_FLOOR <= a <= AROUSAL_CEIL for a in after)


def test_arousal_rises_after_surprise_perturbation() -> None:
    """A queued 'surprise' perturbation (forced prediction error) raises arousal."""
    agent = CognitiveAgent(SimConfig(random_seed=7))
    before = agent.cognitive_cycle().workspace.arousal

    agent.perturb(PerturbRequest(type="surprise", magnitude=1.0))
    after = [agent.cognitive_cycle().workspace.arousal for _ in range(2)]

    assert max(after) > before, (
        f"surprise perturbation should raise arousal above {before:.3f}, got {after}"
    )
    assert all(AROUSAL_FLOOR <= a <= AROUSAL_CEIL for a in after)


# --------------------------------------------------------------------------- #
# 2) higher arousal lowers the effective ignition threshold
# --------------------------------------------------------------------------- #
def _arousal_coalitions(gw: GlobalWorkspace):
    """A borderline field: one moderate leader over two weak rivals."""
    return [
        gw.make_coalition("perception", "objet", 0.55, 0.9, [1.0, 0.0]),
        gw.make_coalition("memory", "memory record", 0.35, 0.7, [0.0, 1.0]),
        gw.make_coalition("motivation", "need", 0.08, 0.4, [0.5, 0.5]),
    ]


def test_high_arousal_lowers_effective_threshold_and_is_at_least_as_likely_to_ignite() -> None:
    """High arousal => lower effective_threshold and >= likelihood of igniting.

    The SAME field is competed twice (fresh workspaces so neither sees the other's
    adaptive score history). High vigilance must not RAISE the bar, and it must not
    be LESS likely to ignite than the low-vigilance run.
    """
    cfg = _cfg()

    gw_high = GlobalWorkspace(cfg)
    ws_high = gw_high.compete(_arousal_coalitions(gw_high), cfg, arousal=0.95)

    gw_low = GlobalWorkspace(cfg)
    ws_low = gw_low.compete(_arousal_coalitions(gw_low), cfg, arousal=0.05)

    # Rising vigilance lowers the cutoff for conscious access.
    assert ws_high.effective_threshold < ws_low.effective_threshold
    # ... and is at least as likely to ignite (>= as ints: True(1) >= False(0)).
    assert int(ws_high.ignited) >= int(ws_low.ignited)


def test_arousal_can_flip_ignition_on_a_borderline_field() -> None:
    """A borderline winner ignites under high arousal but stays subliminal under low.

    The ignition score lands between the high- and low-arousal effective thresholds,
    so vigilance is the deciding factor for conscious access on this exact field.
    """
    cfg = _cfg()

    gw_high = GlobalWorkspace(cfg)
    ws_high = gw_high.compete(_arousal_coalitions(gw_high), cfg, arousal=0.95)

    gw_low = GlobalWorkspace(cfg)
    ws_low = gw_low.compete(_arousal_coalitions(gw_low), cfg, arousal=0.05)

    # Same field, same winner, same ignition score either way.
    assert ws_high.winner_source == ws_low.winner_source == "perception"
    assert ws_high.ignition_score == pytest.approx(ws_low.ignition_score, abs=1e-9)
    # Score sits in the band between the two effective thresholds => arousal flips it.
    assert ws_high.effective_threshold <= ws_high.ignition_score < ws_low.effective_threshold
    assert ws_high.ignited is True
    assert ws_low.ignited is False


# --------------------------------------------------------------------------- #
# 3) dominance matters: a clear leader ignites, a flat field does not
# --------------------------------------------------------------------------- #
def test_dominant_coalition_ignites_but_flat_field_does_not() -> None:
    """A runaway strong winner ignites; an equal/flat field has no dominance => no ignition."""
    cfg = _cfg()

    gw_dom = GlobalWorkspace(cfg)
    dominant = [
        gw_dom.make_coalition("perception", "salient object", 0.95, 0.95, [1.0, 0.0, 0.0]),
        gw_dom.make_coalition("memory", "weak memory", 0.08, 0.4, [0.0, 1.0, 0.0]),
        gw_dom.make_coalition("motivation", "weak need", 0.06, 0.3, [0.0, 0.0, 1.0]),
    ]
    ws_dom = gw_dom.compete(dominant, cfg)

    gw_flat = GlobalWorkspace(cfg)
    flat = [
        gw_flat.make_coalition("perception", "A", 0.5, 0.6, [0.1, 0.2]),
        gw_flat.make_coalition("memory", "B", 0.5, 0.6, [0.1, 0.2]),
        gw_flat.make_coalition("motivation", "C", 0.5, 0.6, [0.1, 0.2]),
        gw_flat.make_coalition("interoception", "D", 0.5, 0.6, [0.1, 0.2]),
    ]
    ws_flat = gw_flat.compete(flat, cfg)

    # Clear leader: high dominance, ignites, broadcasts the winner verbatim.
    assert ws_dom.ignited is True
    assert ws_dom.winner_source == "perception"
    assert ws_dom.dominance > ws_flat.dominance

    # Flat field: zero relative dominance => sub-threshold ignition score => no access,
    # even though every bid is individually strong (0.5 activation).
    assert ws_flat.ignited is False
    assert ws_flat.dominance == pytest.approx(0.0, abs=1e-6)
    assert ws_flat.ignition_score < ws_flat.effective_threshold


# --------------------------------------------------------------------------- #
# 4) hysteresis: maintenance_source sustains a borderline winner
# --------------------------------------------------------------------------- #
def _hysteresis_coalitions(gw: GlobalWorkspace):
    """Two near-tied bids; 'perception' edges 'memory' absent any maintenance."""
    return [
        gw.make_coalition("perception", "p", 0.50, 0.8, [1.0, 0.0]),
        gw.make_coalition("memory", "m", 0.48, 0.8, [0.0, 1.0]),
    ]


def test_maintenance_source_raises_effective_drive_of_borderline_coalition() -> None:
    """Passing maintenance_source for a borderline rival boosts its drive so it wins.

    Without maintenance, 'perception' narrowly wins. Feeding the previously-broadcast
    source ('memory') back in as maintenance_source applies the hysteresis boost, so
    'memory' overtakes and its winning drive (winner_strength) is >= the no-maintenance
    winner's — a sustained train of thought.
    """
    cfg = _cfg()

    gw_none = GlobalWorkspace(cfg)
    ws_none = gw_none.compete(_hysteresis_coalitions(gw_none), cfg)

    gw_maint = GlobalWorkspace(cfg)
    ws_maint = gw_maint.compete(
        _hysteresis_coalitions(gw_maint), cfg, maintenance_source="memory"
    )

    # No maintenance: the higher raw bid ('perception') wins the near-tie.
    assert ws_none.winner_source == "perception"
    # Maintenance sustains the previously-broadcast 'memory' coalition into the win.
    assert ws_maint.winner_source == "memory"
    # The maintained winner's effective drive is at least the no-maintenance winner's.
    assert ws_maint.winner_strength >= ws_none.winner_strength


# --------------------------------------------------------------------------- #
# 5) cross-cycle: healthy ignition rate + non-empty awareness while a winner exists
# --------------------------------------------------------------------------- #
def test_cross_cycle_ignition_rate_and_awareness_are_healthy() -> None:
    """Over 80 default cycles ignition fires sometimes (not never/always) and the
    attention schema always reflects a real dominant content while a winner exists.

    This complements tests/test_ignition_fix.py; both are kept.
    """
    agent = CognitiveAgent(SimConfig())
    n = 80
    ignited = 0
    empty_field_while_winner = 0
    for _ in range(n):
        trace = agent.cognitive_cycle()
        if trace.workspace.ignited:
            ignited += 1
        winner_present = trace.workspace.winner_source is not None
        if winner_present and "no content available" in trace.attention_schema.aware_of:
            empty_field_while_winner += 1

    rate = ignited / n
    assert 0.0 < rate < 1.0, f"ignition rate should be in (0,1), got {rate:.2%}"
    assert empty_field_while_winner == 0, (
        f"attention_schema reported the empty-field string on "
        f"{empty_field_while_winner}/{n} ticks while a winner existed"
    )
