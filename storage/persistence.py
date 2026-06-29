"""JSON persistence for the agent's autobiographical memory.

FUNCTIONAL NOTE: this stores plain data records produced by the simulation.
The records are serialized internal variables, not memories of any lived
experience — the agent is not conscious, sentient, or alive.
"""
from __future__ import annotations

import json
from pathlib import Path

from schemas.models import MemoryRecord

# Default on-disk location for persisted memory records.
_DATA_DIR = Path(__file__).resolve().parent / "data"
_DEFAULT_PATH = _DATA_DIR / "memory.json"


class MemoryStore:
    """Persist autobiographical :class:`MemoryRecord` objects to a JSON file.

    The store is robust to a missing file or directory and always round-trips
    through Pydantic so the on-disk representation stays schema-valid.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        """Create a store backed by ``path`` (defaults to storage/data/memory.json)."""
        self._path: Path = Path(path) if path is not None else _DEFAULT_PATH

    def path(self) -> str:
        """Return the absolute path of the backing JSON file."""
        return str(self._path)

    def _ensure_dir(self) -> None:
        """Create the parent directory if it does not yet exist."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save_records(self, records: list[MemoryRecord]) -> None:
        """Overwrite the backing file with ``records`` serialized as a JSON list."""
        self._ensure_dir()
        payload = [record.model_dump(mode="json") for record in records]
        with self._path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def load_records(self) -> list[MemoryRecord]:
        """Load and validate all records. Returns ``[]`` if the file is absent or empty."""
        if not self._path.exists():
            return []
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                raw = handle.read().strip()
        except OSError:
            return []
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Corrupt or partial file: treat as empty rather than crash the sim.
            return []
        if not isinstance(data, list):
            return []
        records: list[MemoryRecord] = []
        for item in data:
            try:
                records.append(MemoryRecord.model_validate(item))
            except Exception:
                # Skip individual malformed records but keep the rest.
                continue
        return records

    def clear(self) -> None:
        """Remove all persisted records (delete the backing file if present)."""
        try:
            self._path.unlink()
        except FileNotFoundError:
            return
        except OSError:
            return
