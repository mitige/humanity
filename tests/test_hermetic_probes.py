"""Regression tests for disk-free scientific probes.

Scenarios and functional batteries are reproducibility tools.  They must never
observe or mutate the live instrument's persisted memory or trace stream, even
when a caller explicitly requests persistence in the supplied configuration.
"""

from core.scenario import ScenarioRunner
from core.test_battery import ConsciousnessTestBattery
from schemas.models import ConfigPatch, Scenario
from storage.persistence import MemoryStore
from storage.trace_logger import TraceLogger


def _forbid_probe_io(monkeypatch) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("a hermetic probe attempted disk I/O")

    monkeypatch.setattr(MemoryStore, "load_records", forbidden)
    monkeypatch.setattr(MemoryStore, "save_records", forbidden)
    monkeypatch.setattr(TraceLogger, "log", forbidden)


def test_scenario_is_hermetic_before_society_construction(monkeypatch):
    _forbid_probe_io(monkeypatch)
    scenario = Scenario(
        name="hermetic",
        config=ConfigPatch(
            n_agents=1,
            world_noise=0.0,
            persist_memory=True,
            trace_logging=True,
        ),
        ticks=2,
        seed=17,
    )

    result = ScenarioRunner().run(scenario)

    assert len(result.series.rows) == 2


def test_battery_is_hermetic_before_agent_construction(monkeypatch):
    _forbid_probe_io(monkeypatch)

    result = ConsciousnessTestBattery().false_memory_test(seed=17, ticks=1)

    assert result.test == "false_memory"
    assert result.detail["intruded"] is True
