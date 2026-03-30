"""Tests for conversation simulation (§15)."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from beval.conversation.actor import run_actor
from beval.conversation.runner import (
    ConversationRunner,
    _build_conversations,
    _build_summary,
    load_personas_and_goals,
)
from beval.conversation.simulator import (
    OpenAISimulator,
    _build_system_message,
    _build_user_message,
    _parse_dynamic_case,
)
from beval.conversation.types import (
    ConversationResult,
    DynamicCase,
    Goal,
    GoalGiven,
    GoalStage,
    Persona,
    PersonaTraits,
    TurnResult,
)
from beval.types import EvalContext, EvaluationMode, RunConfig


# ── Fixtures ───────────────────────────────────────────────────────────────


def make_persona(**kwargs: Any) -> Persona:
    defaults: dict[str, Any] = dict(
        id="test_user",
        name="Test User",
        description="A test persona.",
        goals=["test_goal"],
    )
    defaults.update(kwargs)
    return Persona(**defaults)


def make_goal(**kwargs: Any) -> Goal:
    defaults: dict[str, Any] = dict(
        id="test_goal",
        name="Test Goal",
        given=GoalGiven(objective="Accomplish the test task.", max_turns=5),
        stages=[],
    )
    defaults.update(kwargs)
    return Goal(**defaults)


def make_context() -> EvalContext:
    return EvalContext(
        mode=EvaluationMode.DEV,
        config=RunConfig(grade_pass_threshold=0.5, case_pass_threshold=0.7),
    )


# ── _parse_dynamic_case ───────────────────────────────────────────────────


class TestParseDynamicCase:
    def test_parses_valid_json(self):
        raw = '{"progress": 0.5, "query": "What is the policy?", "then": ["the agent answers"]}'
        dc = _parse_dynamic_case(raw)
        assert dc.progress == 0.5
        assert dc.query == "What is the policy?"
        assert dc.then == ("the agent answers",)

    def test_strips_markdown_fences(self):
        raw = '```json\n{"progress": 0.3, "query": "Hello", "then": []}\n```'
        dc = _parse_dynamic_case(raw)
        assert dc.query == "Hello"
        assert dc.progress == 0.3

    def test_progress_100_returns_early(self):
        raw = '{"progress": 1.0, "query": "ignored", "then": ["ignored"]}'
        dc = _parse_dynamic_case(raw)
        assert dc.progress == 1.0
        assert dc.query == ""
        assert dc.then == ()

    def test_clamps_progress(self):
        raw = '{"progress": 2.5, "query": "Hi", "then": []}'
        dc = _parse_dynamic_case(raw)
        assert dc.progress == 1.0

    def test_missing_progress_defaults_to_zero(self):
        raw = '{"query": "Hi", "then": []}'
        dc = _parse_dynamic_case(raw)
        assert dc.progress == 0.0

    def test_missing_then_uses_empty(self):
        raw = '{"progress": 0.2, "query": "Hi"}'
        dc = _parse_dynamic_case(raw)
        assert dc.then == ()

    def test_missing_query_raises(self):
        raw = '{"progress": 0.5, "then": []}'
        with pytest.raises(ValueError, match="empty or missing"):
            _parse_dynamic_case(raw)

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            _parse_dynamic_case("not json at all")

    def test_extracts_json_from_surrounding_text(self):
        raw = 'Info: processing...\n{"progress": 0.4, "query": "Hello", "then": []}'
        dc = _parse_dynamic_case(raw)
        assert dc.query == "Hello"


# ── Prompt building ───────────────────────────────────────────────────────


class TestPromptBuilding:
    def test_system_message_contains_persona_description(self):
        persona = make_persona(description="An expert user.")
        goal = make_goal()
        msg = _build_system_message(persona, goal)
        assert "An expert user." in msg

    def test_system_message_contains_objective(self):
        persona = make_persona()
        goal = make_goal(given=GoalGiven(objective="Find the refund policy."))
        msg = _build_system_message(persona, goal)
        assert "Find the refund policy." in msg

    def test_system_message_includes_on_finish_criteria(self):
        persona = make_persona()
        goal = make_goal(
            stages=[GoalStage(when="on finish", then=["the agent answered fully"])]
        )
        msg = _build_system_message(persona, goal)
        assert "the agent answered fully" in msg

    def test_user_message_empty_history(self):
        msg = _build_user_message([])
        assert "start of the conversation" in msg.lower()

    def test_user_message_with_history(self):
        history = [
            TurnResult(
                turn_number=1,
                user_message="Hello",
                agent_response="Hi there!",
                completion_time_seconds=0.5,
                goal_progress=0.2,
                grades=(),
                metric_scores={},
                overall_score=0.0,
                error=None,
            )
        ]
        msg = _build_user_message(history)
        assert "Hello" in msg
        assert "<agent_response>" in msg
        assert "Hi there!" in msg


# ── Actor ─────────────────────────────────────────────────────────────────


class MockSimulator:
    """Simulator that returns pre-configured DynamicCase objects."""

    def __init__(self, cases: list[DynamicCase]) -> None:
        self._cases = iter(cases)

    async def generate_case(self, persona, goal, history, context) -> DynamicCase:
        return next(self._cases)

    async def close(self) -> None:
        pass


class MockAdapter:
    """Adapter that returns a fixed agent response."""

    def __init__(self, response: str = "Agent reply.") -> None:
        self._response = response

    def invoke(self, adapter_input: Any) -> Any:
        from beval.types import Subject

        return Subject(
            input=adapter_input.query,
            output=self._response,
            completion_time=0.1,
        )

    def close(self) -> None:
        pass


class TestRunActor:
    def _run(self, persona, goal, simulator, adapter=None, context=None):
        if adapter is None:
            adapter = MockAdapter()
        if context is None:
            context = make_context()
        return asyncio.run(run_actor(persona, goal, 1, adapter, simulator, context))

    def test_goal_achieved_on_progress_1(self):
        persona = make_persona()
        goal = make_goal()
        sim = MockSimulator(
            [
                DynamicCase(query="Hi", then=(), progress=0.5),
                DynamicCase(query="", then=(), progress=1.0),
            ]
        )
        result = self._run(persona, goal, sim)
        assert result.goal_achieved is True
        assert result.termination_reason == "goal_achieved"
        assert result.turn_count == 1  # 1 turn sent, then goal achieved

    def test_terminated_max_turns(self):
        persona = make_persona()
        goal = make_goal(given=GoalGiven(objective="test", max_turns=3))
        # Always returns progress 0.0 — never finishes
        sim = MockSimulator(
            [DynamicCase(query=f"turn {i}", then=(), progress=0.0) for i in range(5)]
        )
        result = self._run(persona, goal, sim)
        assert result.termination_reason == "terminated_max_turns"
        assert result.turn_count == 3

    def test_simulator_error_terminates(self):
        persona = make_persona()
        goal = make_goal()

        class ErrorSim:
            async def generate_case(self, *a, **kw):
                raise RuntimeError("LLM API failed")

            async def close(self):
                pass

        result = self._run(persona, goal, ErrorSim())
        assert result.termination_reason == "simulator_error"
        assert result.error is not None
        # Actor records an error TurnResult for the failed turn (§15.5.2)
        assert result.turn_count == 1
        assert result.turns[0].error is not None

    def test_agent_error_terminates(self):
        persona = make_persona()
        goal = make_goal()
        sim = MockSimulator([DynamicCase(query="Hello", then=(), progress=0.5)])

        class ErrorAdapter:
            def invoke(self, *a, **kw):
                raise RuntimeError("Agent offline")

            def close(self):
                pass

        result = self._run(persona, goal, sim, adapter=ErrorAdapter())
        assert result.termination_reason == "agent_error"
        assert result.turn_count == 1
        assert result.turns[0].error is not None

    def test_result_fields(self):
        persona = make_persona()
        goal = make_goal()
        sim = MockSimulator([DynamicCase(query="", then=(), progress=1.0)])
        result = self._run(persona, goal, sim)
        assert result.id == "test_user:test_goal:1"
        assert result.persona_id == "test_user"
        assert result.goal_id == "test_goal"
        assert result.actor_index == 1
        assert result.category == "test_user/test_goal"

    def test_goal_achievement_score_is_last_progress(self):
        persona = make_persona()
        goal = make_goal(given=GoalGiven(objective="test", max_turns=2))
        sim = MockSimulator(
            [
                DynamicCase(query="Hi", then=(), progress=0.4),
                DynamicCase(query="More", then=(), progress=0.7),
            ]
        )
        result = self._run(persona, goal, sim)
        assert result.termination_reason == "terminated_max_turns"
        assert result.goal_achievement_score == pytest.approx(0.7)

    def test_goal_achievement_score_is_1_when_goal_achieved(self):
        persona = make_persona()
        goal = make_goal()
        sim = MockSimulator([DynamicCase(query="", then=(), progress=1.0)])
        result = self._run(persona, goal, sim)
        assert result.goal_achievement_score == pytest.approx(1.0)


# ── Build conversations ───────────────────────────────────────────────────


class TestBuildConversations:
    def test_persona_centric_pairing(self):
        goal_pool = {
            "g1": make_goal(id="g1", name="Goal 1"),
            "g2": make_goal(id="g2", name="Goal 2"),
            "g3": make_goal(id="g3", name="Goal 3"),
        }
        personas = [
            make_persona(id="p1", goals=["g1", "g2"]),
            make_persona(id="p2", goals=["g3"]),
        ]
        convs = _build_conversations(personas, goal_pool, actor_count=1)
        ids = [(p.id, g.id, i) for p, g, i in convs]
        assert ("p1", "g1", 1) in ids
        assert ("p1", "g2", 1) in ids
        assert ("p2", "g3", 1) in ids
        assert len(ids) == 3

    def test_actor_count(self):
        goal_pool = {"g1": make_goal(id="g1")}
        personas = [make_persona(goals=["g1"])]
        convs = _build_conversations(personas, goal_pool, actor_count=3)
        assert len(convs) == 3
        indices = [i for _, _, i in convs]
        assert sorted(indices) == [1, 2, 3]


# ── Summary ───────────────────────────────────────────────────────────────


class TestBuildSummary:
    def _make_result(self, **kwargs: Any) -> ConversationResult:
        defaults: dict[str, Any] = dict(
            id="p:g:1",
            name="p → g (actor 1)",
            category="p/g",
            persona_id="p",
            goal_id="g",
            actor_index=1,
            overall_score=1.0,
            goal_achievement_score=1.0,
            passed=True,
            goal_achieved=True,
            termination_reason="goal_achieved",
            turn_count=3,
            time_seconds=5.0,
            metric_scores={},
            error=None,
            turns=[],
            grades=[],
        )
        defaults.update(kwargs)
        return ConversationResult(**defaults)

    def test_counts(self):
        results = [
            self._make_result(passed=True, goal_achieved=True, termination_reason="goal_achieved"),
            self._make_result(passed=False, goal_achieved=False, termination_reason="terminated_max_turns"),
            self._make_result(passed=False, goal_achieved=False, termination_reason="agent_error"),
            self._make_result(passed=False, goal_achieved=False, termination_reason="cancelled"),
        ]
        summary = _build_summary(results, RunConfig())
        assert summary.total == 4
        assert summary.passed == 1
        assert summary.errored == 1
        assert summary.cancelled == 1
        assert summary.failed == 1

    def test_goal_achievement_rate(self):
        results = [
            self._make_result(goal_achieved=True),
            self._make_result(goal_achieved=True),
            self._make_result(goal_achieved=False, termination_reason="terminated_max_turns", passed=False),
        ]
        summary = _build_summary(results, RunConfig())
        assert summary.goal_achievement_rate == pytest.approx(2 / 3)

    def test_mean_turns_to_goal(self):
        results = [
            self._make_result(goal_achieved=True, turn_count=2),
            self._make_result(goal_achieved=True, turn_count=4),
        ]
        summary = _build_summary(results, RunConfig())
        assert summary.mean_turns_to_goal == pytest.approx(3.0)

    def test_mean_turns_to_goal_none_when_none_achieved(self):
        results = [
            self._make_result(goal_achieved=False, termination_reason="terminated_max_turns", passed=False)
        ]
        summary = _build_summary(results, RunConfig())
        assert summary.mean_turns_to_goal is None

    def test_total_turns(self):
        results = [
            self._make_result(turn_count=3),
            self._make_result(turn_count=7),
        ]
        summary = _build_summary(results, RunConfig())
        assert summary.total_turns == 10
