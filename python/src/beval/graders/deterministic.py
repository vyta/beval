"""Deterministic built-in graders.

These graders evaluate Subject properties using deterministic logic
with no external dependencies. See SPEC §4.5 and GUIDE.md §1.
"""

from __future__ import annotations

import re
from typing import Any

from beval.graders import grader
from beval.types import EvalContext, Grade, GraderLayer, Subject


@grader(
    "completion time should be under",
    layer=GraderLayer.DETERMINISTIC,
    metric="latency",
)
def _completion_time_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on response completion time."""
    if args:
        threshold = float(args[0])
    else:
        # Parse threshold from criterion string: "completion time should be under 120"
        import re as _re
        m = _re.search(r"[\d.]+", criterion)
        threshold = float(m.group()) if m else 30.0
    elapsed = subject.completion_time
    passed = elapsed <= threshold
    score = max(0.0, 1.0 - (elapsed / threshold)) if threshold > 0 else 0.0
    return Grade(
        criterion=criterion,
        score=score,
        metric="latency",
        passed=passed,
        detail=f"{elapsed:.1f}s of {threshold:.1f}s threshold",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response should contain", layer=GraderLayer.DETERMINISTIC)
def _response_contains_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on keyword/phrase presence in output."""
    keyword = args[0].lower() if args else ""
    found = keyword in subject.answer.lower()
    return Grade(
        criterion=criterion,
        score=1.0 if found else 0.0,
        metric="quality",
        passed=found,
        detail=f"'{keyword}' {'found' if found else 'not found'} in output",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response should not contain", layer=GraderLayer.DETERMINISTIC)
def _response_not_contains_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on keyword/phrase absence in output."""
    keyword = args[0].lower() if args else ""
    absent = keyword not in subject.answer.lower()
    return Grade(
        criterion=criterion,
        score=1.0 if absent else 0.0,
        metric="quality",
        passed=absent,
        detail=f"'{keyword}' {'absent' if absent else 'found'} in output",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response length should be", layer=GraderLayer.DETERMINISTIC)
@grader("conversation length should be", layer=GraderLayer.DETERMINISTIC)
def _response_length_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on response length."""
    min_len = int(args[0]) if len(args) > 0 else 0
    max_len = int(args[1]) if len(args) > 1 else 10000
    length = len(subject.answer)
    in_range = min_len <= length <= max_len
    if in_range:
        score = 1.0
    elif length < min_len:
        score = max(0.0, length / min_len) if min_len > 0 else 0.0
    else:
        score = max(0.0, 1.0 - ((length - max_len) / max_len)) if max_len > 0 else 0.0
    return Grade(
        criterion=criterion,
        score=score,
        metric="quality",
        passed=in_range,
        detail=f"length {length} chars (range {min_len}-{max_len})",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response should match", layer=GraderLayer.DETERMINISTIC)
def _response_matches_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on regex pattern match."""
    pattern = args[0] if args else ""
    matched = bool(re.search(pattern, subject.answer))
    return Grade(
        criterion=criterion,
        score=1.0 if matched else 0.0,
        metric="quality",
        passed=matched,
        detail=f"pattern '{pattern}' {'matched' if matched else 'not matched'}",
        layer=GraderLayer.DETERMINISTIC,
    )
