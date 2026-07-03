from core.global_workspace import GlobalWorkspace
from schemas.models import SimConfig


def _coal(gw, source, content, activation, precision=0.9):
    return gw.make_coalition(source, content, activation=activation,
                             precision=precision, vector=[activation, 0.0])


def test_subliminal_content_deposits_a_trace():
    cfg = SimConfig(priming_enabled=True, priming_decay=0.8, priming_gain=1.0)
    gw = GlobalWorkspace(cfg)
    strong = _coal(gw, "perception", "P", 0.9)
    weak = _coal(gw, "injection", "S", 0.3)
    gw.compete([strong, weak], cfg)
    assert ("injection", "S") in gw._facilitation
    assert gw._facilitation[("injection", "S")] > 0.0


def test_bonus_applies_only_to_returning_content():
    cfg = SimConfig(priming_enabled=True, priming_decay=1.0, priming_gain=1.0)
    gw = GlobalWorkspace(cfg)
    # Tick 1: weak S present (deposits) alongside a strong rival.
    gw.compete([_coal(gw, "perception", "P", 0.9), _coal(gw, "injection", "S", 0.3)], cfg)
    # Tick 2: S present AGAIN immediately -> continuously present, no bonus.
    ws2 = gw.compete([_coal(gw, "perception", "P", 0.9), _coal(gw, "injection", "S", 0.3)], cfg)
    assert ws2.facilitation_applied == 0.0
    # Tick 3: S absent.
    gw.compete([_coal(gw, "perception", "P", 0.9)], cfg)
    # Tick 4: S returns -> facilitated now.
    ws4 = gw.compete([_coal(gw, "perception", "P", 0.2), _coal(gw, "injection", "S", 0.35)], cfg)
    winner_is_s = ws4.winner_source == "injection"
    assert winner_is_s
    assert ws4.facilitation_applied > 0.0


def test_traces_decay_and_evaporate():
    cfg = SimConfig(priming_enabled=True, priming_decay=0.1, priming_gain=1.0)
    gw = GlobalWorkspace(cfg)
    gw.compete([_coal(gw, "perception", "P", 0.9), _coal(gw, "injection", "S", 0.3)], cfg)
    first = gw._facilitation.get(("injection", "S"), 0.0)
    assert first > 0.0
    for _ in range(4):                       # S absent: trace decays hard
        gw.compete([_coal(gw, "perception", "P", 0.9)], cfg)
    assert gw._facilitation.get(("injection", "S"), 0.0) < first * 0.01 + 1e-9


def test_ignited_winner_does_not_deposit():
    cfg = SimConfig(priming_enabled=True, priming_decay=1.0, priming_gain=1.0,
                    competition_sharpness=1.0)
    gw = GlobalWorkspace(cfg)
    ws = gw.compete([_coal(gw, "perception", "P", 0.95, 0.95),
                     _coal(gw, "injection", "S", 0.2)], cfg)
    if ws.ignited:                            # broadcast content is consolidated
        assert ("perception", "P") not in gw._facilitation
    assert ("injection", "S") in gw._facilitation


def test_flag_off_no_traces_no_field():
    cfg = SimConfig()
    gw = GlobalWorkspace(cfg)
    ws = gw.compete([_coal(gw, "perception", "P", 0.9),
                     _coal(gw, "injection", "S", 0.3)], cfg)
    assert gw._facilitation == {}
    assert ws.facilitation_applied == 0.0
