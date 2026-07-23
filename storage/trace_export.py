# storage/trace_export.py
"""Richer JSONL trace export (Phase 7): filters, projection, formats, analysis.

FUNCTIONAL NOTE: this module is a level-2 functional mechanism — pure functions
over the on-disk JSONL cognitive-trace file (one ``CycleTrace`` JSON object per
line, written by :class:`storage.trace_logger.TraceLogger`). It streams, filters,
projects, reformats, and aggregates recorded variables for observability and
data export. It is a measurement/reporting layer only: nothing here implies
subjective experience, and the agent whose traces are exported is not conscious,
sentient, or alive.
"""
from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from typing import Iterator

# Honest one-sentence disclaimer appended to every analysis report.
_ANALYSIS_DISCLAIMER = (
    "These are aggregate statistics over logged internal variables of a "
    "functional simulation; they are not evidence of subjective experience — "
    "the agent is not conscious."
)


def gender_scenario_export(manager, *, include_private: bool = False) -> dict:
    """Export a Phase-8 scenario with an explicit privacy boundary.

    The default export contains only manifest metadata, social context and the
    public observer layer. ``include_private=True`` is an explicit opt-in to the
    full experiment input, including configured private profiles.
    """
    manifest = getattr(manager, "gender_scenario_manifest", None)
    if manifest is None:
        raise ValueError("no gender-life scenario is installed")
    if include_private:
        return {
            "privacy": "private_experiment_input",
            "contains_private_profiles": True,
            "manifest": manifest.model_dump(mode="json"),
            "warning": (
                "This export contains configured felt profiles, body preferences "
                "and undisclosed experiment inputs. Do not treat it as observer "
                "knowledge or as a diagnostic record."
            ),
        }
    society = manager.gender_society.state()
    return {
        "privacy": "public_projection",
        "contains_private_profiles": False,
        "manifest": {
            "schema_version": manifest.schema_version,
            "scenario_id": manifest.scenario_id,
            "preset_id": manifest.preset_id,
            "seed": manifest.seed,
            "enable": manifest.enable,
            "configured_agent_ids": sorted(manifest.agents),
            "social_context": manifest.social_context.model_dump(mode="json"),
        },
        "society": society.model_dump(mode="json"),
        "warning": (
            "Public projection only. Private felt profiles, body goals, "
            "internalized pressure and undisclosed intents are excluded."
        ),
    }


def _as_float(value: object, default: float = 0.0) -> float:
    """Coerce ``value`` to a FINITE float, returning ``default`` on any failure.

    ``json.loads`` accepts the bare tokens ``NaN``/``Infinity``/``-Infinity``
    (and arbitrarily large integer literals), so a trace file can legally carry
    non-finite or overflowing numbers. Those are treated as 'not a usable
    reading' and coerced to ``default`` so every aggregate stays finite and
    strict-JSON serializable.
    """
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _as_int(value: object, default: int = 0) -> int:
    """Coerce ``value`` to int, returning ``default`` on any failure.

    ``OverflowError`` covers ``int(float('inf'))`` from an ``Infinity`` token
    in the JSONL.
    """
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default


def _sub_dict(trace: dict, key: str) -> dict:
    """Return ``trace[key]`` when it is a dict, else an empty dict (old files)."""
    value = trace.get(key)
    return value if isinstance(value, dict) else {}


def tail_traces(path: str | Path, *, limit: int = 50,
                block_size: int = 64 * 1024) -> list[dict]:
    """Read only enough bytes from the end of a JSONL file for its latest rows."""
    file_path = Path(path)
    wanted = max(1, int(limit))
    chunk_size = max(1024, int(block_size))
    if not file_path.exists():
        return []
    try:
        with file_path.open("rb") as handle:
            handle.seek(0, 2)
            position = handle.tell()
            chunks: list[bytes] = []
            newline_count = 0
            while position > 0 and newline_count <= wanted:
                size = min(chunk_size, position)
                position -= size
                handle.seek(position)
                chunk = handle.read(size)
                chunks.append(chunk)
                newline_count += chunk.count(b"\n")
            payload = b"".join(reversed(chunks))
            lines = payload.splitlines()
            if position > 0 and lines:
                handle.seek(position - 1)
                if handle.read(1) != b"\n":
                    lines = lines[1:]
    except OSError:
        return []

    traces: list[dict] = []
    for raw_line in lines[-wanted:]:
        try:
            trace = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(trace, dict):
            traces.append(trace)
    return traces


def iter_traces(path: str | Path, *, from_tick: int | None = None,
                to_tick: int | None = None, ignited_only: bool = False,
                fields: list[str] | None = None,
                limit: int | None = None) -> Iterator[dict]:
    """Stream traces from the JSONL file at ``path``, one dict per matching line.

    The file is read line by line (never loaded whole). Malformed or non-object
    lines are skipped silently. Filters: inclusive ``[from_tick, to_tick]``
    range on ``trace["tick"]``; ``ignited_only`` keeps only traces whose
    ``workspace.ignited`` is truthy. ``fields`` projects each trace to the given
    TOP-LEVEL keys (``"tick"`` is always kept). ``limit`` stops the stream after
    that many yielded rows. A missing file yields nothing.
    """
    file_path = Path(path)
    if not file_path.exists():
        return
    yielded = 0
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if limit is not None and yielded >= limit:
                    return
                line = line.strip()
                if not line:
                    continue
                try:
                    trace = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(trace, dict):
                    continue
                tick = _as_int(trace.get("tick", 0))
                if from_tick is not None and tick < from_tick:
                    continue
                if to_tick is not None and tick > to_tick:
                    continue
                if ignited_only and not _sub_dict(trace, "workspace").get("ignited"):
                    continue
                if fields is not None:
                    keep = set(fields) | {"tick"}
                    trace = {k: v for k, v in trace.items() if k in keep}
                    trace.setdefault("tick", tick)
                yielded += 1
                yield trace
    except OSError:
        return


def _scalar(value: object) -> object:
    """Pass scalars through; JSON-dump anything non-scalar for CSV cells."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _flatten_row(row: dict) -> dict:
    """Flatten one row for CSV: dotted keys one level deep for ``metrics`` only."""
    flat: dict = {}
    for key, value in row.items():
        if key == "metrics" and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"metrics.{sub_key}"] = _scalar(sub_value)
        else:
            flat[key] = _scalar(value)
    return flat


def format_rows(rows: list[dict], fmt: str) -> tuple[str, str]:
    """Serialize ``rows`` as ``fmt`` in {"jsonl", "json", "csv"}.

    Returns ``(payload_string, media_type)``. ``jsonl`` emits one compact JSON
    object per line (``application/x-ndjson``); ``json`` wraps the rows as
    ``{"rows": [...], "count": N}`` (``application/json``); ``csv`` flattens
    the ``metrics`` sub-object one level deep with dotted keys, JSON-dumps any
    remaining non-scalar value, and uses the union of keys in first-seen order
    as header (``text/csv``). Unknown formats raise :class:`ValueError`.
    """
    if fmt == "jsonl":
        lines = [json.dumps(row, separators=(",", ":"), ensure_ascii=False)
                 for row in rows]
        payload = "\n".join(lines) + ("\n" if lines else "")
        return payload, "application/x-ndjson"
    if fmt == "json":
        payload = json.dumps({"rows": rows, "count": len(rows)},
                             ensure_ascii=False)
        return payload, "application/json"
    if fmt == "csv":
        flat_rows = [_flatten_row(row) for row in rows]
        header: list[str] = []
        seen: set[str] = set()
        for flat in flat_rows:
            for key in flat:
                if key not in seen:
                    seen.add(key)
                    header.append(key)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=header, restval="",
                                extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for flat in flat_rows:
            writer.writerow(flat)
        return buf.getvalue(), "text/csv"
    raise ValueError(f"unknown format: {fmt!r} (expected jsonl, json, or csv)")


def analysis(path: str | Path, *, window: int = 50) -> dict:
    """Aggregate statistics over the whole trace file in a single streaming pass.

    Returns a dict with trace counts, tick range, ignition rate, phi summaries
    (Φ_AR and causal Φ averaged over actual computation ticks, including valid
    zero results), mean prediction error, a windowed prediction-error
    curve (``window`` ticks per bucket, keyed by ``tick_start``), an action
    histogram from ``decision.action``, the sleeping fraction, the last seen
    ``metrics.wandering_occupancy``, and an honest disclaimer. Missing keys in
    old trace files default gracefully to 0/None; an empty or missing file
    yields sane zeros.
    """
    bucket_size = max(1, int(window))
    n_traces = 0
    tick_min: int | None = None
    tick_max: int | None = None
    n_ignited = 0
    sum_phi_proxy = 0.0
    max_phi_proxy = 0.0
    sum_phi_ar = 0.0
    n_phi_ar = 0
    max_phi_ar = 0.0
    sum_phi_causal = 0.0
    n_phi_causal = 0
    max_phi_causal = 0.0
    sum_pred_error = 0.0
    buckets: dict[int, list[float]] = {}   # tick_start -> [sum, count]
    action_histogram: dict[str, int] = {}
    n_sleeping = 0
    wandering_last = 0.0

    for trace in iter_traces(path):
        n_traces += 1
        tick = _as_int(trace.get("tick", 0))
        tick_min = tick if tick_min is None else min(tick_min, tick)
        tick_max = tick if tick_max is None else max(tick_max, tick)
        metrics = _sub_dict(trace, "metrics")
        if _sub_dict(trace, "workspace").get("ignited"):
            n_ignited += 1
        phi_proxy = _as_float(metrics.get("phi_proxy", 0.0))
        sum_phi_proxy += phi_proxy
        max_phi_proxy = max(max_phi_proxy, phi_proxy)
        phi_ar_state = _sub_dict(trace, "phi_ar")
        phi_ar = _as_float(phi_ar_state.get(
            "phi_ar", metrics.get("phi_ar", 0.0)))
        observation_tick = _as_int(
            (trace.get("observation") or {}).get("tick", -2), -2)
        phi_ar_computed = (
            bool(phi_ar_state)
            and _as_int(phi_ar_state.get("computed_at_tick", -1), -1)
            in {tick, observation_tick}
        )
        # Historical traces exposed only the metric; for those files a nonzero
        # reading remains the only available computation marker.
        if phi_ar_computed or (not phi_ar_state and phi_ar != 0.0):
            sum_phi_ar += phi_ar
            n_phi_ar += 1
            max_phi_ar = max(max_phi_ar, phi_ar)
        phi_causal_state = _sub_dict(trace, "phi_causal")
        phi_causal = _as_float(phi_causal_state.get(
            "phi_causal", metrics.get("phi_causal", 0.0)))
        phi_causal_computed = (
            bool(phi_causal_state)
            and _as_int(
                phi_causal_state.get("computed_at_tick", -1), -1)
            in {tick, observation_tick}
        )
        if (phi_causal_computed
                or (not phi_causal_state and phi_causal != 0.0)):
            sum_phi_causal += phi_causal
            n_phi_causal += 1
            max_phi_causal = max(max_phi_causal, phi_causal)
        pred_error = _as_float(metrics.get("prediction_error", 0.0))
        sum_pred_error += pred_error
        tick_start = (tick // bucket_size) * bucket_size
        acc = buckets.setdefault(tick_start, [0.0, 0.0])
        acc[0] += pred_error
        acc[1] += 1.0
        action = _sub_dict(trace, "decision").get("action")
        if isinstance(action, str) and action:
            action_histogram[action] = action_histogram.get(action, 0) + 1
        if metrics.get("is_sleeping"):
            n_sleeping += 1
        if "wandering_occupancy" in metrics:
            wandering_last = _as_float(metrics.get("wandering_occupancy", 0.0))

    denom = max(1, n_traces)
    error_curve = [
        {"tick_start": int(start), "mean": round(acc[0] / max(1.0, acc[1]), 6)}
        for start, acc in sorted(buckets.items())
    ]
    return {
        "n_traces": n_traces,
        "tick_range": [int(tick_min) if tick_min is not None else 0,
                       int(tick_max) if tick_max is not None else 0],
        "ignition_rate": round(n_ignited / denom, 6),
        "mean_phi_proxy": round(sum_phi_proxy / denom, 6),
        "max_phi_proxy": round(max_phi_proxy, 6),
        "mean_phi_ar": round(sum_phi_ar / max(1, n_phi_ar), 6),
        "n_phi_ar_computations": int(n_phi_ar),
        "max_phi_ar": round(max_phi_ar, 6),
        "mean_phi_causal": round(sum_phi_causal / max(1, n_phi_causal), 6),
        "n_phi_causal_computations": int(n_phi_causal),
        "max_phi_causal": round(max_phi_causal, 6),
        "mean_prediction_error": round(sum_pred_error / denom, 6),
        "error_curve": error_curve,
        "action_histogram": action_histogram,
        "sleep_fraction": round(n_sleeping / denom, 6),
        "wandering_occupancy_last": round(wandering_last, 6),
        "disclaimer": _ANALYSIS_DISCLAIMER,
    }
