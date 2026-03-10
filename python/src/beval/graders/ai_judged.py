"""AI-judged built-in graders.

These graders delegate to the configured LLM judge. See SPEC §10.
"""

from __future__ import annotations

from typing import Any

from beval.graders import grader
from beval.judge import NullJudge
from beval.types import EvalContext, Grade, GraderLayer, Subject


@grader("the answer should", layer=GraderLayer.AI_JUDGED)
def _answer_should_be_grader(
    criterion: str,
    args: list[Any],
    subject: Subject,
    context: EvalContext,
) -> Grade:
    """Delegate 'the answer should be/mention' to the LLM judge."""
    judge = context.llm_judge or NullJudge()
    expectation = args[0] if args else criterion
    return judge.evaluate(
        criterion=f"{criterion} {expectation}",
        subject_answer=subject.output,
        context={"input": subject.input},
    )
