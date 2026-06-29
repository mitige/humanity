from core.curiosity import Curiosity
from schemas.models import SimConfig


def test_disabled_or_too_few_errors_is_neutral():
    c = Curiosity()
    assert c.update([0.5], SimConfig(curiosity_enabled=True)).boredom == 0.0
    assert c.update([0.1] * 8, SimConfig(curiosity_enabled=False)).boredom == 0.0


def test_learning_progress_positive_when_error_falls():
    c = Curiosity()
    st = c.update([0.8, 0.7, 0.6, 0.3, 0.2, 0.1], SimConfig(curiosity_enabled=True, curiosity_window=6))
    assert st.learning_progress > 0.0 and st.intrinsic_reward > 0.0


def test_boredom_high_when_error_low_and_flat():
    c = Curiosity()
    st = c.update([0.05] * 8, SimConfig(curiosity_enabled=True, curiosity_window=8))
    assert st.boredom > 0.5
