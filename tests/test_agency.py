from core.agency import Agency
from schemas.models import ActionType, Prediction, StepResult


def _pred(e, g):
    return Prediction(action=ActionType.INTERACT, target_id=1, expected_energy_delta=e,
                      expected_danger=0.0, expected_novelty=0.0, expected_goal_progress=g,
                      uncertainty=0.2, value=0.0)


def _result(e, g):
    return StepResult(tick=1, action=ActionType.INTERACT, target_id=1, energy_delta=e,
                      new_energy=50.0, events=[], actual={"goal_progress": g})


def test_agency_high_when_prediction_matches_outcome():
    st = Agency().compute(_pred(5.0, 0.5), _result(5.0, 0.5))
    assert st.agency > 0.95


def test_agency_low_when_outcome_surprising():
    st = Agency().compute(_pred(5.0, 0.5), _result(-8.0, 0.0))
    assert st.agency < 0.5
