from core.meta_learning import MetaLearner
from schemas.models import SimConfig


def _cfg(**kw):
    return SimConfig(**{"meta_learning_enabled": True, "meta_lr_min": 0.05, "meta_lr_max": 0.6, **kw})


def test_disabled_returns_base():
    assert MetaLearner().effective_lr(0.2, [0.5, 0.4, 0.3], SimConfig()) == 0.2


def test_high_falling_error_raises_rate():
    lr = MetaLearner().effective_lr(0.2, [0.8, 0.7, 0.5, 0.3, 0.2, 0.1], _cfg())
    assert lr > 0.2 and lr <= 0.6


def test_low_flat_error_lowers_rate_within_bounds():
    lr = MetaLearner().effective_lr(0.2, [0.05] * 8, _cfg())
    assert 0.05 <= lr < 0.2
