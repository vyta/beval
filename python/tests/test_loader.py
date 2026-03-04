"""Tests for beval YAML case loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from beval.dsl import CaseBuilder
from beval.loader import (
    _parse_then_clause,
    load_case_directory,
    load_case_file,
    parse_cases,
)


class TestLoadCaseFile:
    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        content = {
            "cases": [{"name": "test case", "when": "action", "then": [{"check": 1}]}]
        }
        path = tmp_path / "test.yaml"
        path.write_text(yaml.dump(content), encoding="utf-8")

        result = load_case_file(path)
        assert result["cases"][0]["name"] == "test case"

    def test_rejects_non_mapping(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ValueError, match="Expected a mapping"):
            load_case_file(path)

    def test_uses_safe_load(self, tmp_path: Path) -> None:
        """Verify that unsafe YAML constructs are not executed."""
        malicious = "!!python/object/apply:os.system ['echo pwned']"
        path = tmp_path / "malicious.yaml"
        path.write_text(malicious, encoding="utf-8")

        with pytest.raises(yaml.YAMLError):
            load_case_file(path)


class TestLoadCaseDirectory:
    def test_loads_multiple_files(self, tmp_path: Path) -> None:
        for name in ("a.yaml", "b.yml"):
            (tmp_path / name).write_text(yaml.dump({"cases": []}), encoding="utf-8")

        results = load_case_directory(tmp_path)
        assert len(results) == 2

    def test_empty_directory(self, tmp_path: Path) -> None:
        results = load_case_directory(tmp_path)
        assert results == []


class TestParseThenClause:
    def test_single_string_arg(self) -> None:
        crit, args = _parse_then_clause({"the answer should mention": "AI"})
        assert crit == "the answer should mention"
        assert args == ("AI",)

    def test_numeric_arg(self) -> None:
        crit, args = _parse_then_clause({"completion time under": 20})
        assert crit == "completion time under"
        assert args == (20,)

    def test_list_args(self) -> None:
        crit, args = _parse_then_clause({"should call": ["search", "filter"]})
        assert crit == "should call"
        assert args == ("search", "filter")

    def test_no_arg(self) -> None:
        crit, args = _parse_then_clause({"should be comprehensive": None})
        assert crit == "should be comprehensive"
        assert args == ()


class TestParseCases:
    def test_preresolved_single_stage(self) -> None:
        data: dict[str, Any] = {
            "cases": [
                {
                    "name": "test",
                    "id": "t1",
                    "when": "action",
                    "grades": [
                        {
                            "criterion": "check",
                            "score": 0.9,
                            "metric": "quality",
                            "layer": "deterministic",
                            "passed": True,
                        }
                    ],
                }
            ]
        }
        defs = parse_cases(data)
        assert len(defs) == 1
        assert defs[0].grades is not None
        assert defs[0].grades[0].score == 0.9

    def test_then_clause_single_stage(self) -> None:
        """YAML cases with when+then produce a runnable function."""
        data: dict[str, Any] = {
            "cases": [
                {
                    "name": "Then test",
                    "id": "then_test",
                    "given": {"query": "What is AI?"},
                    "when": "the system answers",
                    "then": [
                        {"answer should mention": "artificial intelligence"},
                        {"response time under": 5},
                    ],
                }
            ]
        }
        defs = parse_cases(data)
        assert len(defs) == 1
        assert defs[0].func is not None
        assert defs[0].grades is None

        # Verify the synthetic function drives the builder correctly
        builder = CaseBuilder()
        defs[0].func(builder)
        assert builder._givens == {"query": "What is AI?"}
        assert builder._whens == ["the system answers"]
        assert len(builder._thens) == 2
        assert builder._thens[0] == (
            "answer should mention",
            ("artificial intelligence",),
        )
        assert builder._thens[1] == ("response time under", (5,))

    def test_then_clause_multi_stage(self) -> None:
        """YAML multi-stage with then-clauses builds a multi-when function."""
        data: dict[str, Any] = {
            "cases": [
                {
                    "name": "Multi stage",
                    "id": "ms_then",
                    "given": {"topic": "AI safety"},
                    "stages": [
                        {
                            "when": "agent searches",
                            "then": [{"results relevant": None}],
                        },
                        {
                            "when": "agent summarizes",
                            "then": [
                                {"summary covers topic": "AI safety"},
                                {"summary length ok": None},
                            ],
                        },
                    ],
                }
            ]
        }
        defs = parse_cases(data)
        assert len(defs) == 1
        assert defs[0].func is not None

        builder = CaseBuilder()
        defs[0].func(builder)
        assert builder._givens == {"topic": "AI safety"}
        assert builder._whens == ["agent searches", "agent summarizes"]
        assert len(builder._thens) == 3
        # Stage boundaries tracked correctly
        assert len(builder._stage_thens) == 2
        assert len(builder._stage_thens[0]) == 1
        assert len(builder._stage_thens[1]) == 2

    def test_background_givens_merged(self) -> None:
        """Background given values are merged into each case (§3.4)."""
        data: dict[str, Any] = {
            "background": {
                "category": "research",
                "given": {"api_key": "test-key", "timeout": 30},
            },
            "cases": [
                {
                    "name": "BG test",
                    "id": "bg_test",
                    "given": {"query": "hello"},
                    "when": "action",
                    "then": [{"check": None}],
                }
            ],
        }
        defs = parse_cases(data)
        assert defs[0].category == "research"

        builder = CaseBuilder()
        defs[0].func(builder)  # type: ignore[misc]
        assert builder._givens["api_key"] == "test-key"
        assert builder._givens["timeout"] == 30
        assert builder._givens["query"] == "hello"

    def test_background_case_overrides(self) -> None:
        """Case-level given values override background (§3.4)."""
        data: dict[str, Any] = {
            "background": {"given": {"query": "default"}},
            "cases": [
                {
                    "name": "Override",
                    "id": "bg_override",
                    "given": {"query": "custom"},
                    "when": "action",
                    "then": [{"check": None}],
                }
            ],
        }
        defs = parse_cases(data)
        builder = CaseBuilder()
        defs[0].func(builder)  # type: ignore[misc]
        assert builder._givens["query"] == "custom"

    def test_examples_preserved(self) -> None:
        """Examples field is carried through to CaseDefinition."""
        data: dict[str, Any] = {
            "cases": [
                {
                    "name": "Param",
                    "id": "param_test",
                    "when": "action",
                    "then": [{"check": None}],
                    "examples": [{"query": "a"}, {"query": "b"}],
                }
            ]
        }
        defs = parse_cases(data)
        assert defs[0].examples == [{"query": "a"}, {"query": "b"}]

    def test_bare_case_no_func_no_grades(self) -> None:
        """Case with neither grades nor then-clauses gets no func or grades."""
        data: dict[str, Any] = {
            "cases": [{"name": "bare", "id": "bare"}]
        }
        defs = parse_cases(data)
        assert defs[0].func is None
        assert defs[0].grades is None
