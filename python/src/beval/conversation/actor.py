"""Actor coroutine for conversation simulation (§15.5, §15.7).

See spec/conversation-sim.spec.md §15.5 for the normative turn loop specification.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from beval.adapters import AdapterInput, AdapterInterface
from beval.conversation.simulator import UserSimulatorInterface
from beval.conversation.types import (
    ConversationResult,
    Goal,
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
    on_turn: Callable[[str, int, str], None] | None = None,
    on_turn_complete: Callable[[str, "TurnResult"], None] | None = None,
) -> ConversationResult:
    """Run a single actor: one persona pursuing one goal (§15.5.2).

    Each actor has its own adapter, simulator, and history (§15.7.1).
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
        for turn_number in range(1, goal.given.max_turns + 1):
            # Timeout circuit breaker (§15.4.1)
            if time.monotonic() - start > goal.given.timeout_seconds:
                termination_reason = "terminated_timeout"
                break

            # Generate DynamicCase — simulator error → terminate conversation
            try:
                dyn_case = await simulator.generate_case(  # noqa: E501
                    persona, goal, history, context
                )
            except Exception as exc:  # noqa: BLE001
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
            all_then = goal.each_turn_then() + list(dyn_case.then)

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
                all_then = []

            grades: list[Grade] = [
                resolve_grade(criterion, [], turn_subject, context)
                for criterion in all_then
            ]

            turn_overall = _aggregate_grades(grades, context.config) if grades else 0.0
            turn_metrics = _metric_scores(grades, context.config) if grades else {}

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
    on_finish_then = goal.on_finish_then()
    conv_grades: list[Grade] = []
    if on_finish_then and history:
        conv_subject = _build_conversation_subject(
            history, persona.id, goal.id, actor_index, termination_reason, elapsed
        )
        conv_grades = [
            resolve_grade(criterion, [], conv_subject, context)
            for criterion in on_finish_then
        ]

    # overall_score (§15.8.4): mean of all non-skipped grades; fall back to goal_achievement_score  # noqa: E501
    all_grades = [g for t in history for g in t.grades] + conv_grades
    if all_grades:
        overall_score = _aggregate_grades(all_grades, context.config)
    else:
        overall_score = 1.0 if termination_reason == "goal_achieved" else last_progress

    all_metric_scores = _metric_scores(all_grades, context.config) if all_grades else {}

    # goal_achievement_score (§15.8.3)
    goal_achievement_score = 1.0 if termination_reason == "goal_achieved" else last_progress  # noqa: E501

    goal_achieved = termination_reason == "goal_achieved"
    passed = goal_achieved and overall_score >= context.config.case_pass_threshold

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
    )
