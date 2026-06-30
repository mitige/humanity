from core.personality import PersonalityModel
from schemas.models import EmotionState


def test_novelty_drives_openness_and_label():
    p = PersonalityModel()
    for _ in range(30):
        st = p.update(novelty_experienced=1.0, danger_experienced=0.0, drift=0.3)
    assert st.novelty_seeking > 0.7 and st.openness > 0.6
    assert "explor" in st.label.lower() or "audac" in st.label.lower()


def test_danger_drives_caution():
    p = PersonalityModel()
    for _ in range(30):
        st = p.update(novelty_experienced=0.0, danger_experienced=1.0, drift=0.3)
    assert st.caution > 0.7 and "prudent" in st.label.lower()


def test_modulate_is_bounded_and_shifts_affect():
    p = PersonalityModel()
    for _ in range(30):
        p.update(novelty_experienced=0.0, danger_experienced=1.0, drift=0.3)
    out = p.modulate(EmotionState(fear=0.4, curiosity=0.4))
    assert 0.0 <= out.fear <= 1.0 and out.fear >= 0.4


def test_two_histories_diverge():
    bold, timid = PersonalityModel(), PersonalityModel()
    for _ in range(30):
        bold.update(novelty_experienced=1.0, danger_experienced=0.0, drift=0.3)
        timid.update(novelty_experienced=0.0, danger_experienced=1.0, drift=0.3)
    assert bold.update(0.5, 0.5, 0.0).label != timid.update(0.5, 0.5, 0.0).label
