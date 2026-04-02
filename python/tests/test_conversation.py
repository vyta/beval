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
    _run_all_actors,
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
        assert "opening message" in msg.lower() or "start" in msg.lower()

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
        assert "Assistant:" in msg
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


# ── Parallel concurrency ──────────────────────────────────────────────────


class TestParallelActors:
    """Verify that max_parallel_actors limits concurrency via semaphore."""

    def test_3_actors_run_concurrently(self):
        """All 3 actors complete when max_parallel_actors=3."""
        import asyncio

        persona = make_persona(id="p", goals=["g1", "g2", "g3"])
        goals = [
            make_goal(id="g1"),
            make_goal(id="g2"),
            make_goal(id="g3"),
        ]
        goal_pool = {g.id: g for g in goals}
        conversations = _build_conversations([persona], goal_pool, actor_count=1)
        assert len(conversations) == 3

        active_count = 0
        peak_active = 0

        class CountingSimulator:
            async def generate_case(self, *a, **kw):
                nonlocal active_count, peak_active
                active_count += 1
                peak_active = max(peak_active, active_count)
                await asyncio.sleep(0.01)  # yield to let others start
                active_count -= 1
                return DynamicCase(query="", then=(), progress=1.0)

            async def close(self):
                pass

        class CountingAdapter:
            def invoke(self, *a, **kw):
                from beval.types import Subject
                return Subject(input="q", output="a", completion_time=0.0)

            def close(self):
                pass

        from unittest.mock import patch

        def make_simulator(_config):
            return CountingSimulator()

        def make_adapter(_def):
            return CountingAdapter()

        context = make_context()

        with patch(
            "beval.conversation.runner.load_simulator_from_config", side_effect=make_simulator
        ), patch("beval.conversation.runner.create_adapter", side_effect=make_adapter):
            results = asyncio.run(
                _run_all_actors(
                    conversations,
                    agent_def={"name": "mock", "protocol": "acp", "connection": {}},
                    simulator_config={"protocol": "openai", "model": "mock"},
                    context=context,
                    max_parallel_actors=3,
                    run_timeout_seconds=None,
                )
            )

        assert len(results) == 3
        assert all(r.termination_reason == "goal_achieved" for r in results)
        # With max_parallel_actors=3 all 3 should have been active simultaneously
        assert peak_active == 3

    def test_semaphore_limits_to_1(self):
        """With max_parallel_actors=1 actors run one at a time."""
        import asyncio

        persona = make_persona(id="p", goals=["g1", "g2", "g3"])
        goals = [make_goal(id=f"g{i}") for i in range(1, 4)]
        goal_pool = {g.id: g for g in goals}
        conversations = _build_conversations([persona], goal_pool, actor_count=1)

        active_count = 0
        peak_active = 0

        class CountingSimulator:
            async def generate_case(self, *a, **kw):
                nonlocal active_count, peak_active
                active_count += 1
                peak_active = max(peak_active, active_count)
                await asyncio.sleep(0.01)
                active_count -= 1
                return DynamicCase(query="", then=(), progress=1.0)

            async def close(self):
                pass

        class CountingAdapter:
            def invoke(self, *a, **kw):
                from beval.types import Subject
                return Subject(input="q", output="a", completion_time=0.0)

            def close(self):
                pass

        from unittest.mock import patch

        context = make_context()

        with patch(
            "beval.conversation.runner.load_simulator_from_config",
            side_effect=lambda _: CountingSimulator(),
        ), patch(
            "beval.conversation.runner.create_adapter",
            side_effect=lambda _: CountingAdapter(),
        ):
            asyncio.run(
                _run_all_actors(
                    conversations,
                    agent_def={},
                    simulator_config={},
                    context=context,
                    max_parallel_actors=1,
                    run_timeout_seconds=None,
                )
            )

        # Semaphore of 1 means at most 1 actor active at a time
        assert peak_active == 1


# ── on_turn_complete callback ─────────────────────────────────────────────────


class TestOnTurnComplete:
    def _run_with_callback(self, persona, goal, sim, adapter=None):
        if adapter is None:
            adapter = MockAdapter()
        calls: list[tuple[str, Any]] = []

        def callback(actor_id: str, turn_result: Any) -> None:
            calls.append((actor_id, turn_result))

        result = asyncio.run(
            run_actor(persona, goal, 1, adapter, sim, make_context(),
                      on_turn_complete=callback)
        )
        return result, calls

    def test_called_once_per_successful_turn(self):
        persona = make_persona()
        goal = make_goal(given=GoalGiven(objective="t", max_turns=3))
        sim = MockSimulator([
            DynamicCase(query="turn1", then=(), progress=0.3),
            DynamicCase(query="turn2", then=(), progress=0.6),
            DynamicCase(query="turn3", then=(), progress=0.9),
        ])
        result, calls = self._run_with_callback(persona, goal, sim)
        assert result.termination_reason == "terminated_max_turns"
        assert len(calls) == 3

    def test_not_called_on_simulator_error(self):
        persona = make_persona()
        goal = make_goal()

        class ErrorSim:
            async def generate_case(self, *a, **kw):
                raise RuntimeError("sim failed")
            async def close(self): pass

        _, calls = self._run_with_callback(persona, goal, ErrorSim())
        assert calls == []

    def test_not_called_on_agent_error(self):
        persona = make_persona()
        goal = make_goal()
        sim = MockSimulator([DynamicCase(query="hi", then=(), progress=0.5)])

        class ErrorAdapter:
            def invoke(self, *a, **kw): raise RuntimeError("agent failed")
            def close(self): pass

        _, calls = self._run_with_callback(persona, goal, sim, adapter=ErrorAdapter())
        assert calls == []

    def test_callback_receives_correct_actor_id(self):
        persona = make_persona(id="myp")
        goal = make_goal(id="myg")
        sim = MockSimulator([DynamicCase(query="hi", then=(), progress=0.5),
                             DynamicCase(query="", then=(), progress=1.0)])
        _, calls = self._run_with_callback(persona, goal, sim)
        assert len(calls) == 1
        assert calls[0][0] == "myp:myg:1"

    def test_callback_receives_fully_populated_turn_result(self):
        persona = make_persona()
        goal = make_goal()
        sim = MockSimulator([DynamicCase(query="hello", then=(), progress=0.5),
                             DynamicCase(query="", then=(), progress=1.0)])
        _, calls = self._run_with_callback(persona, goal, sim)
        assert len(calls) == 1
        tr = calls[0][1]
        assert tr.turn_number == 1
        assert tr.user_message == "hello"
        assert tr.agent_response == "Agent reply."
        assert tr.error is None

    def test_not_called_when_progress_1_first(self):
        """If simulator immediately returns progress=1.0, no turns are sent."""
        persona = make_persona()
        goal = make_goal()
        sim = MockSimulator([DynamicCase(query="", then=(), progress=1.0)])
        _, calls = self._run_with_callback(persona, goal, sim)
        assert calls == []


# ── Transcript files ──────────────────────────────────────────────────────────


class TestTranscriptFiles:
    def _run_all(self, conversations, transcript_dir=None):
        from unittest.mock import patch

        class QuickSim:
            async def generate_case(self, *a, **kw):
                return DynamicCase(query="", then=(), progress=1.0)
            async def close(self): pass

        class QuickAdapter:
            def invoke(self, *a, **kw):
                from beval.types import Subject
                return Subject(input="q", output="a", completion_time=0.0)
            def close(self): pass

        context = make_context()
        with patch("beval.conversation.runner.load_simulator_from_config",
                   return_value=QuickSim()), \
             patch("beval.conversation.runner.create_adapter",
                   return_value=QuickAdapter()):
            return asyncio.run(
                _run_all_actors(
                    conversations,
                    agent_def={"name": "mock", "protocol": "acp", "connection": {}},
                    simulator_config={},
                    context=context,
                    max_parallel_actors=1,
                    run_timeout_seconds=None,
                    transcript_dir=transcript_dir,
                )
            )

    def test_no_files_when_transcript_dir_is_none(self, tmp_path):
        persona = make_persona()
        goal = make_goal()
        convs = _build_conversations([persona], {goal.id: goal}, 1)
        self._run_all(convs, transcript_dir=None)
        assert list(tmp_path.iterdir()) == []

    def test_creates_one_file_per_actor(self, tmp_path):
        persona = make_persona()
        goal = make_goal()
        convs = _build_conversations([persona], {goal.id: goal}, actor_count=2)
        self._run_all(convs, transcript_dir=tmp_path)
        files = sorted(tmp_path.iterdir())
        assert len(files) == 2

    def test_filename_uses_safe_actor_id(self, tmp_path):
        persona = make_persona(id="my_persona", goals=["my_goal"])
        goal = make_goal(id="my_goal")
        convs = _build_conversations([persona], {goal.id: goal}, 1)
        self._run_all(convs, transcript_dir=tmp_path)
        names = [f.name for f in tmp_path.iterdir()]
        assert "my_persona_my_goal_1.json" in names

    def test_transcript_is_valid_json(self, tmp_path):
        import json
        persona = make_persona()
        goal = make_goal()
        convs = _build_conversations([persona], {goal.id: goal}, 1)
        self._run_all(convs, transcript_dir=tmp_path)
        f = next(tmp_path.iterdir())
        data = json.loads(f.read_text())
        assert data["persona_id"] == "test_user"
        assert data["goal_id"] == "test_goal"
        assert "turns" in data

    def test_transcript_contains_turn_data(self, tmp_path):
        import json
        persona = make_persona()
        goal = make_goal(given=GoalGiven(objective="t", max_turns=2))

        class TwoTurnSim:
            _count = 0
            async def generate_case(self, *a, **kw):
                self._count += 1
                if self._count == 1:
                    return DynamicCase(query="hello", then=(), progress=0.5)
                return DynamicCase(query="", then=(), progress=1.0)
            async def close(self): pass

        from unittest.mock import patch

        class QuickAdapter:
            def invoke(self, *a, **kw):
                from beval.types import Subject
                return Subject(input="q", output="agent says hi", completion_time=0.0)
            def close(self): pass

        context = make_context()
        with patch("beval.conversation.runner.load_simulator_from_config",
                   return_value=TwoTurnSim()), \
             patch("beval.conversation.runner.create_adapter",
                   return_value=QuickAdapter()):
            asyncio.run(
                _run_all_actors(
                    _build_conversations([persona], {goal.id: goal}, 1),
                    agent_def={"name": "mock", "protocol": "acp", "connection": {}},
                    simulator_config={},
                    context=context,
                    max_parallel_actors=1,
                    run_timeout_seconds=None,
                    transcript_dir=tmp_path,
                )
            )

        f = next(tmp_path.iterdir())
        data = json.loads(f.read_text())
        assert len(data["turns"]) == 1
        assert data["turns"][0]["user_message"] == "hello"
        assert data["turns"][0]["agent_response"] == "agent says hi"
