"""Tests for beval grader registry and resolution."""

from __future__ import annotations

from typing import Any

from beval.graders import (
    GraderEntry,
    get_registered_graders,
    match_grader,
    register_grader,
    resolve_grade,
)
from beval.types import (
    EvalContext,
    EvaluationMode,
    Grade,
    GraderLayer,
    Subject,
)


def _simple_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """A minimal passing grader for testing."""
    return Grade(
        criterion=criterion,
        score=1.0,
        metric="quality",
        passed=True,
        detail="Test grader passed.",
        layer=GraderLayer.DETERMINISTIC,
    )


def _quality_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """A grader that returns a specific score."""
    return Grade(
        criterion=criterion,
        score=0.8,
        metric="quality",
        passed=True,
        detail="Quality grader.",
        layer=GraderLayer.DETERMINISTIC,
    )


def _ai_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """An AI-judged grader for mode testing."""
    return Grade(
        criterion=criterion,
        score=0.9,
        metric="relevance",
        passed=True,
        detail="AI grader.",
        layer=GraderLayer.AI_JUDGED,
    )


def _process_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """A process grader for mode testing."""
    return Grade(
        criterion=criterion,
        score=0.7,
        metric="cost",
        passed=True,
        detail="Process grader.",
        layer=GraderLayer.PROCESS,
    )


class TestGraderEntry:
    def test_grader_entry_creation(self) -> None:
        """GraderEntry stores pattern, handler, layer, and metric."""
        entry = GraderEntry(
            pattern="test pattern",
            handler=_simple_grader,
            layer=GraderLayer.DETERMINISTIC,
            metric="quality",
        )
        assert entry.pattern == "test pattern"
        assert entry.handler is _simple_grader
        assert entry.layer == GraderLayer.DETERMINISTIC
        assert entry.metric == "quality"

    def test_grader_entry_pattern_lowercased(self) -> None:
        """GraderEntry stores pattern in lowercase."""
        entry = GraderEntry(
            pattern="Test PATTERN",
            handler=_simple_grader,
            layer=GraderLayer.DETERMINISTIC,
            metric="quality",
        )
        assert entry.pattern == "test pattern"


class TestRegisterGrader:
    def test_register_grader_adds_to_registry(self) -> None:
        """register_grader() adds entry to the registry."""
        initial_count = len(get_registered_graders())
        register_grader(
            "test criterion",
            _simple_grader,
            layer=GraderLayer.DETERMINISTIC,
            metric="quality",
        )
        graders = get_registered_graders()
        assert len(graders) == initial_count + 1

    def test_register_grader_with_defaults(self) -> None:
        """register_grader() uses default layer and metric."""
        register_grader("default test", _simple_grader)
        graders = get_registered_graders()
        entry = next((g for g in graders if g.pattern == "default test"), None)
        assert entry is not None
        assert entry.layer == GraderLayer.DETERMINISTIC
        assert entry.metric == "quality"

    def test_multiple_registrations(self) -> None:
        """Multiple register_grader() calls accumulate."""
        initial_count = len(get_registered_graders())
        register_grader("pattern1", _simple_grader)
        register_grader("pattern2", _quality_grader)
        graders = get_registered_graders()
        assert len(graders) == initial_count + 2


class TestMatchGrader:
    def test_match_exact(self) -> None:
        """match_grader() finds exact match."""
        register_grader("the answer should mention", _simple_grader)
        entry = match_grader("the answer should mention")
        assert entry is not None
        assert entry.pattern == "the answer should mention"

    def test_match_case_insensitive(self) -> None:
        """match_grader() is case-insensitive."""
        register_grader("should be correct", _simple_grader)
        entry = match_grader("Should Be Correct")
        assert entry is not None
        assert entry.pattern == "should be correct"

    def test_match_prefix(self) -> None:
        """match_grader() matches by prefix."""
        register_grader("should mention", _simple_grader)
        entry = match_grader("should mention AI")
        assert entry is not None
        assert entry.pattern == "should mention"

    def test_match_returns_longest_prefix(self) -> None:
        """When multiple patterns match, match_grader() returns longest prefix."""
        register_grader("should", _simple_grader, metric="quality")
        register_grader("should mention", _quality_grader, metric="relevance")
        entry = match_grader("should mention AI")
        # "should mention" is longer prefix, wins over "should"
        assert entry is not None
        assert entry.metric == "relevance"

    def test_match_ambiguous_returns_none(self) -> None:
        """match_grader() returns None for ambiguous same-length matches."""
        register_grader("same pattern", _simple_grader)
        register_grader("same pattern", _quality_grader)
        entry = match_grader("same pattern with extra")
        assert entry is None

    def test_match_no_match(self) -> None:
        """match_grader() returns None when no pattern matches."""
        register_grader("known pattern", _simple_grader)
        entry = match_grader("unknown pattern")
        assert entry is None

    def test_match_empty_string(self) -> None:
        """match_grader() with empty string returns None."""
        register_grader("test", _simple_grader)
        entry = match_grader("")
        assert entry is None


class TestResolveGrade:
    def test_resolve_grade_success(self, sample_subject: Subject) -> None:
        """resolve_grade() invokes handler and returns Grade."""
        register_grader("passes", _simple_grader)
        grade = resolve_grade(
            "passes",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.VALIDATION),
        )
        assert grade.criterion == "passes"
        assert grade.score == 1.0
        assert grade.passed is True

    def test_resolve_grade_no_match(self, sample_subject: Subject) -> None:
        """resolve_grade() returns failed Grade when no grader matches."""
        grade = resolve_grade(
            "nonexistent criterion",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.VALIDATION),
        )
        assert grade.score == 0.0
        assert grade.passed is False
        assert "No grader found" in grade.detail

    def test_resolve_grade_with_args(self, sample_subject: Subject) -> None:
        """resolve_grade() passes args to grader handler."""

        def grader_with_args(
            criterion: str, args: list[Any], subject: Subject, context: Any
        ) -> Grade:
            return Grade(
                criterion=criterion,
                score=1.0,
                metric="quality",
                passed=True,
                detail=f"Args: {args}",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("test args", grader_with_args)
        grade = resolve_grade(
            "test args",
            ["arg1", "arg2"],
            sample_subject,
            EvalContext(mode=EvaluationMode.VALIDATION),
        )
        assert "arg1" in grade.detail
        assert "arg2" in grade.detail

    def test_resolve_grade_ai_judged_skipped_in_dev(
        self, sample_subject: Subject
    ) -> None:
        """AI-judged graders are skipped in DEV mode."""
        register_grader(
            "ai criterion", _ai_grader, layer=GraderLayer.AI_JUDGED, metric="relevance"
        )
        grade = resolve_grade(
            "ai criterion",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV),
        )
        assert grade.skipped is True
        assert "not active in" in grade.detail
        assert grade.score == 0.0

    def test_resolve_grade_ai_judged_skipped_in_dev_process(
        self, sample_subject: Subject
    ) -> None:
        """AI-judged graders are skipped in DEV_PROCESS mode."""
        register_grader("ai criterion", _ai_grader, layer=GraderLayer.AI_JUDGED)
        grade = resolve_grade(
            "ai criterion",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV_PROCESS),
        )
        assert grade.skipped is True

    def test_resolve_grade_ai_judged_active_in_validation(
        self, sample_subject: Subject
    ) -> None:
        """AI-judged graders are active in VALIDATION mode."""
        register_grader("ai criterion", _ai_grader, layer=GraderLayer.AI_JUDGED)
        grade = resolve_grade(
            "ai criterion",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.VALIDATION),
        )
        assert grade.skipped is not True
        assert grade.score == 0.9

    def test_resolve_grade_process_skipped_in_dev(
        self, sample_subject: Subject
    ) -> None:
        """Process graders are skipped in DEV mode."""
        register_grader("process criterion", _process_grader, layer=GraderLayer.PROCESS)
        grade = resolve_grade(
            "process criterion",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV),
        )
        assert grade.skipped is True
        assert "not active in dev mode" in grade.detail

    def test_resolve_grade_process_active_in_dev_process(
        self, sample_subject: Subject
    ) -> None:
        """Process graders are active in DEV_PROCESS mode."""
        register_grader("process criterion", _process_grader, layer=GraderLayer.PROCESS)
        grade = resolve_grade(
            "process criterion",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV_PROCESS),
        )
        assert grade.skipped is not True
        assert grade.score == 0.7

    def test_resolve_grade_process_active_in_validation(
        self, sample_subject: Subject
    ) -> None:
        """Process graders are active in VALIDATION mode."""
        register_grader("process criterion", _process_grader, layer=GraderLayer.PROCESS)
        grade = resolve_grade(
            "process criterion",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.VALIDATION),
        )
        assert grade.skipped is not True

    def test_resolve_grade_enforces_threshold_fail(
        self, sample_subject: Subject
    ) -> None:
        """Grade passed is overridden when score <= threshold (§5.3)."""

        def low_score_passes(
            criterion: str,
            args: list[Any],
            subject: Subject,
            context: Any,
        ) -> Grade:
            return Grade(
                criterion=criterion,
                score=0.3,
                metric="quality",
                passed=True,  # handler claims pass
                detail="Low score.",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("low score", low_score_passes)
        grade = resolve_grade(
            "low score",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV),
        )
        assert grade.score == 0.3
        assert grade.passed is False  # runner enforces threshold

    def test_resolve_grade_enforces_threshold_pass(
        self, sample_subject: Subject
    ) -> None:
        """Grade passed is corrected when score > threshold (§5.3)."""

        def high_score_fails(
            criterion: str,
            args: list[Any],
            subject: Subject,
            context: Any,
        ) -> Grade:
            return Grade(
                criterion=criterion,
                score=0.9,
                metric="quality",
                passed=False,  # handler claims fail
                detail="High score.",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("high score", high_score_fails)
        grade = resolve_grade(
            "high score",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV),
        )
        assert grade.score == 0.9
        assert grade.passed is True  # runner enforces threshold

    def test_resolve_grade_threshold_boundary(self, sample_subject: Subject) -> None:
        """Score exactly at threshold passes (>= not >, §5.3)."""

        def exact_threshold(
            criterion: str,
            args: list[Any],
            subject: Subject,
            context: Any,
        ) -> Grade:
            return Grade(
                criterion=criterion,
                score=0.5,
                metric="quality",
                passed=False,
                detail="At threshold.",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("exact", exact_threshold)
        grade = resolve_grade(
            "exact",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV),
        )
        assert grade.score == 0.5
        assert grade.passed is True  # 0.5 >= 0.5

    def test_resolve_grade_custom_threshold(self, sample_subject: Subject) -> None:
        """Custom grade_pass_threshold from config is honoured."""
        from beval.types import RunConfig

        def mid_score(
            criterion: str,
            args: list[Any],
            subject: Subject,
            context: Any,
        ) -> Grade:
            return Grade(
                criterion=criterion,
                score=0.3,
                metric="quality",
                passed=False,
                detail="Mid score.",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("mid", mid_score)
        config = RunConfig(grade_pass_threshold=0.2)
        grade = resolve_grade(
            "mid",
            [],
            sample_subject,
            EvalContext(mode=EvaluationMode.DEV, config=config),
        )
        assert grade.score == 0.3
        assert grade.passed is True  # 0.3 > 0.2


class TestRegistry:
    def test_get_registered_graders_returns_copy(self) -> None:
        """get_registered_graders() returns a copy, not the internal list."""
        graders1 = get_registered_graders()
        graders2 = get_registered_graders()
        assert graders1 is not graders2


def _make_context(mode: EvaluationMode = EvaluationMode.VALIDATION) -> EvalContext:
    """Helper to create an EvalContext with a given mode."""
    return EvalContext(mode=mode)


def _register_builtins() -> None:
    """Re-register built-in graders after registry clear."""
    from beval.graders import register_builtin_graders

    register_builtin_graders()


class TestDeterministicGraders:
    """Tests for deterministic built-in graders."""

    def test_completion_time_under_threshold(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="a", completion_time=2.0)
        grade = resolve_grade(
            "completion time should be under 10",
            ["10"],
            subject,
            _make_context(),
        )
        assert grade.passed
        assert grade.score > 0.5
        assert grade.layer == GraderLayer.DETERMINISTIC

    def test_completion_time_over_threshold(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="a", completion_time=15.0)
        grade = resolve_grade(
            "completion time should be under 10",
            ["10"],
            subject,
            _make_context(),
        )
        assert not grade.passed

    def test_response_contains_keyword_found(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="Hello World", completion_time=1.0)
        grade = resolve_grade(
            "response should contain hello",
            ["hello"],
            subject,
            _make_context(),
        )
        assert grade.passed
        assert grade.score == 1.0

    def test_response_contains_keyword_missing(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="Hello World", completion_time=1.0)
        grade = resolve_grade(
            "response should contain goodbye",
            ["goodbye"],
            subject,
            _make_context(),
        )
        assert not grade.passed
        assert grade.score == 0.0

    def test_response_not_contains_absent(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="Hello World", completion_time=1.0)
        grade = resolve_grade(
            "response should not contain goodbye",
            ["goodbye"],
            subject,
            _make_context(),
        )
        assert grade.passed
        assert grade.score == 1.0

    def test_response_not_contains_present(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="Hello World", completion_time=1.0)
        grade = resolve_grade(
            "response should not contain hello",
            ["hello"],
            subject,
            _make_context(),
        )
        assert not grade.passed
        assert grade.score == 0.0

    def test_response_length_in_range(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="Hello", completion_time=1.0)
        grade = resolve_grade(
            "response length should be between 1 and 100",
            ["1", "100"],
            subject,
            _make_context(),
        )
        assert grade.passed
        assert grade.score == 1.0

    def test_response_length_out_of_range(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="Hi", completion_time=1.0)
        grade = resolve_grade(
            "response length should be at least 100",
            ["100", "200"],
            subject,
            _make_context(),
        )
        assert not grade.passed
        assert grade.score < 1.0

    def test_response_matches_pattern(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="abc123", completion_time=1.0)
        grade = resolve_grade(
            "response should match digits",
            [r"\d+"],
            subject,
            _make_context(),
        )
        assert grade.passed
        assert grade.score == 1.0

    def test_response_matches_pattern_no_match(self) -> None:
        _register_builtins()
        subject = Subject(input="q", output="abcdef", completion_time=1.0)
        grade = resolve_grade(
            "response should match digits",
            [r"^\d+$"],
            subject,
            _make_context(),
        )
        assert not grade.passed
        assert grade.score == 0.0


class TestProcessGraders:
    """Tests for process-layer built-in graders."""

    def test_has_span_found(self) -> None:
        _register_builtins()
        subject = Subject(
            input="q",
            output="a",
            completion_time=1.0,
            spans=[{"name": "retrieval", "duration": 0.5}],
        )
        grade = resolve_grade(
            "should have span retrieval",
            ["retrieval"],
            subject,
            _make_context(EvaluationMode.DEV_PROCESS),
        )
        assert grade.passed
        assert grade.layer == GraderLayer.PROCESS

    def test_has_span_not_found(self) -> None:
        _register_builtins()
        subject = Subject(
            input="q",
            output="a",
            completion_time=1.0,
            spans=[],
        )
        grade = resolve_grade(
            "should have span retrieval",
            ["retrieval"],
            subject,
            _make_context(EvaluationMode.DEV_PROCESS),
        )
        assert not grade.passed

    def test_calls_tool_found(self) -> None:
        _register_builtins()
        subject = Subject(
            input="q",
            output="a",
            completion_time=1.0,
            tool_calls=[{"name": "search", "args": {}}],
        )
        grade = resolve_grade(
            "should call tool search",
            ["search"],
            subject,
            _make_context(EvaluationMode.DEV_PROCESS),
        )
        assert grade.passed

    def test_calls_tool_not_found(self) -> None:
        _register_builtins()
        subject = Subject(
            input="q",
            output="a",
            completion_time=1.0,
            tool_calls=[],
        )
        grade = resolve_grade(
            "should call tool search",
            ["search"],
            subject,
            _make_context(EvaluationMode.DEV_PROCESS),
        )
        assert not grade.passed

    def test_tool_call_count_exact(self) -> None:
        _register_builtins()
        subject = Subject(
            input="q",
            output="a",
            completion_time=1.0,
            tool_calls=[{"name": "a"}, {"name": "b"}],
        )
        grade = resolve_grade(
            "tool call count should be 2",
            ["2"],
            subject,
            _make_context(EvaluationMode.DEV_PROCESS),
        )
        assert grade.passed
        assert grade.score == 1.0

    def test_tool_call_count_mismatch(self) -> None:
        _register_builtins()
        subject = Subject(
            input="q",
            output="a",
            completion_time=1.0,
            tool_calls=[{"name": "a"}],
        )
        grade = resolve_grade(
            "tool call count should be 3",
            ["3"],
            subject,
            _make_context(EvaluationMode.DEV_PROCESS),
        )
        assert not grade.passed
        assert grade.score < 1.0
