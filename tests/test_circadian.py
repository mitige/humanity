from core.circadian import Circadian
from schemas.models import SimConfig


def test_disabled_is_constant_daylight():
    c = Circadian()
    st = c.state(tick=13, config=SimConfig(circadian_enabled=False, circadian_period=50))
    assert st.daylight == 1.0 and st.is_night is False
    assert c.arousal_baseline(0.45, st.daylight, SimConfig(circadian_enabled=False)) == 0.45


def test_phase_cycles_and_night_at_midnight():
    cfg = SimConfig(circadian_enabled=True, circadian_period=40, night_threshold=0.3)
    c = Circadian()
    noon = c.state(tick=0, config=cfg)
    midnight = c.state(tick=20, config=cfg)
    assert noon.daylight > 0.9 and noon.is_night is False
    assert midnight.daylight < 0.1 and midnight.is_night is True


def test_arousal_baseline_drops_at_night():
    cfg = SimConfig(circadian_enabled=True, circadian_period=40)
    c = Circadian()
    day_b = c.arousal_baseline(0.5, c.state(0, cfg).daylight, cfg)
    night_b = c.arousal_baseline(0.5, c.state(20, cfg).daylight, cfg)
    assert night_b < day_b
