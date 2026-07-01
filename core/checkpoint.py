# core/checkpoint.py
"""Run checkpoints: save and resume the full live society state.

Serializes the picklable core of a :class:`SocietyManager` — config, shared
world (including its RNG state), every agent's internal state (world-model
beliefs, learned Q-values, personality, self-model, memory, concepts…), and the
metrics recorder — to a local file, so a run can be resumed exactly where it
left off. The manager's asyncio lock/task are intentionally excluded and rebuilt
on load.

FUNCTIONAL NOTE: this is bookkeeping over internal variables; it captures no
"experience". Checkpoints are plain pickles for LOCAL, trusted use only (never
load an untrusted checkpoint). They are version-bound: load with the same code
that saved them.
"""
from __future__ import annotations

import json
import pickle
import re
import time
from pathlib import Path

CKPT_DIR = Path("storage/checkpoints")
_SCHEMA = 1


def _safe(name: str) -> str:
    """Sanitize a checkpoint name to a safe filename stem."""
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(name).strip()).strip("-.")
    return stem[:64] or "checkpoint"


def save(manager, name: str) -> dict:
    """Pickle the manager's core state to ``storage/checkpoints/<name>.pkl``."""
    CKPT_DIR.mkdir(parents=True, exist_ok=True)
    stem = _safe(name)
    state = {
        "schema": _SCHEMA,
        "config": manager.config,
        "world": manager.world,
        "agents": manager.agents,
        "recorder": manager.recorder,
    }
    (CKPT_DIR / f"{stem}.pkl").write_bytes(
        pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL))
    meta = {
        "name": stem,
        "tick": int(manager.world.tick),
        "n_agents": len(manager.agents),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "bytes": (CKPT_DIR / f"{stem}.pkl").stat().st_size,
    }
    (CKPT_DIR / f"{stem}.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def load(manager, name: str) -> dict:
    """Restore the manager IN PLACE from a saved checkpoint."""
    stem = _safe(name)
    path = CKPT_DIR / f"{stem}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"checkpoint '{stem}' not found")
    state = pickle.loads(path.read_bytes())
    manager.pause()  # stop any running background loop before swapping state
    manager.config = state["config"]
    manager.world = state["world"]
    manager.agents = state["agents"]
    manager.recorder = state["recorder"]
    # Ensure every agent points at the restored shared world (shared refs survive a
    # single pickle, but rebind defensively so the society is always consistent).
    for agent in manager.agents.values():
        if getattr(agent, "_shared_world", None) is not None:
            agent._shared_world = manager.world
    return {"name": stem, "tick": int(manager.world.tick), "n_agents": len(manager.agents)}


def listing() -> list[dict]:
    """Return metadata for all saved checkpoints, newest first."""
    if not CKPT_DIR.exists():
        return []
    metas: list[dict] = []
    for meta_file in CKPT_DIR.glob("*.json"):
        if not (CKPT_DIR / f"{meta_file.stem}.pkl").exists():
            continue
        try:
            metas.append(json.loads(meta_file.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    return sorted(metas, key=lambda m: str(m.get("saved_at", "")), reverse=True)


def delete(name: str) -> bool:
    """Delete a checkpoint (both the pickle and its metadata). Returns found."""
    stem = _safe(name)
    found = False
    for suffix in (".pkl", ".json"):
        f = CKPT_DIR / f"{stem}{suffix}"
        if f.exists():
            f.unlink()
            found = True
    return found
