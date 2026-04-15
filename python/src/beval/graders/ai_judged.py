"""AI-judged built-in graders.

These graders delegate to the configured LLM judge. See SPEC §10.
"""

from __future__ import annotations

from typing import Any

from beval.graders import grader
from beval.judge import NullJudge
from beval.types import EvalContext, Grade, GraderLayer, Subject


@grader("the answer should", layer=GraderLayer.AI_JUDGED)
@grader("the conversation should", layer=GraderLayer.AI_JUDGED)
def _ai_judged_grader(
    criterion: str,
    args: list[Any],
    subject: Subject,
    context: EvalContext,
) -> Grade:
    """Delegate 'the answer/conversation should ...' to the LLM judge."""
    judge = context.llm_judge or NullJudge()
    return judge.evaluate(
        criterion=criterion,
        subject_answer=subject.answer,
        context={"input": subject.input},
    )
