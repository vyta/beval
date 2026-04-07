"""Actor coroutine for conversation simulation (§15.5, §15.7).

See spec/conversation-sim.spec.md §15.5 for the normative turn loop specification.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from typing import Any

from beval.adapters import AdapterInput, AdapterInterface
from beval.judge import _is_content_filter
from beval.conversation.simulator import UserSimulatorInterface
from beval.conversation.types import (
    ConversationResult,
    Goal,
    GoalEval,
    Persona,
    TurnResult,
)
from beval.graders import resolve_grade
from beval.runner import _aggregate_grades, _metric_scores
from beval.types import EvalContext, Grade, Subject

logger = logging.getLogger(__name__)


def _build_turn_subject(
    subject: Subject,
    turn_number: int,
    persona_id: str,
    goal_id: str,
    actor_index: int,
    goal_progress: float,
) -> Subject:
    """Construct TurnSubject with stage metadata additions (§15.8.1)."""
    metadata = dict(subject.metadata)
    metadata.update(
        {
            "persona_id": persona_id,
            "goal_id": goal_id,
            "actor_index": actor_index,
            "goal_progress": goal_progress,
        }
    )
    return Subject(
        input=subject.input,
        output=subject.output,
        completion_time=subject.completion_time,
        tool_calls=subject.tool_calls,
        spans=subject.spans,
        metadata=metadata,
        stage=turn_number,
        stage_name=f"turn {turn_number}",
        prior_subject=subject.prior_subject,
    )


def _build_conversation_subject(
    history: list[TurnResult],
    persona_id: str,
    goal_id: str,
    actor_index: int,
    termination_reason: str,
    elapsed: float,
) -> Subject:
    """Construct ConversationSubject for post-conversation grading (§15.5.5)."""
    messages: list[dict[str, Any]] = []
    for t in history:
        messages.append({"role": "user", "content": t.user_message})
        messages.append({"role": "assistant", "content": t.agent_response})
    # Serialize the full conversation as output so on-finish judges can evaluate
    # the entire session arc, not just the last agent response.
    turn_lines: list[str] = []
    for t in history:
        if t.user_message:
            turn_lines.append(f"User: {t.user_message}")
        agent_text = t.agent_response or ""
        if agent_text.strip() and "operation cancelled" not in agent_text.lower():
            turn_lines.append(f"Agent: {agent_text}")
    final_output = "\n\n".join(turn_lines)
    return Subject(
        input=messages,
        output=final_output,
        completion_time=elapsed,
        metadata={
            "persona_id": persona_id,
            "goal_id": goal_id,
            "actor_index": actor_index,
            "turn_count": len(history),
            "termination_reason": termination_reason,
            "goal_achieved": termination_reason == "goal_achieved",
        },
    )


async def run_actor(
    persona: Persona,
    goal: Goal,
    actor_index: int,
    adapter: AdapterInterface,
    simulator: UserSimulatorInterface,
    context: EvalContext,
    *,
    max_turns: int = 20,
    timeout_seconds: float = 600.0,
    on_turn: Callable[[str, int, str], None] | None = None,
    on_turn_complete: Callable[[str, "TurnResult"], None] | None = None,
    feedback_text_rate: float = 0.0,
) -> ConversationResult:
    """Run a single actor: one persona pursuing one goal (§15.5.2).

    Each actor has its own adapter, simulator, and history (§15.7.1).
    max_turns and timeout_seconds are circuit breakers from the global config.
    Cancellation (asyncio.CancelledError) is propagated to the caller (§15.13).
    """
    actor_id = f"{persona.id}:{goal.id}:{actor_index}"
    history: list[TurnResult] = []
    termination_reason = "terminated_max_turns"
    conv_error: str | None = None
    last_progress: float = 0.0
    prior_subject: Subject | None = None
    start = time.monotonic()

    try:
        for turn_number in range(1, max_turns + 1):
            # Timeout circuit breaker (§15.9.1)
            if time.monotonic() - start > timeout_seconds:
                termination_reason = "terminated_timeout"
                break

            # Generate DynamicCase — simulator error → terminate conversation
            # (content filter errors just skip the turn and continue)
            try:
                dyn_case = await simulator.generate_case(  # noqa: E501
                    persona, goal, history, context
                )
            except Exception as exc:  # noqa: BLE001
                if _is_content_filter(exc):
                    logger.info(
                        "Content filter in %s turn %d, skipping turn", actor_id, turn_number
                    )
                    continue
                logger.warning(
                    "Simulator error in %s turn %d: %s", actor_id, turn_number, exc
                )
                history.append(
                    TurnResult(
                        turn_number=turn_number,
                        user_message="",
                        agent_response="",
                        completion_time_seconds=0.0,
                        goal_progress=last_progress,
                        grades=(),
                        metric_scores={},
                        overall_score=0.0,
                        passed=False,
                        error=str(exc),
                    )
                )
                termination_reason = "simulator_error"
                conv_error = str(exc)
                break

            # Clamp progress to be monotonically non-decreasing
            last_progress = max(last_progress, dyn_case.progress)

            # Goal achieved mid-loop (§15.5.2)
            if dyn_case.progress == 1.0:
                termination_reason = "goal_achieved"
                break

            if on_turn:
                on_turn(actor_id, turn_number, dyn_case.query)

            # Invoke agent — run sync adapter in thread pool to avoid blocking event loop  # noqa: E501
            adapter_input = AdapterInput(
                query=dyn_case.query,
                givens={},
                context=context,
                stage=turn_number,
                stage_name=f"turn {turn_number}",
                prior_subject=prior_subject,
            )
            try:
                subject = await asyncio.to_thread(adapter.invoke, adapter_input)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Agent error in %s turn %d: %s", actor_id, turn_number, exc
                )
                history.append(
                    TurnResult(
                        turn_number=turn_number,
                        user_message=dyn_case.query,
                        agent_response="",
                        completion_time_seconds=0.0,
                        goal_progress=dyn_case.progress,
                        grades=(),
                        metric_scores={},
                        overall_score=0.0,
                        passed=False,
                        error=str(exc),
                    )
                )
                termination_reason = "agent_error"
                conv_error = str(exc)
                break

            # Build TurnSubject and run per-turn graders (§15.8.1)
            turn_subject = _build_turn_subject(
                subject, turn_number, persona.id, goal.id, actor_index, dyn_case.progress  # noqa: E501
            )

            # Skip AI grading for cancelled/empty agent responses — they're infra
            # failures, not coaching quality signals.
            _answer = subject.answer or ""
            _is_cancelled = (
                not _answer.strip()
                or "operation cancelled" in _answer.lower()
            )

            if _is_cancelled:
                logger.warning(
                    "Skipping grades for %s turn %d — agent returned cancelled/empty response",
                    actor_id, turn_number,
                )
                query_eval_list: list[GoalEval] = []
                dyn_then: tuple[str, ...] = ()
            else:
                query_eval_list = goal.query_evals
                dyn_then = dyn_case.then

            # Multi-stage per-turn grading — each GoalEval is one stage,
            # mirroring static _run_multistage() in runner.py
            grades: list[Grade] = []
            stage_num = 0
            for ev in query_eval_list:
                stage_num += 1
                stage_subject = Subject(
                    input=turn_subject.input,
                    output=turn_subject.output,
                    completion_time=turn_subject.completion_time,
                    tool_calls=turn_subject.tool_calls,
                    spans=turn_subject.spans,
                    metadata=turn_subject.metadata,
                    stage=stage_num,
                    stage_name=ev.when,
                    prior_subject=turn_subject.prior_subject,
                )
                for criterion, args in ev.then:
                    grade = resolve_grade(criterion, list(args), stage_subject, context)
                    grades.append(Grade(
                        criterion=grade.criterion,
                        score=grade.score,
                        metric=grade.metric,
                        passed=grade.passed,
                        detail=grade.detail,
                        layer=grade.layer,
                        skipped=grade.skipped,
                        stage=stage_num,
                        stage_name=ev.when,
                    ))
            # Dynamic criteria from simulator appended to last stage
            if dyn_then:
                if stage_num == 0:
                    stage_num = 1
                    dyn_stage_name = "dynamic"
                else:
                    dyn_stage_name = query_eval_list[-1].when
                dyn_subject = Subject(
                    input=turn_subject.input,
                    output=turn_subject.output,
                    completion_time=turn_subject.completion_time,
                    tool_calls=turn_subject.tool_calls,
                    spans=turn_subject.spans,
                    metadata=turn_subject.metadata,
                    stage=stage_num,
                    stage_name=dyn_stage_name,
                    prior_subject=turn_subject.prior_subject,
                )
                for criterion in dyn_then:
                    grade = resolve_grade(criterion, [], dyn_subject, context)
                    grades.append(Grade(
                        criterion=grade.criterion,
                        score=grade.score,
                        metric=grade.metric,
                        passed=grade.passed,
                        detail=grade.detail,
                        layer=grade.layer,
                        skipped=grade.skipped,
                        stage=stage_num,
                        stage_name=dyn_stage_name,
                    ))

            turn_overall = _aggregate_grades(grades, context.config) if grades else 0.0
            turn_metrics = _metric_scores(grades, context.config) if grades else {}

            # Turn pass/fail: fraction of passing grades >= case_pass_rate
            if grades:
                passing = sum(1 for g in grades if g.passed)
                turn_passed = (passing / len(grades)) >= context.config.case_pass_rate
            else:
                turn_passed = True  # no-evals pass rule

            history.append(
                TurnResult(
                    turn_number=turn_number,
                    user_message=dyn_case.query,
                    agent_response=subject.answer,
                    completion_time_seconds=subject.completion_time,
                    goal_progress=dyn_case.progress,
                    grades=tuple(grades),
                    metric_scores=turn_metrics,
                    overall_score=turn_overall,
                    passed=turn_passed,
                    error=None,
                )
            )
            if on_turn_complete:
                on_turn_complete(actor_id, history[-1])
            prior_subject = subject

    except asyncio.CancelledError:
        termination_reason = "cancelled"
        raise  # propagate so the runner records it

    elapsed = time.monotonic() - start

    # Conversation-level grading (§15.8.2)
    conv_grades: list[Grade] = []
    if goal.conversation_evals and history:
        conv_subject = _build_conversation_subject(
            history, persona.id, goal.id, actor_index, termination_reason, elapsed
        )
        for stage_idx, ev in enumerate(goal.conversation_evals, 1):
            stage_subject = Subject(
                input=conv_subject.input,
                output=conv_subject.output,
                completion_time=conv_subject.completion_time,
                metadata=conv_subject.metadata,
                stage=stage_idx,
                stage_name=ev.when,
            )
            for criterion, args in ev.then:
                grade = resolve_grade(criterion, list(args), stage_subject, context)
                conv_grades.append(Grade(
                    criterion=grade.criterion,
                    score=grade.score,
                    metric=grade.metric,
                    passed=grade.passed,
                    detail=grade.detail,
                    layer=grade.layer,
                    skipped=grade.skipped,
                    stage=stage_idx,
                    stage_name=ev.when,
                ))

    # overall_score (§15.8.4): mean of all non-skipped grades (informational)
    all_grades = [g for t in history for g in t.grades] + conv_grades
    if all_grades:
        overall_score = _aggregate_grades(all_grades, context.config)
    elif termination_reason in ("agent_error", "simulator_error"):
        overall_score = 0.0
    else:
        overall_score = 1.0

    all_metric_scores = _metric_scores(all_grades, context.config) if all_grades else {}

    # goal_achievement_score (§15.8.3)
    goal_achievement_score = 1.0 if termination_reason == "goal_achieved" else last_progress  # noqa: E501

    goal_achieved = termination_reason == "goal_achieved"

    # Pass/fail: both turn pass rate and conversation grade pass rate must meet thresholds
    if termination_reason in ("agent_error", "simulator_error"):
        passed = False
    else:
        # Turn pass rate
        turns_with_grades = [t for t in history if t.grades]
        if turns_with_grades:
            t_rate = sum(1 for t in turns_with_grades if t.passed) / len(turns_with_grades)
        else:
            t_rate = 1.0
        # Conversation grade pass rate
        if conv_grades:
            c_passing = sum(1 for g in conv_grades if g.passed)
            c_rate = c_passing / len(conv_grades)
        else:
            c_rate = 1.0
        passed = (
            goal_achieved
            and t_rate >= context.config.turn_pass_rate
            and c_rate >= context.config.conversation_pass_rate
        )

    # Post-conversation feedback
    feedback = None
    if history and termination_reason != "cancelled":
        include_text = random.random() < feedback_text_rate  # noqa: S311
        try:
            feedback = await simulator.generate_feedback(
                persona, goal, history, termination_reason,
                include_text=include_text,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Feedback generation failed for %s", actor_id)

    # Enforce min_satisfaction threshold per conversation
    if (
        passed
        and context.config.min_satisfaction is not None
        and feedback is not None
        and feedback.satisfaction < context.config.min_satisfaction
    ):
        passed = False

    return ConversationResult(
        id=actor_id,
        name=f"{persona.name} → {goal.name} (actor {actor_index})",
        category=f"{persona.id}/{goal.id}",
        persona_id=persona.id,
        goal_id=goal.id,
        actor_index=actor_index,
        overall_score=overall_score,
        goal_achievement_score=goal_achievement_score,
        passed=passed,
        goal_achieved=goal_achieved,
        termination_reason=termination_reason,
        turn_count=len(history),
        time_seconds=elapsed,
        metric_scores=all_metric_scores,
        error=conv_error,
        turns=list(history),
        grades=conv_grades,
        feedback=feedback,
    )
