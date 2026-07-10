"""JSON persistence for the agent's autobiographical memory.

FUNCTIONAL NOTE: this stores plain data records produced by the simulation.
The records are serialized internal variables, not memories of any lived
experience — the agent is not conscious, sentient, or alive.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

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

    @classmethod
    def for_agent(cls, agent_id: int, n_agents: int) -> "MemoryStore":
        """Create the legacy solo store or an agent-specific society store."""
        path = (
            _DEFAULT_PATH
            if int(n_agents) <= 1
            else _DATA_DIR / f"memory-agent-{int(agent_id)}.json"
        )
        return cls(path)

    def path(self) -> str:
        """Return the absolute path of the backing JSON file."""
        return str(self._path)

    def _ensure_dir(self) -> None:
        """Create the parent directory if it does not yet exist."""
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _prepare_records(self, records: list[MemoryRecord]) -> Path:
        """Write and fsync a complete replacement beside the target file."""
        self._ensure_dir()
        payload = [record.model_dump(mode="json") for record in records]
        fd, temp_name = tempfile.mkstemp(
            dir=str(self._path.parent),
            prefix=f".{self._path.name}.",
            suffix=".tmp",
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            return temp_path
        except Exception:
            try:
                temp_path.unlink()
            except OSError:
                pass
            raise

    def save_records(self, records: list[MemoryRecord]) -> None:
        """Atomically replace the backing file with the serialized records."""
        atomic_save_batch([(self, records)])

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


def atomic_save_batch(
    entries: list[tuple[MemoryStore, list[MemoryRecord]]],
) -> None:
    """Commit several memory stores as one rollback-safe filesystem batch.

    All JSON replacements are fully serialized and fsynced before the first
    live path changes. Existing files are moved to same-directory rollback
    names while the prepared files are installed; any failure restores every
    prior file, including stores already committed earlier in the batch.
    """
    if not entries:
        return
    targets = [store._path.resolve() for store, _records in entries]
    if len(set(targets)) != len(targets):
        raise ValueError("memory persistence targets must be distinct")

    prepared: list[tuple[Path, Path]] = []
    committed: list[tuple[Path, Path | None]] = []
    commit_succeeded = False
    try:
        for store, records in entries:
            prepared.append((store._path, store._prepare_records(records)))

        for target, desired in prepared:
            backup: Path | None = None
            if target.exists():
                fd, backup_name = tempfile.mkstemp(
                    dir=str(target.parent),
                    prefix=f".{target.name}.",
                    suffix=".rollback",
                )
                os.close(fd)
                backup = Path(backup_name)
                backup.unlink()
                target.replace(backup)
            committed.append((target, backup))
            desired.replace(target)
        commit_succeeded = True
    except Exception as exc:
        rollback_errors: list[str] = []
        for target, backup in reversed(committed):
            try:
                if backup is not None and backup.exists():
                    # Replace atomically; never unlink the installed target
                    # first or a failed recovery could destroy both copies.
                    backup.replace(target)
                elif backup is None and target.exists():
                    target.unlink()
            except OSError as rollback_exc:
                rollback_errors.append(
                    f"{target} (recovery copy: {backup}): {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                "memory batch commit failed and rollback was incomplete; "
                "recovery copies were retained: " + "; ".join(rollback_errors)
            ) from exc
        raise
    finally:
        for _target, desired in prepared:
            try:
                desired.unlink()
            except OSError:
                pass
        for _target, backup in committed:
            if commit_succeeded and backup is not None:
                try:
                    backup.unlink()
                except OSError:
                    pass
