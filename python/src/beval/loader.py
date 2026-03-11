"""YAML case file loading with safe_load enforcement.

Loads evaluation case definitions from YAML files and converts them to
CaseDefinition objects the Runner can consume.
See SPEC.md §4 (The DSL), §3.6 (Pre-resolved grades).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from beval.dsl import CaseBuilder, CaseDefinition
from beval.types import Grade, GraderLayer


def load_case_file(path: str | Path) -> dict[str, Any]:
    """Load a single YAML case file using safe_load.

    Only ``yaml.safe_load`` is used to prevent arbitrary code execution.
    See SPEC security requirements.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        msg = f"Expected a mapping at top level of {path}, got {type(data).__name__}"
        raise ValueError(msg)

    return data


def load_case_directory(directory: str | Path) -> list[dict[str, Any]]:
    """Load all YAML case files from a directory.

    Searches for ``*.yaml`` and ``*.yml`` files recursively.
    """
    directory = Path(directory)
    results: list[dict[str, Any]] = []

    for pattern in ("**/*.yaml", "**/*.yml"):
        for path in sorted(directory.glob(pattern)):
            results.append(load_case_file(path))

    return results


def _parse_grade(
    raw: dict[str, Any],
    *,
    stage: int | None = None,
    stage_name: str | None = None,
) -> Grade:
    """Convert a raw grade dict from YAML to a Grade object."""
    return Grade(
        criterion=raw["criterion"],
        score=float(raw["score"]),
        metric=raw.get("metric", "quality"),
        passed=bool(raw["passed"]),
        detail=raw.get("detail"),
        layer=raw.get("layer", GraderLayer.DETERMINISTIC),
        skipped=bool(raw.get("skipped", False)),
        stage=stage,
        stage_name=stage_name,
    )


def _parse_then_clause(raw: dict[str, Any]) -> tuple[str, tuple[Any, ...]]:
    """Parse a YAML ThenClause object into (criterion, args).

    Each ThenClause is a mapping with exactly one key (the criterion pattern)
    and its value as the argument. See case.schema.json §ThenClause.
    """
    criterion = next(iter(raw))
    value = raw[criterion]
    if isinstance(value, list):
        return (criterion, tuple(value))
    if value is None:
        return (criterion, ())
    return (criterion, (value,))


def _build_yaml_func(
    givens: dict[str, Any],
    when_text: str | None,
    thens: list[tuple[str, tuple[Any, ...]]],
    stages: list[dict[str, Any]] | None = None,
) -> Any:
    """Build a synthetic case function from YAML given/when/then fields.

    Returns a closure that drives a CaseBuilder the same way a @case-decorated
    function would, so the Runner's existing execution path handles it.
    """
    if stages is not None:

        def func(builder: CaseBuilder) -> None:
            for k, v in givens.items():
                builder.given(k, v)
            for stage in stages:
                builder.when(stage["when"])
                for criterion, args in stage["thens"]:
                    builder.then(criterion, *args)
    else:

        def func(builder: CaseBuilder) -> None:
            for k, v in givens.items():
                builder.given(k, v)
            if when_text:
                builder.when(when_text)
            for criterion, args in thens:
                builder.then(criterion, *args)

    return func


def parse_cases(data: dict[str, Any]) -> list[CaseDefinition]:
    """Convert a loaded YAML dict into CaseDefinition objects.

    Supports:
    - Pre-resolved grades (``grades``) for single- and multi-stage (§3.6)
    - Then-clause cases (``when`` + ``then``) for grader matching
    - Multi-stage then-clause cases (``stages`` with ``then``)
    - Background shared context (``background``) (§3.4)
    - Parameterization via ``examples`` (§3.3)
    """
    raw_cases = data.get("cases", [])
    definitions: list[CaseDefinition] = []

    # Background block (§3.4)
    bg = data.get("background", {})
    bg_givens: dict[str, Any] = bg.get("given", {}) if bg else {}
    bg_category: str = bg.get("category", "") if bg else ""

    for raw in raw_cases:
        case_id = raw.get("id", raw.get("name", "unknown"))
        name = raw.get("name", case_id)
        category = raw.get("category", bg_category) or ""
        tags = raw.get("tags", [])
        case_givens = dict(bg_givens)  # background first
        case_givens.update(raw.get("given", {}))  # case-level wins (§3.4)
        case_examples = raw.get("examples")

        # Multi-stage (§3.5)
        if "stages" in raw:
            # Check if stages use pre-resolved grades or then-clauses
            has_grades = any("grades" in s for s in raw["stages"])
            has_thens = any("then" in s for s in raw["stages"])

            if has_grades:
                # Pre-resolved multi-stage grades (§3.6)
                grades: list[Grade] = []
                stage_errors: dict[int, str] = {}

                for idx, stage_raw in enumerate(raw["stages"]):
                    stage_num = idx + 1
                    stage_name = stage_raw.get("when", "")
                    if "error" in stage_raw:
                        stage_errors[stage_num] = stage_raw["error"]
                    for g_raw in stage_raw.get("grades", []):
                        grades.append(
                            _parse_grade(g_raw, stage=stage_num, stage_name=stage_name)
                        )

                defn = CaseDefinition(
                    id=case_id,
                    name=name,
                    category=category,
                    tags=tags,
                    grades=grades,
                    examples=case_examples,
                )
                if stage_errors:
                    defn._stage_errors = stage_errors  # type: ignore[attr-defined]
                definitions.append(defn)

            elif has_thens:
                # Then-clause multi-stage — build synthetic function
                parsed_stages = []
                for stage_raw in raw["stages"]:
                    thens = [_parse_then_clause(t) for t in stage_raw.get("then", [])]
                    parsed_stages.append(
                        {"when": stage_raw.get("when", ""), "thens": thens}
                    )
                func = _build_yaml_func(case_givens, None, [], stages=parsed_stages)
                definitions.append(
                    CaseDefinition(
                        id=case_id,
                        name=name,
                        category=category,
                        tags=tags,
                        func=func,
                        examples=case_examples,
                        givens=case_givens,
                    )
                )

        # Single-stage with pre-resolved grades (§3.6)
        elif "grades" in raw:
            grades = [_parse_grade(g) for g in raw["grades"]]
            definitions.append(
                CaseDefinition(
                    id=case_id,
                    name=name,
                    category=category,
                    tags=tags,
                    grades=grades,
                    examples=case_examples,
                    givens=case_givens,
                )
            )

        # Single-stage with then-clauses (grader matching)
        elif "then" in raw:
            thens = [_parse_then_clause(t) for t in raw["then"]]
            when_text = raw.get("when")
            func = _build_yaml_func(case_givens, when_text, thens)
            definitions.append(
                CaseDefinition(
                    id=case_id,
                    name=name,
                    category=category,
                    tags=tags,
                    func=func,
                    examples=case_examples,
                    givens=case_givens,
                )
            )

        else:
            # Case without pre-resolved grades or then-clauses
            definitions.append(
                CaseDefinition(
                    id=case_id,
                    name=name,
                    category=category,
                    tags=tags,
                    examples=case_examples,
                    givens=case_givens,
                )
            )

    return definitions


def load_cases(path: str | Path) -> list[CaseDefinition]:
    """Load and parse cases from a YAML file or directory.

    Returns a list of CaseDefinition objects ready for the Runner.
    """
    path = Path(path)
    if path.is_dir():
        datas = load_case_directory(path)
    else:
        datas = [load_case_file(path)]

    definitions: list[CaseDefinition] = []
    for data in datas:
        definitions.extend(parse_cases(data))
    return definitions
