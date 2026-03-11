"""Baseline snapshot management for regression detection.

Saves evaluation results as baseline snapshots and compares subsequent
runs against them to detect score regressions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_BASELINE_DIR = ".beval"
_BASELINE_FILENAME = "baseline.json"


def _baseline_path() -> Path:
    """Resolve the baseline file path."""
    return Path(_DEFAULT_BASELINE_DIR) / _BASELINE_FILENAME


def save_baseline(result_data: dict[str, Any]) -> Path:
    """Save result data as the new baseline. Returns the file path."""
    path = _baseline_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)
    return path


def load_baseline() -> dict[str, Any] | None:
    """Load the current baseline. Returns None if no baseline exists."""
    path = _baseline_path()
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def clear_baseline() -> bool:
    """Remove the saved baseline. Returns True if a file was removed."""
    path = _baseline_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def compare_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any],
    *,
    threshold: float = 0.05,
) -> dict[str, Any]:
    """Compare current results against baseline and detect regressions.

    Returns a comparison dict with per-metric deltas and a regressions list.
    """
    cur_summary = current.get("summary", {})
    base_summary = baseline.get("summary", {})

    cur_metrics = cur_summary.get("metrics", {})
    base_metrics = base_summary.get("metrics", {})

    overall_delta = cur_summary.get("overall_score", 0.0) - base_summary.get(
        "overall_score", 0.0
    )

    metric_deltas: dict[str, float] = {}
    regressions: list[dict[str, Any]] = []

    all_metrics = set(cur_metrics) | set(base_metrics)
    for m in sorted(all_metrics):
        cur_val = cur_metrics.get(m, 0.0)
        base_val = base_metrics.get(m, 0.0)
        delta = cur_val - base_val
        metric_deltas[m] = delta
        if delta < -threshold:
            regressions.append({
                "metric": m,
                "baseline": base_val,
                "current": cur_val,
                "delta": delta,
            })

    if overall_delta < -threshold:
        regressions.insert(0, {
            "metric": "overall_score",
            "baseline": base_summary.get("overall_score", 0.0),
            "current": cur_summary.get("overall_score", 0.0),
            "delta": overall_delta,
        })

    return {
        "overall_delta": overall_delta,
        "metric_deltas": metric_deltas,
        "regressions": regressions,
        "regressed": len(regressions) > 0,
    }
