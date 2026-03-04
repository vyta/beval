"""Tests for beval core types."""

from __future__ import annotations

from beval.types import (
    CaseResult,
    EvaluationMode,
    Grade,
    GraderLayer,
    MetricCategory,
    RunConfig,
    RunSummary,
    Subject,
)


class TestGrade:
    def test_grade_creation(self) -> None:
        grade = Grade(
            criterion="test criterion",
            score=0.8,
            metric="relevance",
            passed=True,
            detail="Test detail",
            layer=GraderLayer.DETERMINISTIC,
        )
        assert grade.score == 0.8
        assert grade.passed is True
        assert grade.layer == GraderLayer.DETERMINISTIC

    def test_grade_is_frozen(self) -> None:
        grade = Grade(
            criterion="test",
            score=1.0,
            metric="quality",
            passed=True,
            detail=None,
            layer=GraderLayer.DETERMINISTIC,
        )
        try:
            grade.score = 0.5  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("Grade should be frozen")  # noqa: TRY003


class TestSubject:
    def test_subject_defaults(self) -> None:
        subject = Subject(input="q", output="a", completion_time=1.0)
        assert subject.tool_calls == []
        assert subject.metadata == {}
        assert subject.spans == []

    def test_subject_is_frozen(self) -> None:
        subject = Subject(input="q", output="a", completion_time=1.0)
        try:
            subject.input = "new"  # type: ignore[misc]
        except AttributeError:
            pass
        else:
            raise AssertionError("Subject should be frozen")  # noqa: TRY003

    def test_subject_query_answer_aliases(self) -> None:
        subject = Subject(input="q", output="a", completion_time=1.0)
        assert subject.query == "q"
        assert subject.answer == "a"

    def test_subject_message_array_aliases(self) -> None:
        subject = Subject(
            input=[{"role": "user", "content": "hello"}],
            output=[{"role": "assistant", "content": "hi"}],
            completion_time=1.0,
        )
        assert subject.query == "hello"
        assert subject.answer == "hi"


class TestMetricCategory:
    def test_all_categories_defined(self) -> None:
        expected = {
            "latency",
            "coverage",
            "relevance",
            "groundedness",
            "correctness",
            "quality",
            "safety",
            "cost",
        }
        actual = {c.value for c in MetricCategory}
        assert actual == expected


class TestEvaluationMode:
    def test_modes(self) -> None:
        assert EvaluationMode.DEV.value == "dev"
        assert EvaluationMode.VALIDATION.value == "validation"


class TestRunConfig:
    def test_defaults(self) -> None:
        config = RunConfig()
        assert config.grade_pass_threshold == 0.5
        assert config.case_pass_threshold == 0.7


class TestCaseResult:
    def test_creation(self, sample_grade: Grade) -> None:
        result = CaseResult(
            id="test_case",
            name="Test Case",
            category="test",
            overall_score=0.8,
            passed=True,
            time_seconds=1.0,
            metric_scores={"relevance": 0.8},
            error=None,
            grades=[sample_grade],
        )
        assert result.id == "test_case"
        assert len(result.grades) == 1


class TestRunSummary:
    def test_creation(self) -> None:
        summary = RunSummary(
            overall_score=0.85,
            passed=3,
            failed=1,
            errored=0,
            total=4,
            metrics={"relevance": 0.9},
        )
        assert summary.total == 4
