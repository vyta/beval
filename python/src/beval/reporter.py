"""Result reporting for the beval framework.

Formats and outputs evaluation results to console or JSON.
See SPEC.md §12 (Results Schema).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from typing import Any

from beval.types import RunResult

# Optional CaseResult fields omitted from JSON when None.
_CASE_OPTIONAL = {
    "stages",
    "trials",
    "per_trial",
    "score_stddev",
    "score_min",
    "score_max",
    "pass_rate",
    "high_variance",
    "subject_output",
}

# Optional RunResult top-level fields omitted when None.
_RUN_OPTIONAL = {"label"}

# Optional RunConfig fields omitted when at default.
_CONFIG_DEFAULTS: dict[str, Any] = {
    "skip_mode": "exclude",
    "metric_weights": {},
    "active_layers": None,
    "pass_at_k": 1,
    "agent": None,
}

# Patterns identifying sensitive keys for scrubbing (§10.1).
_SENSITIVE_KEY_RE = re.compile(
    r"(secret|password|token|key|credential|auth|api.?key)",
    re.IGNORECASE,
)
_REDACTED = "***REDACTED***"


def _strip_defaults(d: dict[str, Any]) -> dict[str, Any]:
    """Remove optional fields that carry their default value."""
    out: dict[str, Any] = {}
    for key, val in d.items():
        if key in _CONFIG_DEFAULTS and val == _CONFIG_DEFAULTS[key]:
            continue
        out[key] = val
    return out


def _prepare(result: RunResult, *, scrub: bool = False) -> dict[str, Any]:
    """Build a JSON-ready dict from a RunResult, pruning null optionals."""
    raw = asdict(result)

    # Top-level optional fields
    for key in _RUN_OPTIONAL:
        if raw.get(key) is None:
            raw.pop(key, None)

    # Config: drop fields at defaults
    if "config" in raw:
        raw["config"] = _strip_defaults(raw["config"])

    # Cases: drop null optional fields and false high_variance
    for case in raw.get("cases", []):
        for key in _CASE_OPTIONAL:
            val = case.get(key)
            if val is None or val is False:
                case.pop(key, None)

    if scrub:
        raw = _scrub_sensitive(raw)

    return raw


def _scrub_sensitive(obj: Any) -> Any:
    """Recursively redact values whose keys match sensitive patterns (§10.1)."""
    if isinstance(obj, dict):
        return {
            k: (_REDACTED if _SENSITIVE_KEY_RE.search(k) else _scrub_sensitive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub_sensitive(item) for item in obj]
    return obj


def to_json(
    result: RunResult, *, indent: int = 2, scrub: bool = False
) -> str:
    """Serialize a RunResult to JSON string."""
    return json.dumps(
        _prepare(result, scrub=scrub), indent=indent, default=_json_default
    )


def write_json(result: RunResult, path: str, *, scrub: bool = False) -> None:
    """Write a RunResult to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_json(result, scrub=scrub))


def to_jsonl(
    result: RunResult, *, scrub: bool = False
) -> str:
    """Serialize a RunResult to JSONL (one JSON object per line)."""
    prepared = _prepare(result, scrub=scrub)
    lines: list[str] = []
    for case in prepared.get("cases", []):
        lines.append(json.dumps(case, default=_json_default))
    summary_obj = {"summary": prepared.get("summary", {})}
    lines.append(json.dumps(summary_obj, default=_json_default))
    return "\n".join(lines) + "\n"


def write_jsonl(result: RunResult, path: str, *, scrub: bool = False) -> None:
    """Write a RunResult to a JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_jsonl(result, scrub=scrub))


def _json_default(obj: Any) -> Any:
    """Handle non-serializable types."""
    if isinstance(obj, frozenset):
        return sorted(obj)
    if hasattr(obj, "value"):
        return obj.value
    msg = f"Object of type {type(obj).__name__} is not JSON serializable"
    raise TypeError(msg)
