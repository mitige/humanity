# tests/test_trace_export.py
"""Unit tests for storage/trace_export.py (Phase 7 richer JSONL export).

Uses hand-written synthetic trace dicts mimicking the CycleTrace JSONL shape —
the simulation is never run. Pure file-based tests over tmp_path.
"""
from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path

import pytest

from storage.trace_export import analysis, format_rows, iter_traces, tail_traces


def _trace(tick: int, *, ignited: bool = False, pe: float = 0.1,
           phi: float = 0.2, phi_ar: float = 0.0, phi_causal: float = 0.0,
           sleeping: bool = False, wandering: float = 0.0,
           action: str = "MOVE") -> dict:
    """Build one synthetic trace dict shaped like CycleTrace.model_dump()."""
    return {
        "tick": tick,
        "workspace": {"ignited": ignited, "broadcast_strength": 0.5},
        "metrics": {
            "tick": tick,
            "prediction_error": pe,
            "phi_proxy": phi,
            "phi_ar": phi_ar,
            "phi_causal": phi_causal,
            "is_sleeping": sleeping,
            "wandering_occupancy": wandering,
        },
        "decision": {"action": action, "confidence": 0.7},
        "emotion": {"valence": 0.0, "arousal": 0.4},
    }


def _write_jsonl(path: Path, traces: list[dict],
                 malformed_at: int | None = None) -> None:
    """Write traces as JSONL, optionally inserting a malformed line."""
    lines = [json.dumps(t, ensure_ascii=False) for t in traces]
    if malformed_at is not None:
        lines.insert(malformed_at, "{this is not json]]")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture()
def trace_file(tmp_path: Path) -> Path:
    """A 20-tick synthetic trace file with one malformed line in the middle."""
    traces = []
    for t in range(20):
        traces.append(_trace(
            t,
            ignited=(t % 4 == 0),                 # 5 of 20 ignited
            pe=0.1 if t < 10 else 0.3,            # two error-curve buckets
            phi=0.2 + 0.01 * t,
            phi_ar=0.5 if t == 7 else 0.0,        # single nonzero reading
            phi_causal=0.25 if t in (3, 5) else 0.0,
            sleeping=(t >= 16),                    # 4 of 20 sleeping
            wandering=0.05 * t,
            action="MOVE" if t % 2 == 0 else "WAIT",
        ))
    path = tmp_path / "traces.jsonl"
    _write_jsonl(path, traces, malformed_at=10)
    return path


def test_iter_traces_tick_range(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file, from_tick=5, to_tick=8))
    assert [r["tick"] for r in rows] == [5, 6, 7, 8]


def test_iter_traces_ignited_only(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file, ignited_only=True))
    assert [r["tick"] for r in rows] == [0, 4, 8, 12, 16]
    assert all(r["workspace"]["ignited"] for r in rows)


def test_iter_traces_projection_keeps_tick(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file, fields=["metrics"], limit=3))
    assert len(rows) == 3
    for row in rows:
        assert set(row.keys()) == {"tick", "metrics"}
        assert isinstance(row["tick"], int)


def test_iter_traces_limit(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file, limit=4))
    assert [r["tick"] for r in rows] == [0, 1, 2, 3]


def test_tail_traces_returns_latest_rows_from_large_file(tmp_path: Path) -> None:
    path = tmp_path / "large.jsonl"
    _write_jsonl(path, [_trace(t) for t in range(2000)])

    rows = tail_traces(path, limit=5, block_size=1024)

    assert [row["tick"] for row in rows] == [1995, 1996, 1997, 1998, 1999]


def test_iter_traces_limit_zero_yields_nothing(trace_file: Path) -> None:
    """limit=0 is a real limit (zero rows), not 'unlimited'."""
    assert list(iter_traces(trace_file, limit=0)) == []


def test_iter_traces_skips_malformed_line(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file))
    assert len(rows) == 20          # 21 lines on disk, 1 malformed skipped
    assert [r["tick"] for r in rows] == list(range(20))


def test_iter_traces_missing_file(tmp_path: Path) -> None:
    assert list(iter_traces(tmp_path / "nope.jsonl")) == []


def test_format_rows_jsonl(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file, limit=3))
    payload, media = format_rows(rows, "jsonl")
    assert media == "application/x-ndjson"
    assert payload.endswith("\n")
    lines = [ln for ln in payload.splitlines() if ln]
    assert len(lines) == 3
    assert json.loads(lines[0])["tick"] == 0


def test_format_rows_json(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file, limit=5))
    payload, media = format_rows(rows, "json")
    assert media == "application/json"
    parsed = json.loads(payload)
    assert parsed["count"] == 5
    assert len(parsed["rows"]) == 5
    assert parsed["rows"][4]["tick"] == 4


def test_format_rows_csv_flattens_metrics(trace_file: Path) -> None:
    rows = list(iter_traces(trace_file, limit=2))
    payload, media = format_rows(rows, "csv")
    assert media == "text/csv"
    reader = csv.DictReader(io.StringIO(payload))
    parsed = list(reader)
    assert len(parsed) == 2
    assert "metrics.phi_proxy" in (reader.fieldnames or [])
    assert parsed[0]["metrics.phi_proxy"] == "0.2"
    # non-scalar top-level values are JSON-dumped strings
    workspace = json.loads(parsed[0]["workspace"])
    assert workspace["ignited"] is True


def test_format_rows_unknown_format() -> None:
    with pytest.raises(ValueError):
        format_rows([], "xml")


def test_analysis_aggregates(trace_file: Path) -> None:
    report = analysis(trace_file, window=10)
    assert report["n_traces"] == 20
    assert report["tick_range"] == [0, 19]
    assert report["ignition_rate"] == pytest.approx(5 / 20)
    assert report["mean_phi_ar"] == pytest.approx(0.5)          # one nonzero
    assert report["mean_phi_causal"] == pytest.approx(0.25)     # two nonzero
    assert report["mean_prediction_error"] == pytest.approx(0.2)
    assert report["max_phi_proxy"] == pytest.approx(0.39)
    assert report["action_histogram"] == {"MOVE": 10, "WAIT": 10}
    assert report["sleep_fraction"] == pytest.approx(4 / 20)
    assert report["wandering_occupancy_last"] == pytest.approx(0.95)
    assert "not conscious" in report["disclaimer"]
    curve = report["error_curve"]
    assert [b["tick_start"] for b in curve] == [0, 10]
    assert curve[0]["mean"] == pytest.approx(0.1)
    assert curve[1]["mean"] == pytest.approx(0.3)


def test_analysis_counts_zero_phi_only_on_actual_computation_ticks(
    tmp_path: Path,
) -> None:
    rows = [_trace(0), _trace(1), _trace(2)]
    rows[0]["phi_ar"] = {"phi_ar": 0.0, "computed_at_tick": 0}
    rows[0]["phi_causal"] = {
        "phi_causal": 0.0, "computed_at_tick": 0}
    # Held values on tick 1 must not be counted a second time.
    rows[1]["phi_ar"] = {"phi_ar": 0.0, "computed_at_tick": 0}
    rows[1]["phi_causal"] = {
        "phi_causal": 0.0, "computed_at_tick": 0}
    rows[2]["phi_ar"] = {"phi_ar": 0.6, "computed_at_tick": 2}
    rows[2]["phi_causal"] = {
        "phi_causal": 0.4, "computed_at_tick": 2}
    path = tmp_path / "computed-phi.jsonl"
    _write_jsonl(path, rows)

    report = analysis(path)

    assert report["mean_phi_ar"] == pytest.approx(0.3)
    assert report["n_phi_ar_computations"] == 2
    assert report["max_phi_ar"] == pytest.approx(0.6)
    assert report["mean_phi_causal"] == pytest.approx(0.2)
    assert report["n_phi_causal_computations"] == 2
    assert report["max_phi_causal"] == pytest.approx(0.4)


def test_analysis_counts_phi_from_real_generated_traces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration pin: agent timestamps and exporter computation ticks agree."""
    from core.society import SocietyManager
    from schemas.models import SimConfig
    from storage.trace_logger import TraceLogger

    trace_path = tmp_path / "real-phi.jsonl"
    monkeypatch.setattr(
        TraceLogger, "for_agent",
        classmethod(lambda cls, agent_id, n_agents: cls(trace_path)),
    )
    manager = SocietyManager(SimConfig(
        n_agents=1,
        n_objects=4,
        random_seed=42,
        world_noise=0.1,
        persist_memory=False,
        trace_logging=True,
        phi_ar_enabled=True,
        phi_ar_window=8,
        phi_ar_every=1,
        phi_causal_enabled=True,
        phi_causal_nodes=3,
        phi_causal_window=16,
        phi_causal_every=1,
    ))
    for _ in range(40):
        manager.tick()

    report = analysis(trace_path)

    assert report["n_phi_ar_computations"] > 0
    assert report["n_phi_causal_computations"] > 0
    # A valid integrated-information result may be exactly zero; computation
    # counts, not a scientifically unjustified positivity assumption, pin the
    # timestamp/export contract this integration test is about.


def test_analysis_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    report = analysis(empty)
    assert report["n_traces"] == 0
    assert report["tick_range"] == [0, 0]
    assert report["ignition_rate"] == 0.0
    assert report["mean_phi_proxy"] == 0.0
    assert report["mean_phi_ar"] == 0.0
    assert report["error_curve"] == []
    assert report["action_histogram"] == {}
    assert report["sleep_fraction"] == 0.0
    assert report["wandering_occupancy_last"] == 0.0
    assert "disclaimer" in report


def test_analysis_old_traces_missing_keys(tmp_path: Path) -> None:
    """Old trace files without Phase-7 keys must parse without error."""
    path = tmp_path / "old.jsonl"
    old = [{"tick": 1, "metrics": {"prediction_error": 0.4}},
           {"tick": 2}]
    _write_jsonl(path, old)
    report = analysis(path, window=50)
    assert report["n_traces"] == 2
    assert report["tick_range"] == [1, 2]
    assert report["mean_prediction_error"] == pytest.approx(0.2)
    assert report["wandering_occupancy_last"] == 0.0
    assert report["action_histogram"] == {}


def test_analysis_nonfinite_and_huge_values(tmp_path: Path) -> None:
    """NaN/Infinity tokens and overflowing int literals (all legal to
    ``json.loads``) must neither crash nor leak non-finite numbers into the
    report — non-finite readings are coerced to the 0.0 default."""
    path = tmp_path / "hostile.jsonl"
    lines = [
        '{"tick": Infinity, "metrics": {"prediction_error": NaN}}',
        '{"tick": 1, "metrics": {"phi_proxy": 1e999, '
        '"prediction_error": ' + "9" * 400 + "}}",
        '{"tick": 2, "metrics": {"prediction_error": 0.5}}',
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = list(iter_traces(path))            # must not raise OverflowError
    assert len(rows) == 3
    report = analysis(path)
    assert report["n_traces"] == 3
    assert report["tick_range"] == [0, 2]     # Infinity tick coerced to 0
    assert report["max_phi_proxy"] == 0.0     # 1e999 -> inf -> coerced out
    assert report["mean_prediction_error"] == pytest.approx(0.5 / 3, abs=1e-6)
    assert all(math.isfinite(b["mean"]) for b in report["error_curve"])
    # the whole report must survive strict JSON (what an API route emits)
    json.dumps(report, allow_nan=False)
