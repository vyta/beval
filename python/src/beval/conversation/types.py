"""Data types for conversation simulation (§15).

See spec/conversation-sim.spec.md for the normative specification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from beval.types import Grade


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
class GoalGiven:
    """Setup block for a goal — objective and circuit-breaker constraints (§15.4.1)."""

    objective: str = ""
    max_turns: int = 20
    timeout_seconds: float = 600.0


@dataclass
class GoalStage:
    """A when/then evaluation stage in a Goal (§15.4.1)."""

    when: str  # "each turn" | "on finish"
    then: list[str] = field(default_factory=list)


@dataclass
class Goal:
    """A conversation goal definition (§15.4)."""

    id: str
    name: str
    tags: list[str] = field(default_factory=list)
    given: GoalGiven = field(default_factory=GoalGiven)
    stages: list[GoalStage] = field(default_factory=list)

    def each_turn_then(self) -> list[str]:
        """Criterion strings from the 'each turn' stage."""
        for stage in self.stages:
            if stage.when.lower() == "each turn":
                return stage.then
        return []

    def on_finish_then(self) -> list[str]:
        """Criterion strings from the 'on finish' stage."""
        for stage in self.stages:
            if stage.when.lower() == "on finish":
                return stage.then
        return []


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


@dataclass
class ConversationRunResult:
    """Top-level result artifact for a conversation simulation run (§15.10.3)."""

    mode: str
    config: dict[str, Any]
    summary: ConversationRunSummary
    conversations: list[ConversationResult]
    label: str | None = None
    timestamp: str | None = None
