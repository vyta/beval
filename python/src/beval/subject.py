"""Subject normalization for the beval framework.

Wraps system output into the normalized Subject interface.
See SPEC.md §7.2 (The Subject).
"""

from __future__ import annotations

from typing import Any

from beval.types import Subject


def normalize_subject(
    *,
    input: str | list[dict[str, Any]],  # noqa: A002
    output: str | list[dict[str, Any]],  # noqa: A002
    completion_time: float,
    tool_calls: list[dict[str, Any]] | None = None,
    spans: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
    stage: int | None = None,
    stage_name: str | None = None,
    prior_subject: Subject | None = None,
) -> Subject:
    """Create a normalized Subject from system output. See SPEC §2.2.

    The returned Subject is frozen (immutable) to prevent graders from
    modifying shared state.
    """
    return Subject(
        input=input,
        output=output,
        completion_time=completion_time,
        tool_calls=tool_calls or [],
        spans=spans or [],
        metadata=metadata or {},
        stage=stage,
        stage_name=stage_name,
        prior_subject=prior_subject,
    )
