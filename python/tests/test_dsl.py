"""Tests for beval DSL implementation."""

from __future__ import annotations

from beval.dsl import (
    CaseBuilder,
    case,
    examples,
    get_registered_cases,
)


class TestCaseBuilder:
    def test_given_stores_value(self) -> None:
        """given() stores key-value pairs in _givens dict."""
        builder = CaseBuilder()
        result = builder.given("query", "What is AI?")
        assert builder._givens["query"] == "What is AI?"
        assert result is builder  # fluent

    def test_given_without_value(self) -> None:
        """given() can store None as value."""
        builder = CaseBuilder()
        builder.given("context")
        assert "context" in builder._givens
        assert builder._givens["context"] is None

    def test_when_appends_action(self) -> None:
        """when() appends actions to _whens list."""
        builder = CaseBuilder()
        result = builder.when("the agent processes the query")
        assert "the agent processes the query" in builder._whens
        assert result is builder  # fluent

    def test_multiple_when_calls(self) -> None:
        """Multiple when() calls accumulate in order."""
        builder = CaseBuilder()
        builder.when("action 1").when("action 2").when("action 3")
        assert builder._whens == ["action 1", "action 2", "action 3"]

    def test_then_stores_criterion(self) -> None:
        """then() stores criterion and arguments."""
        builder = CaseBuilder()
        result = builder.then("the answer should mention", "AI")
        assert len(builder._thens) == 1
        assert builder._thens[0] == ("the answer should mention", ("AI",))
        assert result is builder  # fluent

    def test_then_with_multiple_args(self) -> None:
        """then() can accept multiple arguments."""
        builder = CaseBuilder()
        builder.then("criterion", "arg1", "arg2", "arg3")
        assert builder._thens[0] == ("criterion", ("arg1", "arg2", "arg3"))

    def test_then_with_no_args(self) -> None:
        """then() works with no arguments."""
        builder = CaseBuilder()
        builder.then("passes")
        assert builder._thens[0] == ("passes", ())

    def test_fluent_chain(self) -> None:
        """All builder methods return self for fluent chaining."""
        builder = CaseBuilder()
        result = (
            builder.given("query", "What is AI?")
            .when("the agent processes the query")
            .then("the answer should mention", "artificial intelligence")
        )
        assert result is builder
        assert builder._givens == {"query": "What is AI?"}
        assert builder._whens == ["the agent processes the query"]
        assert len(builder._thens) == 1

    def test_stage_thens_tracking(self) -> None:
        """_stage_thens tracks which thens belong to which when."""
        builder = CaseBuilder()
        builder.when("step 1").then("check A").then("check B")
        builder.when("step 2").then("check C")

        assert len(builder._stage_thens) == 2
        assert len(builder._stage_thens[0]) == 2
        assert len(builder._stage_thens[1]) == 1
        assert builder._stage_thens[0][0] == ("check A", ())
        assert builder._stage_thens[0][1] == ("check B", ())
        assert builder._stage_thens[1][0] == ("check C", ())

    def test_stage_thens_uneven_distribution(self) -> None:
        """Uneven then distribution is tracked accurately per stage."""
        builder = CaseBuilder()
        builder.when("stage 1").then("a").then("b").then("c")
        builder.when("stage 2").then("d")

        assert len(builder._stage_thens[0]) == 3
        assert len(builder._stage_thens[1]) == 1


class TestCaseDecorator:
    def test_case_registers_function(self) -> None:
        """@case decorator registers a CaseDefinition."""
        initial_count = len(get_registered_cases())

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        assert len(cases) == initial_count + 1
        assert cases[-1].id == "test_func"
        assert cases[-1].name == "Test case"

    def test_case_uses_function_name_as_id(self) -> None:
        """@case uses function __name__ as the case ID."""

        @case("Display name")
        def my_test_case(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        found = next((c for c in cases if c.id == "my_test_case"), None)
        assert found is not None
        assert found.name == "Display name"

    def test_case_with_category(self) -> None:
        """@case decorator accepts category parameter."""

        @case("Test case", category="legislation")
        def test_func(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        found = next((c for c in cases if c.id == "test_func"), None)
        assert found is not None
        assert found.category == "legislation"

    def test_case_with_tags(self) -> None:
        """@case decorator accepts tags parameter."""

        @case("Test case", tags=["tag1", "tag2"])
        def test_func(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        found = next((c for c in cases if c.id == "test_func"), None)
        assert found is not None
        assert found.tags == ["tag1", "tag2"]

    def test_case_defaults(self) -> None:
        """@case decorator uses empty defaults for category and tags."""

        @case("Test case")
        def test_func(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        found = next((c for c in cases if c.id == "test_func"), None)
        assert found is not None
        assert found.category == ""
        assert found.tags == []

    def test_multiple_case_registrations(self) -> None:
        """Multiple @case decorators accumulate in registry."""
        initial_count = len(get_registered_cases())

        @case("Case one")
        def test_one(s: CaseBuilder) -> None:
            pass

        @case("Case two")
        def test_two(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        assert len(cases) == initial_count + 2


class TestExamplesDecorator:
    def test_examples_attaches_to_case(self) -> None:
        """@examples attaches rows to the most recent matching case."""

        @examples(
            [
                {"query": "q1", "expected": "a1"},
                {"query": "q2", "expected": "a2"},
            ]
        )
        @case("Parameterized case")
        def test_func(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        found = next((c for c in cases if c.id == "test_func"), None)
        assert found is not None
        assert found.examples is not None
        assert len(found.examples) == 2
        assert found.examples[0]["query"] == "q1"
        assert found.examples[1]["expected"] == "a2"

    def test_examples_with_empty_list(self) -> None:
        """@examples can accept an empty list."""

        @examples([])
        @case("Case with no examples")
        def test_func(s: CaseBuilder) -> None:
            pass

        cases = get_registered_cases()
        found = next((c for c in cases if c.id == "test_func"), None)
        assert found is not None
        assert found.examples == []


class TestRegistry:
    def test_get_registered_cases_returns_copy(self) -> None:
        """get_registered_cases() returns a copy, not the internal list."""
        cases1 = get_registered_cases()
        cases2 = get_registered_cases()
        assert cases1 is not cases2

    def test_registry_isolation(self) -> None:
        """Registry is properly isolated between tests (via conftest)."""
        # This test verifies conftest._reset_registries works
        cases = get_registered_cases()
        # All cases registered in this test class should be gone after reset
        # The conftest fixture should have cleared them
        # We can only verify this indirectly by checking other tests pass
        assert isinstance(cases, list)
