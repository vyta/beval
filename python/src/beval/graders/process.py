"""Process-layer built-in graders.

These graders evaluate Subject spans and tool calls. See SPEC §4.5.
"""

from __future__ import annotations

from typing import Any

from beval.graders import register_grader
from beval.types import EvalContext, Grade, GraderLayer, Subject


def _has_span_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on named span presence."""
    span_name = args[0] if args else ""
    found = any(
        s.get("name") == span_name if isinstance(s, dict) else False
        for s in subject.spans
    )
    return Grade(
        criterion=criterion,
        score=1.0 if found else 0.0,
        metric="process",
        passed=found,
        detail=f"span '{span_name}' {'found' if found else 'not found'}",
        layer=GraderLayer.PROCESS,
    )


def _calls_tool_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on named tool call presence."""
    tool_name = args[0] if args else ""
    found = any(
        tc.get("name") == tool_name if isinstance(tc, dict) else False
        for tc in subject.tool_calls
    )
    return Grade(
        criterion=criterion,
        score=1.0 if found else 0.0,
        metric="process",
        passed=found,
        detail=f"tool '{tool_name}' {'called' if found else 'not called'}",
        layer=GraderLayer.PROCESS,
    )


def _tool_call_count_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on exact tool call count."""
    expected = int(args[0]) if args else 0
    actual = len(subject.tool_calls)
    passed = actual == expected
    score = 1.0 if passed else max(0.0, 1.0 - abs(actual - expected) / max(expected, 1))
    return Grade(
        criterion=criterion,
        score=score,
        metric="process",
        passed=passed,
        detail=f"{actual} tool calls (expected {expected})",
        layer=GraderLayer.PROCESS,
    )


def register_process_graders() -> None:
    """Register all process built-in graders."""
    register_grader(
        "should have span",
        _has_span_grader,
        layer=GraderLayer.PROCESS,
        metric="process",
    )
    register_grader(
        "should call tool",
        _calls_tool_grader,
        layer=GraderLayer.PROCESS,
        metric="process",
    )
    register_grader(
        "tool call count should be",
        _tool_call_count_grader,
        layer=GraderLayer.PROCESS,
        metric="process",
    )
