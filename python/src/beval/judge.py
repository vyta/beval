"""LLM judge interface for AI-judged graders.

Provides a pluggable judge abstraction for subjective quality assessment.
See SPEC.md §10 (Pluggable Judges).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from beval.types import Grade, GraderLayer


class Judge(ABC):
    """Base interface for LLM-based judges. See SPEC §10."""

    @abstractmethod
    def evaluate(
        self,
        criterion: str,
        subject_answer: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> Grade:
        """Evaluate a subject answer against a criterion.

        Returns a Grade with score, metric, and reasoning detail.
        """
        ...


class NullJudge(Judge):
    """A no-op judge that returns a skipped grade. Used when no judge is configured."""

    def evaluate(
        self,
        criterion: str,
        subject_answer: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> Grade:
        return Grade(
            criterion=criterion,
            score=0.0,
            metric="quality",
            passed=False,
            detail="No judge configured.",
            layer=GraderLayer.AI_JUDGED,
            skipped=True,
        )
