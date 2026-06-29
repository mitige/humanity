from schemas.models import (
    AgentView, Message, OtherMind, SocialState, Observation, CycleTrace, SimConfig,
)


def test_social_models_have_safe_defaults():
    av = AgentView(id=2, x=1, y=1, distance=2.0)
    assert av.last_action is None and av.dominant_affect == "neutral" and av.valence == 0.0

    msg = Message(id=1, tick_emitted=3, sender_id=0, content="hi", x=4, y=4, radius=4, ttl=2)
    assert msg.vector == [] and msg.sender_id == 0

    om = OtherMind(agent_id=1)
    assert om.trust == 0.5 and om.familiarity == 0.0 and om.inferred_action is None

    ss = SocialState(agent_id=0)
    assert ss.others == [] and ss.affiliation_pressure == 0.0 and ss.received_count == 0


def test_observation_and_config_extensions_default_empty():
    obs = Observation(tick=0, agent_x=0, agent_y=0, agent_energy=10.0, radius=3, visible=[])
    assert obs.visible_agents == [] and obs.audible_messages == []
    cfg = SimConfig()
    assert cfg.n_agents == 1 and cfg.comm_radius == 4 and cfg.message_ttl == 2
    assert cfg.contagion_rate == 0.15 and cfg.affiliation_drive == 1.0
