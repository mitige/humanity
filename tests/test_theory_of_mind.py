# tests/test_theory_of_mind.py
from core.theory_of_mind import TheoryOfMind
from schemas.models import AgentView, ActionType, Message


def test_familiarity_grows_with_repeated_exposure():
    tom = TheoryOfMind()
    av = AgentView(id=1, x=1, y=1, distance=1.0, last_action=ActionType.APPROACH,
                   dominant_affect="curiosity", valence=0.3)
    tom.update([av], [], tick=0)
    f1 = tom.model_of(1).familiarity
    tom.update([av], [], tick=1)
    f2 = tom.model_of(1).familiarity
    assert 0.0 < f1 < f2 <= 1.0


def test_infers_action_and_valence_from_view():
    tom = TheoryOfMind()
    av = AgentView(id=2, x=2, y=2, distance=2.0, last_action=ActionType.AVOID,
                   dominant_affect="fear", valence=-0.5)
    tom.update([av], [], tick=3)
    m = tom.model_of(2)
    assert m.inferred_action == ActionType.AVOID
    assert m.inferred_affect == "fear" and m.inferred_valence < 0.0
    assert m.last_seen_tick == 3


def test_social_coalition_scales_with_salience():
    tom = TheoryOfMind()
    near_intense = AgentView(id=1, x=1, y=1, distance=1.0, dominant_affect="fear", valence=-0.9)
    far_calm = AgentView(id=2, x=9, y=9, distance=9.0, dominant_affect="neutral", valence=0.0)
    tom.update([near_intense, far_calm], [], tick=0, grid_size=12)
    c = tom.social_coalition(grid_size=12)
    assert c is not None and c.source == "social"
    assert 0.0 <= c.activation <= 1.0


def test_no_others_yields_no_social_coalition():
    tom = TheoryOfMind()
    tom.update([], [], tick=0)
    assert tom.social_coalition(grid_size=12) is None
