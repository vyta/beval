"""Data types for conversation simulation (§15).

See spec/conversation-sim.spec.md for the normative specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from beval.types import Grade

# Parsed then-clause: (criterion_string, args_tuple)
ThenClause = tuple[str, tuple[Any, ...]]


@dataclass
class PersonaTraits:
    """Structured behavioral attributes of a persona (§15.3.1)."""

    tone: str | None = None
    expertise: str | None = None
    patience: str | None = None
    verbosity: str | None = None
    language: str = "en"
    style_notes: str | None = None


@dataclass
class Persona:
    """A simulated user persona definition (§15.3)."""

    id: str
    name: str
    description: str
    goals: list[str]
    traits: PersonaTraits | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class GoalEval:
    """A when/then evaluation block (§15.4.1)."""

    when: str
    then: list[ThenClause] = field(default_factory=list)


@dataclass
class EvaluationCriteria:
    """Reusable evaluation criteria matched to goals by tag intersection."""

    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    query_evals: list[GoalEval] = field(default_factory=list)
    conversation_evals: list[GoalEval] = field(default_factory=list)


@dataclass
class Goal:
    """A conversation goal definition (§15.4)."""

    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    objective: str = ""
    query_evals: list[GoalEval] = field(default_factory=list)
    conversation_evals: list[GoalEval] = field(default_factory=list)


@dataclass(frozen=True)
class DynamicCase:
    """Output of UserSimulator.generate_case() (§15.6.1).

    query:    the user message to send (ignored when progress == 1.0)
    then:     dynamic, query-specific criterion strings for this turn
    progress: 0.0–1.0; 1.0 = goal fully achieved, loop breaks
    """

    query: str
    then: tuple[str, ...]
    progress: float


@dataclass(frozen=True)
class UserFeedback:
    """Post-conversation feedback from the simulated user persona."""

    satisfaction: float
    text: str | None = None


@dataclass(frozen=True)
class TurnResult:
    """Recorded outcome of one conversation turn (§15.10.1)."""

    turn_number: int
    user_message: str
    agent_response: str
    completion_time_seconds: float
    goal_progress: float
    grades: tuple[Grade, ...]
    metric_scores: dict[str, float]
    overall_score: float
    passed: bool
    error: str | None


@dataclass
class ConversationResult:
    """Aggregated result for one conversation (§15.10.2)."""

    id: str
    name: str
    category: str
    persona_id: str
    goal_id: str
    actor_index: int
    overall_score: float
    goal_achievement_score: float
    passed: bool
    goal_achieved: bool
    termination_reason: str
    turn_count: int
    time_seconds: float
    metric_scores: dict[str, float]
    error: str | None
    turns: list[TurnResult]
    grades: list[Grade]
    feedback: UserFeedback | None = None


@dataclass
class ConversationRunSummary:
    """Aggregate summary across all conversations in a run (§15.10.4)."""

    overall_score: float
    goal_achievement_rate: float
    passed: int
    failed: int
    errored: int
    cancelled: int
    total: int
    total_turns: int
    mean_turns_to_goal: float | None
    metrics: dict[str, float]
    avg_satisfaction: float | None = None
    run_passed: bool = True


@dataclass
class ConversationRunResult:
    """Top-level result artifact for a conversation simulation run (§15.10.3)."""

    mode: str
    config: dict[str, Any]
    summary: ConversationRunSummary
    conversations: list[ConversationResult]
    label: str | None = None
    timestamp: str | None = None
