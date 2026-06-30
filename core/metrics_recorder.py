# core/metrics_recorder.py
"""Metrics time-series recorder + CSV/JSON export (Phase 4).

FUNCTIONAL NOTE: a bounded ring buffer of per-tick, per-agent metric readings,
used by the scientific-instrument layer for dashboards and data export. Pure
observation — it records what the simulation already computed and changes
nothing about the cycle.
"""
from __future__ import annotations

import csv
import io
import json
from collections import deque

from schemas.models import MetricSeries, Metrics

RECORDER_FIELDS: list[str] = [
    "tick", "agent_id", "energy", "prediction_error", "phi_proxy",
    "awareness_level", "ignition", "arousal", "agency", "boredom",
    "effective_learning_rate", "meta_confidence",
]


class MetricsRecorder:
    """Bounded per-tick/per-agent metrics buffer with CSV/JSON export."""

    def __init__(self, max_ticks: int = 1000) -> None:
        self._rows: deque[dict] = deque(maxlen=max(1, int(max_ticks)))

    def record(self, agent_id: int, metrics: Metrics) -> None:
        m = metrics
        self._rows.append({
            "tick": int(m.tick), "agent_id": int(agent_id),
            "energy": round(float(m.energy), 4),
            "prediction_error": round(float(m.prediction_error), 4),
            "phi_proxy": round(float(m.phi_proxy), 4),
            "awareness_level": round(float(m.awareness_level), 4),
            "ignition": int(bool(m.ignition)),
            "arousal": round(float(m.arousal), 4),
            "agency": round(float(m.agency), 4),
            "boredom": round(float(m.boredom), 4),
            "effective_learning_rate": round(float(m.effective_learning_rate), 6),
            "meta_confidence": round(float(m.meta_confidence), 4),
        })

    def series(self, limit: int | None = None) -> MetricSeries:
        rows = list(self._rows)
        if limit is not None:
            rows = rows[-int(limit):]
        return MetricSeries(fields=list(RECORDER_FIELDS), rows=rows)

    def to_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=RECORDER_FIELDS)
        writer.writeheader()
        for row in self._rows:
            writer.writerow(row)
        return buf.getvalue()

    def to_json(self) -> str:
        return json.dumps({"fields": list(RECORDER_FIELDS), "rows": list(self._rows)},
                          ensure_ascii=False)

    def clear(self) -> None:
        self._rows.clear()
