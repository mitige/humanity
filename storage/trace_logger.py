"""JSONL export of per-tick cognitive traces.

FUNCTIONAL NOTE: each line is a snapshot of the simulation's internal variables
for a single tick. The trace is a debugging/observability artifact and does not
represent subjective experience — the agent is not conscious, sentient, or alive.
"""
from __future__ import annotations

import json
from pathlib import Path

from schemas.models import CycleTrace

# Default on-disk location for the JSONL cognitive-trace export.
_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_PATH = _DATA_DIR / "traces.jsonl"


class TraceLogger:
    """Append :class:`CycleTrace` objects as one JSON object per line (JSONL)."""

    def __init__(self, path: str | Path | None = None) -> None:
        """Create a logger writing to ``path`` (defaults to storage/data/traces.jsonl)."""
        self._path: Path = Path(path) if path is not None else _DEFAULT_PATH

    @classmethod
    def for_agent(cls, agent_id: int, n_agents: int) -> "TraceLogger":
        """Create the legacy solo logger or an agent-specific society logger."""
        path = (
            _DEFAULT_PATH
            if int(n_agents) <= 1
            else _DATA_DIR / f"traces-agent-{int(agent_id)}.jsonl"
        )
        return cls(path)

    def path(self) -> str:
        """Return the absolute path of the backing JSONL file."""
        return str(self._path)

    def _ensure_dir(self) -> None:
        """Create the parent directory if it does not yet exist."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, trace: CycleTrace) -> None:
        """Append ``trace`` as a single JSON line to the export file."""
        self._ensure_dir()
        line = json.dumps(trace.model_dump(mode="json"), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def clear(self) -> None:
        """Remove the trace export file if it exists."""
        try:
            self._path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return
