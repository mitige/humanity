from core.constants import (
    WORKSPACE_SOURCES, CONTAGION_EMA, TRUST_EMA, FAMILIARITY_EMA,
)


def test_social_sources_registered():
    assert "communication" in WORKSPACE_SOURCES
    assert "social" in WORKSPACE_SOURCES


def test_social_emas_in_unit_range():
    for v in (CONTAGION_EMA, TRUST_EMA, FAMILIARITY_EMA):
        assert 0.0 < v <= 1.0
