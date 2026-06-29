from core.communication import build_message_content, message_coalition
from schemas.models import ConsciousMoment, Message, OtherMind


def _moment():
    return ConsciousMoment(tick=5, contents="Aware of: object 3 (food); affect: curiosity; action: approach.",
                           ignited=True, dominant_source="perception", awareness_level=0.7,
                           valence=0.4, phi_proxy=0.3, free_energy=-0.5, arousal=0.6,
                           summary="t5 summary")


def test_build_message_content_is_grounded_in_the_moment():
    content, vector = build_message_content(0, _moment())
    assert content.startswith("agent 0:")
    assert "curiosity" in content or "object 3" in content
    assert len(vector) == 4 and all(isinstance(v, float) for v in vector)


def test_message_coalition_precision_uses_trust():
    msg = Message(id=1, tick_emitted=4, sender_id=2, content="agent 2: ...",
                  vector=[0.5, 0.2, 0.1, 0.0], x=1, y=1, radius=4, ttl=2)
    trusted = OtherMind(agent_id=2, trust=0.9)
    untrusted = OtherMind(agent_id=2, trust=0.1)
    c_hi = message_coalition(msg, trusted)
    c_lo = message_coalition(msg, untrusted)
    assert c_hi.source == "communication"
    assert c_hi.precision > c_lo.precision
