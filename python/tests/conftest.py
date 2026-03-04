"""Shared pytest fixtures for beval tests."""

from __future__ import annotations

import pytest

from beval.types import Grade, GraderLayer, Subject


@pytest.fixture(autouse=True)
def _reset_registries():
    """Isolate global registries between test cases."""
    from beval.dsl import _CASE_REGISTRY
    from beval.graders import _GRADER_REGISTRY

    _CASE_REGISTRY.clear()
    _GRADER_REGISTRY.clear()
    yield
    _CASE_REGISTRY.clear()
    _GRADER_REGISTRY.clear()


@pytest.fixture
def sample_subject() -> Subject:
    """A minimal Subject for testing."""
    return Subject(
        input="What is AI?",
        output="Artificial intelligence is a branch of computer science.",
        completion_time=1.5,
        metadata={
            "documents_retrieved": 3,
            "citations_count": 2,
            "sources_used": ["source1", "source2"],
        },
    )


@pytest.fixture
def sample_grade() -> Grade:
    """A minimal passing Grade for testing."""
    return Grade(
        criterion="the answer should mention",
        score=1.0,
        metric="relevance",
        passed=True,
        detail="Found match.",
        layer=GraderLayer.DETERMINISTIC,
    )
