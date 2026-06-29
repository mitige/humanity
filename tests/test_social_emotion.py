# tests/test_social_emotion.py
from core.social_emotion import apply_contagion, update_trust
from schemas.models import AgentView, EmotionState, OtherMind


def test_contagion_moves_affect_toward_fearful_neighbour():
    own = EmotionState(fear=0.0, curiosity=0.2)
    neighbour = AgentView(id=1, x=1, y=1, distance=1.0, dominant_affect="fear", valence=-0.8)
    out = apply_contagion(own, [neighbour], {1: OtherMind(agent_id=1, trust=1.0)}, rate=0.5)
    assert out.fear > own.fear  # picked up the neighbour's fear


def test_contagion_is_noop_without_neighbours():
    own = EmotionState(fear=0.3, curiosity=0.4)
    out = apply_contagion(own, [], {}, rate=0.5)
    assert out == own


def test_trust_rises_on_positive_reward_near_other():
    om = OtherMind(agent_id=1, trust=0.5)
    update_trust(om, reward=1.0, rate=0.25)
    assert om.trust > 0.5
    update_trust(om, reward=-1.0, rate=0.25)
    assert om.trust < 0.625  # moved back down
