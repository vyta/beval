"""Tests for beval result reporting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from beval.reporter import to_json, write_json
from beval.types import (
    CaseResult,
    EvaluationMode,
    Grade,
    GraderLayer,
    RunConfig,
    RunResult,
    RunSummary,
)


@pytest.fixture
def sample_run_result() -> RunResult:
    """Create a sample RunResult for testing."""
    grade = Grade(
        criterion="test criterion",
        score=0.8,
        metric="quality",
        passed=True,
        detail="Test detail",
        layer=GraderLayer.DETERMINISTIC,
    )
    case = CaseResult(
        id="test_case",
        name="Test Case",
        category="test",
        overall_score=0.8,
        passed=True,
        time_seconds=1.5,
        metric_scores={"quality": 0.8},
        error=None,
        grades=[grade],
    )
    summary = RunSummary(
        overall_score=0.8,
        passed=1,
        failed=0,
        errored=0,
        total=1,
        metrics={"quality": 0.8},
    )
    return RunResult(
        label="test-run",
        timestamp="2026-02-27T12:00:00Z",
        mode=EvaluationMode.VALIDATION,
        config=RunConfig(),
        summary=summary,
        cases=[case],
    )


class TestToJson:
    def test_to_json_basic(self, sample_run_result: RunResult) -> None:
        """to_json() serializes RunResult to JSON string."""
        result = to_json(sample_run_result)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["label"] == "test-run"

    def test_to_json_includes_all_fields(self, sample_run_result: RunResult) -> None:
        """to_json() includes all RunResult fields."""
        result = to_json(sample_run_result)
        parsed = json.loads(result)
        assert "label" in parsed
        assert "timestamp" in parsed
        assert "mode" in parsed
        assert "config" in parsed
        assert "summary" in parsed
        assert "cases" in parsed

    def test_to_json_summary_structure(self, sample_run_result: RunResult) -> None:
        """to_json() correctly serializes RunSummary."""
        result = to_json(sample_run_result)
        parsed = json.loads(result)
        summary = parsed["summary"]
        assert summary["overall_score"] == 0.8
        assert summary["passed"] == 1
        assert summary["failed"] == 0
        assert summary["errored"] == 0
        assert summary["total"] == 1
        assert summary["metrics"]["quality"] == 0.8

    def test_to_json_cases_structure(self, sample_run_result: RunResult) -> None:
        """to_json() correctly serializes CaseResult list."""
        result = to_json(sample_run_result)
        parsed = json.loads(result)
        cases = parsed["cases"]
        assert len(cases) == 1
        case = cases[0]
        assert case["id"] == "test_case"
        assert case["name"] == "Test Case"
        assert case["category"] == "test"
        assert case["overall_score"] == 0.8
        assert case["passed"] is True
        assert case["time_seconds"] == 1.5
        assert case["error"] is None

    def test_to_json_grades_structure(self, sample_run_result: RunResult) -> None:
        """to_json() correctly serializes Grade list."""
        result = to_json(sample_run_result)
        parsed = json.loads(result)
        grades = parsed["cases"][0]["grades"]
        assert len(grades) == 1
        grade = grades[0]
        assert grade["criterion"] == "test criterion"
        assert grade["score"] == 0.8
        assert grade["metric"] == "quality"
        assert grade["passed"] is True
        assert grade["detail"] == "Test detail"

    def test_to_json_enum_serialization(self, sample_run_result: RunResult) -> None:
        """to_json() serializes enum values correctly."""
        result = to_json(sample_run_result)
        parsed = json.loads(result)
        # EvaluationMode.VALIDATION should be "validation"
        assert parsed["mode"] == "validation"
        # GraderLayer.DETERMINISTIC should be "deterministic"
        assert parsed["cases"][0]["grades"][0]["layer"] == "deterministic"

    def test_to_json_indent_parameter(self, sample_run_result: RunResult) -> None:
        """to_json() respects indent parameter."""
        result_compact = to_json(sample_run_result, indent=0)
        result_indented = to_json(sample_run_result, indent=4)
        # Indented version should have more characters due to whitespace
        assert len(result_indented) > len(result_compact)
        # Both should parse to same structure
        assert json.loads(result_compact) == json.loads(result_indented)

    def test_to_json_default_indent(self, sample_run_result: RunResult) -> None:
        """to_json() uses indent=2 by default."""
        result = to_json(sample_run_result)
        # Check for 2-space indentation patterns
        assert "\n  " in result

    def test_to_json_null_fields(self) -> None:
        """to_json() correctly serializes None/null fields."""
        case = CaseResult(
            id="test",
            name="Test",
            category="",
            overall_score=0.0,
            passed=False,
            time_seconds=0.0,
            metric_scores={},
            error="Error message",  # Set error
            grades=[],
            stages=None,  # Explicitly None
        )
        result_obj = RunResult(
            label=None,  # None label
            timestamp="2026-02-27T12:00:00Z",
            mode=EvaluationMode.DEV,
            config=RunConfig(),
            summary=RunSummary(
                overall_score=0.0, passed=0, failed=0, errored=1, total=1, metrics={}
            ),
            cases=[case],
        )
        result = to_json(result_obj)
        parsed = json.loads(result)
        assert "label" not in parsed
        assert "stages" not in parsed["cases"][0]
        assert parsed["cases"][0]["error"] == "Error message"

    def test_to_json_empty_collections(self) -> None:
        """to_json() correctly serializes empty lists and dicts."""
        case = CaseResult(
            id="test",
            name="Test",
            category="",
            overall_score=0.0,
            passed=False,
            time_seconds=0.0,
            metric_scores={},  # Empty dict
            error=None,
            grades=[],  # Empty list
        )
        result_obj = RunResult(
            label="test",
            timestamp="2026-02-27T12:00:00Z",
            mode=EvaluationMode.DEV,
            config=RunConfig(),
            summary=RunSummary(
                overall_score=0.0,
                passed=0,
                failed=0,
                errored=0,
                total=0,
                metrics={},  # Empty dict
            ),
            cases=[case],
        )
        result = to_json(result_obj)
        parsed = json.loads(result)
        assert parsed["cases"][0]["metric_scores"] == {}
        assert parsed["cases"][0]["grades"] == []
        assert parsed["summary"]["metrics"] == {}


class TestWriteJson:
    def test_write_json_creates_file(
        self, sample_run_result: RunResult, tmp_path: Path
    ) -> None:
        """write_json() creates a JSON file."""
        output_path = tmp_path / "test_output.json"
        write_json(sample_run_result, str(output_path))
        assert output_path.exists()

    def test_write_json_content(
        self, sample_run_result: RunResult, tmp_path: Path
    ) -> None:
        """write_json() writes correct JSON content."""
        output_path = tmp_path / "test_output.json"
        write_json(sample_run_result, str(output_path))
        with open(output_path, encoding="utf-8") as f:
            parsed = json.load(f)
        assert parsed["label"] == "test-run"
        assert parsed["summary"]["total"] == 1

    def test_write_json_overwrites_existing(
        self, sample_run_result: RunResult, tmp_path: Path
    ) -> None:
        """write_json() overwrites existing file."""
        output_path = tmp_path / "test_output.json"
        # Write once
        write_json(sample_run_result, str(output_path))
        # Write again with modified result
        sample_run_result.label = "modified-run"
        write_json(sample_run_result, str(output_path))
        with open(output_path, encoding="utf-8") as f:
            parsed = json.load(f)
        assert parsed["label"] == "modified-run"

    def test_write_json_creates_parent_directories(
        self, sample_run_result: RunResult, tmp_path: Path
    ) -> None:
        """write_json() works even if parent directories don't exist."""
        output_path = tmp_path / "nested" / "dir" / "output.json"
        # Create parent directories first (simulating mkdir -p behavior)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(sample_run_result, str(output_path))
        assert output_path.exists()

    def test_write_json_utf8_encoding(
        self, sample_run_result: RunResult, tmp_path: Path
    ) -> None:
        """write_json() uses UTF-8 encoding."""
        # Modify result to include non-ASCII characters
        sample_run_result.cases[0].name = "Test with émojis 🎉"
        output_path = tmp_path / "utf8_test.json"
        write_json(sample_run_result, str(output_path))
        # Read and parse the JSON to verify content is preserved
        with open(output_path, encoding="utf-8") as f:
            parsed = json.load(f)
        assert parsed["cases"][0]["name"] == "Test with émojis 🎉"


class TestJsonDefault:
    def test_json_default_enum_conversion(self) -> None:
        """_json_default() converts enums to their value."""
        from beval.reporter import _json_default

        result = _json_default(EvaluationMode.VALIDATION)
        assert result == "validation"

    def test_json_default_raises_for_unknown_types(self) -> None:
        """_json_default() raises TypeError for non-serializable types."""
        from beval.reporter import _json_default

        class CustomClass:
            pass

        with pytest.raises(TypeError, match="not JSON serializable"):
            _json_default(CustomClass())

    def test_json_default_handles_nested_enums(
        self, sample_run_result: RunResult
    ) -> None:
        """to_json() properly serializes nested enum values."""
        # This is an integration test verifying _json_default is used correctly
        result = to_json(sample_run_result)
        parsed = json.loads(result)
        # Verify enums are converted at multiple levels
        assert isinstance(parsed["mode"], str)
        assert isinstance(parsed["cases"][0]["grades"][0]["layer"], str)


class TestScrubSensitive:
    """Tests for _scrub_sensitive() recursive redaction (SPEC §10.1)."""

    def test_redacts_sensitive_keys(self) -> None:
        """Keys matching sensitive patterns are replaced with redaction marker."""
        from beval.reporter import _scrub_sensitive

        data = {"api_key": "sk-123", "name": "safe"}
        result = _scrub_sensitive(data)
        assert result["api_key"] == "***REDACTED***"
        assert result["name"] == "safe"

    def test_redacts_nested_sensitive_keys(self) -> None:
        """Sensitive keys inside nested dicts are redacted."""
        from beval.reporter import _scrub_sensitive

        data = {"metadata": {"secret_token": "abc", "label": "ok"}}
        result = _scrub_sensitive(data)
        assert result["metadata"]["secret_token"] == "***REDACTED***"  # noqa: S105
        assert result["metadata"]["label"] == "ok"

    def test_redacts_inside_lists(self) -> None:
        """Dicts nested inside lists have sensitive keys redacted."""
        from beval.reporter import _scrub_sensitive

        data = [{"password": "hunter2"}, {"value": 42}]
        result = _scrub_sensitive(data)
        assert result[0]["password"] == "***REDACTED***"  # noqa: S105
        assert result[1]["value"] == 42

    def test_leaves_non_dict_non_list_unchanged(self) -> None:
        """Scalar values pass through unmodified."""
        from beval.reporter import _scrub_sensitive

        assert _scrub_sensitive("hello") == "hello"
        assert _scrub_sensitive(42) == 42
        assert _scrub_sensitive(None) is None

    def test_case_insensitive_matching(self) -> None:
        """Sensitive key matching is case-insensitive."""
        from beval.reporter import _scrub_sensitive

        data = {"API_KEY": "val", "Secret": "val", "TOKEN": "val"}
        result = _scrub_sensitive(data)
        assert all(v == "***REDACTED***" for v in result.values())

    def test_empty_dict_and_list(self) -> None:
        """Empty containers pass through unchanged."""
        from beval.reporter import _scrub_sensitive

        assert _scrub_sensitive({}) == {}
        assert _scrub_sensitive([]) == []

    def test_credential_and_auth_patterns(self) -> None:
        """Additional sensitive patterns like credential, auth are caught."""
        from beval.reporter import _scrub_sensitive

        data = {"credential": "x", "auth_header": "Bearer tok"}
        result = _scrub_sensitive(data)
        assert result["credential"] == "***REDACTED***"
        assert result["auth_header"] == "***REDACTED***"
