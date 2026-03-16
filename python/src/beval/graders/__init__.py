"""Grader registry and base grader interface.

See SPEC.md §7 (Graders) for registration model and pattern matching.
"""

from __future__ import annotations

import threading
import warnings
from collections.abc import Callable
from typing import Any

from beval.types import EvalContext, EvaluationMode, Grade, GraderLayer, Subject

# Type alias for grader handler functions
GraderHandler = Callable[
    [str, list[Any], Subject, EvalContext],  # criterion, args, subject, context
    Grade,
]


# Default mode-to-layer mapping. See SPEC §6.1.
_MODE_LAYERS: dict[EvaluationMode, set[str]] = {
    EvaluationMode.DEV: {GraderLayer.DETERMINISTIC.value},
    EvaluationMode.DEV_PROCESS: {
        GraderLayer.DETERMINISTIC.value,
        GraderLayer.PROCESS.value,
    },
    EvaluationMode.VALIDATION: {
        GraderLayer.DETERMINISTIC.value,
        GraderLayer.PROCESS.value,
        GraderLayer.AI_JUDGED.value,
    },
    EvaluationMode.MONITORING: {
        GraderLayer.DETERMINISTIC.value,
        GraderLayer.PROCESS.value,
        GraderLayer.AI_JUDGED.value,
    },
}


class GraderEntry:
    """A registered grader with its pattern, handler, and options."""

    def __init__(
        self,
        pattern: str,
        handler: GraderHandler,
        layer: str,
        metric: str,
    ) -> None:
        self.pattern = pattern.lower()
        self.handler = handler
        self.layer = layer
        self.metric = metric


_DEFAULT_GRADER_TIMEOUT = 30  # seconds


def _run_with_timeout(
    fn: Callable[..., Grade],
    args: tuple[Any, ...],
    timeout: float,
) -> Grade | None:
    r"""Run *fn(\*args)* in a daemon thread with a timeout.

    Returns ``None`` when the thread does not finish within *timeout* seconds.
    """
    result: list[Grade] = []
    error: list[Exception] = []

    def _target() -> None:
        try:
            result.append(fn(*args))
        except Exception as exc:  # noqa: BLE001
            error.append(exc)

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return None
    if error:
        raise error[0]
    return result[0] if result else None


# Global grader registry
_GRADER_REGISTRY: list[GraderEntry] = []
_BUILTIN_ENTRIES: list[GraderEntry] = []


def grader(
    pattern: str,
    *,
    layer: str = GraderLayer.DETERMINISTIC,
    metric: str = "quality",
) -> Callable[[GraderHandler], GraderHandler]:
    """Decorator to register a grader handler. See SPEC §4.1.

    Usage::

        @grader("response should contain", layer=GraderLayer.DETERMINISTIC)
        def _response_contains(criterion, args, subject, context):
            ...
    """

    def decorator(fn: GraderHandler) -> GraderHandler:
        entry = GraderEntry(pattern, fn, layer, metric)
        _BUILTIN_ENTRIES.append(entry)
        _GRADER_REGISTRY.append(entry)
        return fn

    return decorator


def register_builtin_graders() -> None:
    """Re-register all @grader-decorated built-in graders.

    Call this after ``clear_grader_registry()`` to restore built-ins.
    """
    for entry in _BUILTIN_ENTRIES:
        if entry not in _GRADER_REGISTRY:
            _GRADER_REGISTRY.append(entry)


def register_grader(
    pattern: str,
    handler: GraderHandler,
    *,
    layer: str = GraderLayer.DETERMINISTIC,
    metric: str = "quality",
) -> None:
    """Register a grader against a pattern. See SPEC §4.1."""
    pattern_lower = pattern.lower()
    for existing in _GRADER_REGISTRY:
        if existing.handler is not handler and (
            existing.pattern.startswith(pattern_lower)
            or pattern_lower.startswith(existing.pattern)
        ):
            warnings.warn(
                f"Grader pattern overlap: '{pattern_lower}' and "
                f"'{existing.pattern}' are prefix-related with different handlers",
                stacklevel=2,
            )
    _GRADER_REGISTRY.append(GraderEntry(pattern, handler, layer, metric))


def _active_layers(context: EvalContext) -> set[str]:
    """Return the set of active layer strings for the given context."""
    if context.config.active_layers is not None:
        return set(context.config.active_layers)
    return _MODE_LAYERS.get(context.mode, set())


def match_grader(criterion: str) -> GraderEntry | None:
    """Find the best grader via longest prefix match. See SPEC §4.2.

    Returns the grader with the longest matching prefix. Returns None when
    no pattern matches or when multiple patterns share the same longest
    prefix length (ambiguity).
    """
    criterion_lower = criterion.lower()
    matches: list[GraderEntry] = []
    for entry in _GRADER_REGISTRY:
        if criterion_lower == entry.pattern or criterion_lower.startswith(
            entry.pattern
        ):
            matches.append(entry)
    if not matches:
        return None
    matches.sort(key=lambda e: len(e.pattern), reverse=True)
    longest = len(matches[0].pattern)
    top = [m for m in matches if len(m.pattern) == longest]
    if len(top) > 1:
        return None
    return top[0]


def resolve_grade(
    criterion: str,
    args: list[Any],
    subject: Subject,
    context: EvalContext,
) -> Grade:
    """Resolve a then-clause to a Grade by matching and invoking a grader.

    Uses longest prefix match with ambiguity detection per SPEC §4.2.
    Inactive layers produce skipped grades per SPEC §6.2.
    """
    criterion_lower = criterion.lower()
    matches: list[GraderEntry] = []
    for entry in _GRADER_REGISTRY:
        if criterion_lower == entry.pattern or criterion_lower.startswith(
            entry.pattern
        ):
            matches.append(entry)

    if not matches:
        return Grade(
            criterion=criterion,
            score=0.0,
            metric="quality",
            passed=False,
            detail="No grader found for this criterion.",
            layer=GraderLayer.DETERMINISTIC,
        )

    # Longest prefix match with ambiguity detection (SPEC §4.2)
    matches.sort(key=lambda e: len(e.pattern), reverse=True)
    longest = len(matches[0].pattern)
    top = [m for m in matches if len(m.pattern) == longest]

    if len(top) > 1:
        conflicting = [m.pattern for m in top]
        return Grade(
            criterion=criterion,
            score=0.0,
            metric="quality",
            passed=False,
            detail=f"Ambiguous match: conflicting patterns {conflicting}",
            layer=GraderLayer.DETERMINISTIC,
        )

    entry = top[0]
    active = _active_layers(context)

    # Normalise to plain string for comparison (StrEnum str() varies)
    if isinstance(entry.layer, GraderLayer):
        layer_str = entry.layer.value
    else:
        layer_str = entry.layer
    if layer_str not in active:
        mode_val = context.mode.value
        return Grade(
            criterion=criterion,
            score=0.0,
            metric=entry.metric,
            passed=False,
            detail=f"Skipped: {layer_str} grader not active in {mode_val} mode.",
            layer=entry.layer,
            skipped=True,
        )

    timeout = getattr(context.config, "grader_timeout", _DEFAULT_GRADER_TIMEOUT)
    grade = _run_with_timeout(
        entry.handler, (criterion, args, subject, context), timeout
    )
    if grade is None:
        grade = Grade(
            criterion=criterion,
            score=0.0,
            metric=entry.metric,
            passed=False,
            detail=f"Grader timed out after {timeout}s",
            layer=entry.layer,
        )

    # Enforce grade_pass_threshold (SPEC §5.3): pass is score > threshold
    threshold = context.config.grade_pass_threshold
    enforced_pass = grade.score > threshold
    if enforced_pass != grade.passed:
        grade = Grade(
            criterion=grade.criterion,
            score=grade.score,
            metric=grade.metric,
            passed=enforced_pass,
            detail=grade.detail,
            layer=grade.layer,
            skipped=grade.skipped,
            stage=grade.stage,
            stage_name=grade.stage_name,
        )
    return grade


def get_registered_graders() -> list[GraderEntry]:
    """Return all registered graders."""
    return list(_GRADER_REGISTRY)


def clear_grader_registry() -> None:
    """Remove all registered graders. Useful for test isolation."""
    _GRADER_REGISTRY.clear()


# Auto-register built-in graders (decorators register at import time)
import beval.graders.ai_judged as _ai_judged  # noqa: E402, F401
import beval.graders.deterministic as _deterministic  # noqa: E402, F401
import beval.graders.process as _process  # noqa: E402, F401
