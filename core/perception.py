"""Perception stage of the cognitive cycle.

FUNCTIONAL NOTE: This module performs a purely mechanical transformation of a
world :class:`Observation` into a list of :class:`Percept` objects. It encodes
no subjective experience whatsoever -- it computes relative geometry and
attenuates the stored novelty readings by how often each object has been seen.
The class is intentionally stateless so the same encoder can be reused across
agents and ticks without side effects.
"""
from __future__ import annotations

import math

from schemas.models import Observation, Percept


class Perception:
    """Encode a raw :class:`Observation` into relative :class:`Percept` features.

    The encoder is a pure function of its inputs: it never mutates the
    observation, the visible objects, or the ``seen_counts`` mapping. This keeps
    the perception stage deterministic and side-effect free, mirroring a
    feed-forward sensory transform.
    """

    def encode(
        self, observation: Observation, seen_counts: dict[int, int]
    ) -> list[Percept]:
        """Build one :class:`Percept` per visible object.

        For each visible object we compute the displacement relative to the
        agent (``dx``/``dy``), the euclidean ``distance``, and pass through the
        danger/utility/energy readings. Novelty is attenuated by familiarity so
        that objects the agent has already seen many times read as less novel:

            effective_novelty = novelty * (1 / (1 + seen_count))

        Args:
            observation: The current world observation (agent pose + visible
                objects with their possibly noise-jittered readings).
            seen_counts: Mapping of ``object_id`` -> number of prior
                observations/reveals of that object. Missing ids count as 0.

        Returns:
            A list of percepts, one per visible object, in the order the
            objects appear in ``observation.visible``.
        """
        percepts: list[Percept] = []
        for obj in observation.visible:
            dx = int(obj.x - observation.agent_x)
            dy = int(obj.y - observation.agent_y)
            distance = float(math.hypot(dx, dy))

            # Familiarity attenuation: the more often an object has been seen,
            # the lower its effective novelty contribution to perception.
            seen = int(seen_counts.get(obj.id, 0))
            attenuated_novelty = float(obj.novelty) * (1.0 / (1.0 + seen))

            percepts.append(
                Percept(
                    object_id=int(obj.id),
                    kind=obj.kind,
                    dx=dx,
                    dy=dy,
                    distance=distance,
                    danger=float(obj.danger),
                    novelty=attenuated_novelty,
                    utility=float(obj.utility),
                    energy_value=float(obj.energy_value),
                )
            )
        return percepts
