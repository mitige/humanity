from core.learning import PolicyLearner


def test_q_rises_with_repeated_positive_reward():
    pl = PolicyLearner()
    for _ in range(20):
        pl.update("interact", reward=8.0, lr=0.3)
    assert pl.bonus("interact") > 0.5
    assert pl.bonus("rest") == 0.0


def test_q_is_bounded_and_reward_recorded():
    pl = PolicyLearner()
    pl.update("explore", reward=1000.0, lr=1.0)
    assert -1.0 <= pl.bonus("explore") <= 1.0
    assert pl.last_reward == 1000.0
    assert pl.values()["explore"] == pl.bonus("explore")
