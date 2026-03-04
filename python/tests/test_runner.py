"""Tests for beval runner orchestration."""

from __future__ import annotations

from typing import Any

from beval.dsl import CaseBuilder, case
from beval.graders import register_grader
from beval.runner import Runner
from beval.types import (
    EvaluationMode,
    Grade,
    GraderLayer,
    RunConfig,
    Subject,
    TrialAggregation,
)


def _passing_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """A grader that always passes."""
    return Grade(
        criterion=criterion,
        score=1.0,
        metric="quality",
        passed=True,
        detail="Passed.",
        layer=GraderLayer.DETERMINISTIC,
    )


def _failing_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """A grader that always fails."""
    return Grade(
        criterion=criterion,
        score=0.0,
        metric="quality",
        passed=False,
        detail="Failed.",
        layer=GraderLayer.DETERMINISTIC,
    )


def _half_score_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """A grader that returns 0.5."""
    return Grade(
        criterion=criterion,
        score=0.5,
        metric="quality",
        passed=True,
        detail="Half score.",
        layer=GraderLayer.DETERMINISTIC,
    )


def _relevance_grader(
    criterion: str, args: list[Any], subject: Subject, context: Any
) -> Grade:
    """A grader for relevance metric."""
    return Grade(
        criterion=criterion,
        score=0.8,
        metric="relevance",
        passed=True,
        detail="Relevance check.",
        layer=GraderLayer.DETERMINISTIC,
    )


class TestRunnerInit:
    def test_runner_defaults(self) -> None:
        """Runner() uses default mode and config."""
        runner = Runner()
        assert runner.mode == EvaluationMode.DEV
        assert runner.config is not None
        assert runner.handler is None

    def test_runner_with_mode(self) -> None:
        """Runner() accepts mode parameter."""
        runner = Runner(mode=EvaluationMode.VALIDATION)
        assert runner.mode == EvaluationMode.VALIDATION

    def test_runner_with_config(self) -> None:
        """Runner() accepts config parameter."""
        config = RunConfig(case_pass_threshold=0.9)
        runner = Runner(config=config)
        assert runner.config.case_pass_threshold == 0.9

    def test_runner_with_handler(self) -> None:
        """Runner() accepts handler parameter."""

        def dummy_handler():
            pass

        runner = Runner(handler=dummy_handler)
        assert runner.handler is dummy_handler


class TestRunnerExecute:
    def test_run_with_no_cases(self) -> None:
        """Runner.run() with empty registry returns empty result."""
        runner = Runner()
        result = runner.run()
        assert result.summary.total == 0
        assert result.summary.passed == 0
        assert len(result.cases) == 0

    def test_run_with_single_case(self) -> None:
        """Runner.run() executes a single registered case."""
        register_grader("passes", _passing_grader)

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("passes")

        runner = Runner()
        result = runner.run()
        assert result.summary.total == 1
        assert len(result.cases) == 1
        assert result.cases[0].id == "test_func"
        assert result.cases[0].name == "Test case"

    def test_run_sets_label(self) -> None:
        """Runner.run() sets label in RunResult."""
        runner = Runner()
        result = runner.run(label="test-run")
        assert result.label == "test-run"

    def test_run_sets_timestamp(self) -> None:
        """Runner.run() sets timestamp in RunResult."""
        runner = Runner()
        result = runner.run()
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO 8601 format

    def test_run_case_with_error(self) -> None:
        """Runner._run_case() handles exceptions in case function."""

        @case("Failing case")
        def test_func(s: CaseBuilder) -> None:
            raise ValueError("Test error")

        runner = Runner()
        result = runner.run()
        assert result.summary.errored == 1
        assert result.cases[0].error == "Test error"
        assert result.cases[0].passed is False

    def test_run_case_passes_builder(self) -> None:
        """Runner._run_case() passes CaseBuilder to case function."""
        register_grader("passes", _passing_grader)

        received_builder = None

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            nonlocal received_builder
            received_builder = s
            s.then("passes")

        runner = Runner()
        runner.run()
        assert received_builder is not None
        assert isinstance(received_builder, CaseBuilder)

    def test_run_case_executes_graders(self) -> None:
        """Runner._run_case() executes graders for then-clauses."""
        register_grader("passes", _passing_grader)

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("passes")

        runner = Runner()
        result = runner.run()
        assert len(result.cases[0].grades) == 1
        assert result.cases[0].grades[0].criterion == "passes"

    def test_run_case_multiple_thens(self) -> None:
        """Runner._run_case() executes multiple then-clauses."""
        register_grader("passes", _passing_grader)
        register_grader("also passes", _passing_grader)

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("passes").then("also passes")

        runner = Runner()
        result = runner.run()
        assert len(result.cases[0].grades) == 2

    def test_run_case_error_stores_elapsed_time(self) -> None:
        """Runner._run_case() records time even when case errors."""

        @case("Failing case")
        def test_func(s: CaseBuilder) -> None:
            raise ValueError("Error")

        runner = Runner()
        result = runner.run()
        assert result.cases[0].time_seconds > 0


class TestScoreAggregation:
    def test_overall_score_single_grade(self) -> None:
        """CaseResult.overall_score is the grade score when only one grade."""
        register_grader("half", _half_score_grader)

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("half")

        runner = Runner()
        result = runner.run()
        assert result.cases[0].overall_score == 0.5

    def test_overall_score_multiple_grades(self) -> None:
        """CaseResult.overall_score is average of all grades."""
        register_grader("passes", _passing_grader)  # 1.0
        register_grader("half", _half_score_grader)  # 0.5

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("passes").then("half")

        runner = Runner()
        result = runner.run()
        # Average: (1.0 + 0.5) / 2 = 0.75
        assert result.cases[0].overall_score == 0.75

    def test_overall_score_skips_skipped_grades(self) -> None:
        """CaseResult.overall_score excludes skipped grades."""
        register_grader("passes", _passing_grader)

        def skipped_grader(
            criterion: str, args: list[Any], subject: Subject, context: Any
        ) -> Grade:
            return Grade(
                criterion=criterion,
                score=0.0,
                metric="quality",
                passed=False,
                detail="Skipped",
                layer=GraderLayer.AI_JUDGED,
                skipped=True,
            )

        register_grader("skipped", skipped_grader, layer=GraderLayer.AI_JUDGED)

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("passes").then("skipped")

        runner = Runner()
        result = runner.run()
        # Only "passes" (1.0) should count
        assert result.cases[0].overall_score == 1.0

    def test_metric_scores_aggregation(self) -> None:
        """CaseResult.metric_scores aggregates by metric."""
        register_grader("quality check", _half_score_grader, metric="quality")
        register_grader("relevance check", _relevance_grader, metric="relevance")

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("quality check").then("relevance check")

        runner = Runner()
        result = runner.run()
        assert result.cases[0].metric_scores["quality"] == 0.5
        assert result.cases[0].metric_scores["relevance"] == 0.8

    def test_metric_scores_average_multiple(self) -> None:
        """CaseResult.metric_scores averages multiple grades per metric."""
        register_grader("quality1", _passing_grader, metric="quality")
        register_grader("quality2", _half_score_grader, metric="quality")

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("quality1").then("quality2")

        runner = Runner()
        result = runner.run()
        # Average: (1.0 + 0.5) / 2 = 0.75
        assert result.cases[0].metric_scores["quality"] == 0.75

    def test_passed_uses_threshold(self) -> None:
        """CaseResult.passed checks against case_pass_threshold."""
        register_grader("half", _half_score_grader)

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("half")

        config = RunConfig(case_pass_threshold=0.7)
        runner = Runner(config=config)
        result = runner.run()
        # Score 0.5 < threshold 0.7
        assert result.cases[0].passed is False

    def test_passed_at_threshold(self) -> None:
        """CaseResult.passed uses >= comparison."""
        register_grader("passes", _passing_grader)

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            s.then("passes")

        config = RunConfig(case_pass_threshold=1.0)
        runner = Runner(config=config)
        result = runner.run()
        # Score 1.0 >= threshold 1.0
        assert result.cases[0].passed is True


class TestSummaryAggregation:
    def test_summary_passed_count(self) -> None:
        """RunSummary.passed counts passing cases."""
        register_grader("passes", _passing_grader)

        @case("Case 1")
        def test_func1(s: CaseBuilder) -> None:
            s.then("passes")

        @case("Case 2")
        def test_func2(s: CaseBuilder) -> None:
            s.then("passes")

        runner = Runner()
        result = runner.run()
        assert result.summary.passed == 2

    def test_summary_failed_count(self) -> None:
        """RunSummary.failed counts non-passing, non-errored cases."""
        register_grader("passes", _passing_grader)
        register_grader("fails", _failing_grader)

        @case("Pass case")
        def test_func1(s: CaseBuilder) -> None:
            s.then("passes")

        @case("Fail case")
        def test_func2(s: CaseBuilder) -> None:
            s.then("fails")

        runner = Runner()
        result = runner.run()
        assert result.summary.passed == 1
        assert result.summary.failed == 1

    def test_summary_errored_count(self) -> None:
        """RunSummary.errored counts cases with exceptions."""

        @case("Error case")
        def test_func1(s: CaseBuilder) -> None:
            raise ValueError("Error")

        @case("Another error")
        def test_func2(s: CaseBuilder) -> None:
            raise RuntimeError("Another")

        runner = Runner()
        result = runner.run()
        assert result.summary.errored == 2
        assert result.summary.failed == 0

    def test_summary_overall_score(self) -> None:
        """RunSummary.overall_score is average of non-errored cases."""
        register_grader("passes", _passing_grader)
        register_grader("half", _half_score_grader)

        @case("Case 1")
        def test_func1(s: CaseBuilder) -> None:
            s.then("passes")

        @case("Case 2")
        def test_func2(s: CaseBuilder) -> None:
            s.then("half")

        runner = Runner()
        result = runner.run()
        # Average: (1.0 + 0.5) / 2 = 0.75
        assert result.summary.overall_score == 0.75

    def test_summary_excludes_errored_from_score(self) -> None:
        """RunSummary.overall_score excludes errored cases."""
        register_grader("passes", _passing_grader)

        @case("Pass case")
        def test_func1(s: CaseBuilder) -> None:
            s.then("passes")

        @case("Error case")
        def test_func2(s: CaseBuilder) -> None:
            raise ValueError("Error")

        runner = Runner()
        result = runner.run()
        # Only "Pass case" (1.0) should count
        assert result.summary.overall_score == 1.0

    def test_summary_metrics_aggregation(self) -> None:
        """RunSummary.metrics aggregates across all cases."""
        register_grader("quality", _passing_grader, metric="quality")
        register_grader("relevance", _relevance_grader, metric="relevance")

        @case("Case 1")
        def test_func1(s: CaseBuilder) -> None:
            s.then("quality")

        @case("Case 2")
        def test_func2(s: CaseBuilder) -> None:
            s.then("relevance")

        runner = Runner()
        result = runner.run()
        # Each case contributes one metric score
        assert result.summary.metrics["quality"] == 1.0
        assert result.summary.metrics["relevance"] == 0.8

    def test_summary_total_count(self) -> None:
        """RunSummary.total equals passed + failed + errored."""
        register_grader("passes", _passing_grader)
        register_grader("fails", _failing_grader)

        @case("Pass")
        def test_func1(s: CaseBuilder) -> None:
            s.then("passes")

        @case("Fail")
        def test_func2(s: CaseBuilder) -> None:
            s.then("fails")

        @case("Error")
        def test_func3(s: CaseBuilder) -> None:
            raise ValueError("Error")

        runner = Runner()
        result = runner.run()
        assert result.summary.total == 3
        assert (
            result.summary.passed + result.summary.failed + result.summary.errored == 3
        )


class TestRunWithExplicitCases:
    def test_run_with_explicit_case_list(self) -> None:
        """Runner.run(cases=[...]) uses provided cases, not registry."""
        from beval.dsl import CaseDefinition

        # Register a case in the registry
        register_grader("passes", _passing_grader)

        @case("Registry case")
        def registry_func(s: CaseBuilder) -> None:
            s.then("passes")

        # Create an explicit case
        def explicit_func(s: CaseBuilder) -> None:
            s.then("passes")

        explicit_case = CaseDefinition(
            id="explicit_case",
            name="Explicit case",
            category="test",
            tags=[],
            func=explicit_func,
        )

        runner = Runner()
        result = runner.run(cases=[explicit_case])

        # Should run only the explicit case, not the registry
        assert result.summary.total == 1
        assert result.cases[0].id == "explicit_case"


class TestTrialAggregation:
    def test_pass_at_k_with_k_parameter(self) -> None:
        """pass_at_k uses config.pass_at_k to determine required passes."""
        call_count = 0

        def alternating_grader(
            criterion: str, args: list[Any], subject: Subject, context: Any
        ) -> Grade:
            nonlocal call_count
            call_count += 1
            # Alternate: pass, fail, pass, fail, pass
            score = 1.0 if call_count % 2 == 1 else 0.0
            return Grade(
                criterion=criterion,
                score=score,
                metric="quality",
                passed=score > 0.5,
                detail="alternating",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("alt", alternating_grader)

        @case("trial test")
        def test_func(s: CaseBuilder) -> None:
            s.then("alt")

        # k=3: need at least 3 passes out of 5 trials
        config = RunConfig(pass_at_k=3)
        runner = Runner(
            trials=5,
            trial_aggregation=TrialAggregation.PASS_AT_K,
            config=config,
        )
        result = runner.run()
        # 3 passes out of 5: meets k=3
        assert result.cases[0].passed is True

    def test_pass_at_k_fails_below_threshold(self) -> None:
        """pass_at_k fails when fewer than k trials pass."""
        call_count = 0

        def mostly_fail(
            criterion: str, args: list[Any], subject: Subject, context: Any
        ) -> Grade:
            nonlocal call_count
            call_count += 1
            score = 1.0 if call_count == 1 else 0.0
            return Grade(
                criterion=criterion,
                score=score,
                metric="quality",
                passed=score > 0.5,
                detail="mostly fail",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("mf", mostly_fail)

        @case("k fail test")
        def test_func(s: CaseBuilder) -> None:
            s.then("mf")

        # k=2: need at least 2 passes, but only 1 will pass
        config = RunConfig(pass_at_k=2)
        runner = Runner(
            trials=3,
            trial_aggregation=TrialAggregation.PASS_AT_K,
            config=config,
        )
        result = runner.run()
        assert result.cases[0].passed is False

    def test_high_variance_flagged(self) -> None:
        """high_variance is True when stddev > 0.15 (§11.3)."""
        call_count = 0

        def volatile_grader(
            criterion: str, args: list[Any], subject: Subject, context: Any
        ) -> Grade:
            nonlocal call_count
            call_count += 1
            score = 1.0 if call_count % 2 == 1 else 0.0
            return Grade(
                criterion=criterion,
                score=score,
                metric="quality",
                passed=score > 0.5,
                detail="volatile",
                layer=GraderLayer.DETERMINISTIC,
            )

        register_grader("volatile", volatile_grader)

        @case("variance test")
        def test_func(s: CaseBuilder) -> None:
            s.then("volatile")

        runner = Runner(trials=4)
        result = runner.run()
        assert result.cases[0].high_variance is True
        assert result.cases[0].score_stddev is not None
        assert result.cases[0].score_stddev > 0.15

    def test_low_variance_not_flagged(self) -> None:
        """high_variance is False when stddev <= 0.15."""
        register_grader("passes", _passing_grader)

        @case("stable test")
        def test_func(s: CaseBuilder) -> None:
            s.then("passes")

        runner = Runner(trials=3)
        result = runner.run()
        assert result.cases[0].high_variance is False
