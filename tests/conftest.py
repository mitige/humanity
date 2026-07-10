"""Suite-wide isolation for every on-disk simulation artifact.

Tests must never read, append to, truncate, or checkpoint a user's live run.
Individual tests can still monkeypatch these locations more specifically.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_runtime_storage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect default memory, trace and checkpoint paths per test."""
    import core.checkpoint as checkpoint
    import storage.persistence as persistence
    import storage.trace_logger as trace_logger

    data_dir = tmp_path / "runtime-data"
    monkeypatch.setattr(persistence, "_DATA_DIR", data_dir)
    monkeypatch.setattr(
        persistence, "_DEFAULT_PATH", data_dir / "memory.json")
    monkeypatch.setattr(trace_logger, "_DATA_DIR", data_dir)
    monkeypatch.setattr(
        trace_logger, "_DEFAULT_PATH", data_dir / "traces.jsonl")
    monkeypatch.setattr(checkpoint, "CKPT_DIR", tmp_path / "checkpoints")
