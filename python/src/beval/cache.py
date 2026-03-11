"""Response cache for system outputs and judge responses.

See SPEC.md §9.4 and GUIDE.md §3.1 for cache key strategies.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from beval.reporter import _scrub_sensitive
from beval.types import Subject

_DEFAULT_CACHE_DIR = ".beval/cache"


def _cache_dir() -> Path:
    """Resolve the cache directory from env or default."""
    return Path(os.environ.get("BEVAL_CACHE_DIR", _DEFAULT_CACHE_DIR))


def _cache_key(case_id: str, subject_input: str | list[Any]) -> str:
    """Derive a cache key from case ID and input content."""
    raw = json.dumps({"case_id": case_id, "input": subject_input}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def get_cached_subject(case_id: str, subject_input: str | list[Any]) -> Subject | None:
    """Retrieve a cached Subject if available."""
    key = _cache_key(case_id, subject_input)
    path = _cache_dir() / f"{key}.json"
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Subject(
        input=data.get("input", ""),
        output=data.get("output", ""),
        completion_time=float(data.get("completion_time", 0.0)),
        tool_calls=data.get("tool_calls", []),
        spans=data.get("spans", []),
        metadata=data.get("metadata", {}),
        stage=data.get("stage"),
        stage_name=data.get("stage_name"),
    )


def put_cached_subject(case_id: str, subject: Subject) -> None:
    """Store a Subject in the cache."""
    key = _cache_key(case_id, subject.input)
    cache_dir = _cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    data = asdict(subject)
    # Remove recursive prior_subject to keep cache files flat
    data.pop("prior_subject", None)
    data = _scrub_sensitive(data)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    cache_dir = _cache_dir()
    if not cache_dir.is_dir():
        return {"entries": 0, "size_bytes": 0, "directory": str(cache_dir)}
    files = list(cache_dir.glob("*.json"))
    total_size = sum(f.stat().st_size for f in files)
    return {
        "entries": len(files),
        "size_bytes": total_size,
        "directory": str(cache_dir),
    }


def cache_clear() -> int:
    """Clear all cached responses. Returns the number of entries removed."""
    cache_dir = _cache_dir()
    if not cache_dir.is_dir():
        return 0
    files = list(cache_dir.glob("*.json"))
    for f in files:
        f.unlink()
    return len(files)
