# core/world_dynamics.py
"""Continuous world dynamics (Phase 7): regrowth, hazard cycles, seasons, drift.

FUNCTIONAL NOTE: this module is plain environment physics — deterministic
update rules that make the grid world a *living* habitat (renewable food
patches, hazards that wax and wane, seasonal resource cycles, slowly drifting
objects). Nothing here is cognitive, let alone conscious; it only enriches the
dynamics the simulated agents inhabit.

DETERMINISM (load-bearing): none of these functions consumes the world RNG.
Every update is a pure function of (tick, object id, spawn-time metadata), so
enabling the flag never shifts the seeded random stream, and disabling it
leaves prior-phase behaviour byte-identical.
"""
from __future__ import annotations

import math
import zlib

from schemas.models import SimConfig, WorldObject

# Hazard danger oscillation period (ticks) — a slow, smooth breathing cycle.
_HAZARD_PERIOD: int = 40
# Golden-ratio conjugate used to derive a stable per-object phase from its id.
_GOLDEN: float = 0.6180339887498949


def season_factor(tick: int, period: int) -> float:
    """Seasonal abundance multiplier in [0.5, 1.5] (1.0 at the equinoxes)."""
    period = max(1, int(period))
    return 1.0 + 0.5 * math.sin(2.0 * math.pi * float(tick) / float(period))


def object_phase(object_id: int) -> float:
    """Stable per-object phase in [0, 2π) derived from its id (no RNG)."""
    return ((int(object_id) * _GOLDEN) % 1.0) * 2.0 * math.pi


def drift_step(object_id: int, epoch: int) -> tuple[int, int]:
    """Deterministic (dx, dy) in {-1,0,1}² for a drifting object at ``epoch``."""
    h = zlib.crc32(f"{int(object_id)}:{int(epoch)}".encode("utf-8"))
    return (h % 3) - 1, ((h >> 2) % 3) - 1


def apply_dynamics(
    objects: dict[int, WorldObject],
    spawn_meta: dict[int, dict],
    tick: int,
    config: SimConfig,
    drift_every: int,
) -> list[str]:
    """Advance one tick of continuous dynamics over ``objects`` in place.

    - food: energy_value regrows toward its spawn maximum by exponential
      saturation (a depleted patch replenishes; ``regrow_rate`` per tick);
    - hazard: danger breathes around its spawn base on a smooth cycle whose
      phase is a pure function of the object id;
    - tool / curio: drift one cell every ``drift_every`` ticks, direction a
      pure hash of (id, epoch), clamped to the grid.

    Returns human-readable event strings for notable changes. Consumes NO RNG.
    """
    events: list[str] = []
    g = int(config.grid_size)
    rate = float(config.regrow_rate)
    for obj in objects.values():
        meta = spawn_meta.get(obj.id)
        if obj.kind == "food":
            max_energy = float(meta["max_energy"]) if meta else float(obj.energy_value)
            if max_energy > 0.0 and obj.energy_value < max_energy:
                grown = obj.energy_value + rate * max_energy * (1.0 - obj.energy_value / max_energy)
                was_depleted = obj.energy_value <= 0.05
                obj.energy_value = round(float(min(max_energy, grown)), 4)
                if was_depleted and obj.energy_value > 0.05:
                    events.append(f"Food patch {obj.id} starts regrowing.")
        elif obj.kind == "hazard":
            base = float(meta["base_danger"]) if meta else float(obj.danger)
            wave = math.sin(2.0 * math.pi * float(tick) / float(_HAZARD_PERIOD)
                            + object_phase(obj.id))
            obj.danger = round(float(min(1.0, max(0.0, base * (0.75 + 0.25 * wave)))), 4)
        elif obj.kind in ("tool", "curio"):
            if drift_every > 0 and (tick + obj.id) % drift_every == 0:
                dx, dy = drift_step(obj.id, tick // drift_every)
                if dx or dy:
                    obj.x = int(min(g - 1, max(0, obj.x + dx)))
                    obj.y = int(min(g - 1, max(0, obj.y + dy)))
    return events
