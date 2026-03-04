"""DSL implementation for the beval framework.

Provides the @case decorator, CaseBuilder, and Given/When/Then fluent
interface. See SPEC.md §4 (The DSL).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from beval.types import Grade

# Global case registry
_CASE_REGISTRY: list[CaseDefinition] = []


@dataclass
class CaseDefinition:
    """Internal representation of a registered case."""

    id: str
    name: str
    category: str
    tags: list[str] = field(default_factory=list)
    func: Callable[..., None] | None = None
    examples: list[dict[str, Any]] | None = None
    grades: list[Grade] | None = None


@dataclass
class CaseBuilder:
    """Fluent builder for constructing case steps. See SPEC §4.1."""

    _givens: dict[str, Any] = field(default_factory=dict)
    _whens: list[str] = field(default_factory=list)
    _thens: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)
    _stage_thens: list[list[tuple[str, tuple[Any, ...]]]] = field(
        default_factory=list
    )

    def given(self, name: str, value: Any = None) -> CaseBuilder:
        """Set a precondition. See SPEC §4.1."""
        self._givens[name] = value
        return self

    def when(self, action: str) -> CaseBuilder:
        """Declare the system action. See SPEC §4.1."""
        self._whens.append(action)
        self._stage_thens.append([])
        return self

    def then(self, criterion: str, *args: Any) -> CaseBuilder:
        """Add a grading criterion. See SPEC §4.1."""
        self._thens.append((criterion, args))
        if self._stage_thens:
            self._stage_thens[-1].append((criterion, args))
        return self


def case(
    name: str,
    *,
    category: str = "",
    tags: list[str] | None = None,
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator to register an evaluation case. See SPEC §4.1.

    Usage::

        @case("AI legislation search", category="legislation")
        def test_ai_legislation(s):
            s.given("a query", "What has Congress done on AI?")
            s.when("the agent researches this query")
            s.then("the answer should mention", "artificial intelligence")
    """

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        case_id = func.__name__
        definition = CaseDefinition(
            id=case_id,
            name=name,
            category=category,
            tags=tags or [],
            func=func,
        )
        _CASE_REGISTRY.append(definition)
        return func

    return decorator


def examples(
    rows: list[dict[str, Any]],
) -> Callable[[Callable[..., None]], Callable[..., None]]:
    """Decorator for input parameterization. See SPEC §4.3."""

    def decorator(func: Callable[..., None]) -> Callable[..., None]:
        # Attach examples to the most recently registered case with this function
        for defn in reversed(_CASE_REGISTRY):
            if defn.func is func:
                defn.examples = rows
                break
        return func

    return decorator


def get_registered_cases() -> list[CaseDefinition]:
    """Return all registered case definitions."""
    return list(_CASE_REGISTRY)


def clear_case_registry() -> None:
    """Remove all registered cases. Useful for test isolation."""
    _CASE_REGISTRY.clear()
