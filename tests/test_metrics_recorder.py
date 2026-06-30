from core.metrics_recorder import MetricsRecorder, RECORDER_FIELDS
from schemas.models import Metrics, EmotionState


def _metrics(tick, energy):
    return Metrics(tick=tick, prediction_error=0.1, self_coherence=1.0, attention_focus=0.5,
                   working_memory_load=0.2, autobiographical_memory_count=0, goal_pressure=0.3,
                   emotional_state=EmotionState(), energy=energy, uncertainty=0.4,
                   novelty_score=0.2, action_confidence=0.6)


def test_records_and_respects_bound():
    r = MetricsRecorder(max_ticks=3)
    for t in range(5):
        r.record(0, _metrics(t, 100.0 - t))
    rows = r.series().rows
    assert len(rows) == 3 and rows[0]["tick"] == 2 and rows[-1]["tick"] == 4
    assert rows[0]["agent_id"] == 0 and "energy" in rows[0]


def test_csv_and_json_well_formed():
    r = MetricsRecorder()
    r.record(1, _metrics(0, 99.0))
    csv_text = r.to_csv()
    header = csv_text.splitlines()[0].split(",")
    assert header == RECORDER_FIELDS
    import json
    obj = json.loads(r.to_json())
    assert obj["fields"] == RECORDER_FIELDS and len(obj["rows"]) == 1
