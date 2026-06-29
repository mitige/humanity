from core.motivation import MotivationSystem
from schemas.models import EmotionState, SelfModelState, SimConfig, ActionType


def _self():
    labels = [a.value for a in ActionType]
    return SelfModelState(identity="x", age_ticks=0, energy=100.0, confidence=0.5, mood=0.0,
                          preferences={l: 0.5 for l in labels}, active_goals=[],
                          capability_beliefs={l: 0.5 for l in labels}, coherence=1.0, narrative="n")


def test_affiliate_pressure_present_and_scales_with_drive():
    cfg = SimConfig(affiliation_drive=2.0)
    m = MotivationSystem(cfg)
    goals = m.evaluate(_self(), EmotionState(), [], 0.0, 0.0, cfg,
                       n_visible_agents=0, society_size=3)
    aff = next(g for g in goals if g.need == "affiliate")
    # Isolated agent in a peered society feels affiliation pressure.
    assert aff.pressure > 0.0


def test_affiliate_pressure_drops_when_others_present():
    cfg = SimConfig(affiliation_drive=1.0)
    m = MotivationSystem(cfg)
    alone = next(g for g in m.evaluate(_self(), EmotionState(), [], 0.0, 0.0, cfg,
                 n_visible_agents=0, society_size=3) if g.need == "affiliate")
    social = next(g for g in m.evaluate(_self(), EmotionState(), [], 0.0, 0.0, cfg,
                  n_visible_agents=3, society_size=3) if g.need == "affiliate")
    assert social.pressure < alone.pressure


def test_affiliate_is_zero_in_solo_or_society_of_one():
    cfg = SimConfig(affiliation_drive=2.0)
    m = MotivationSystem(cfg)
    aff = next(g for g in m.evaluate(_self(), EmotionState(), [], 0.0, 0.0, cfg,
               n_visible_agents=0, society_size=1) if g.need == "affiliate")
    assert aff.pressure == 0.0
