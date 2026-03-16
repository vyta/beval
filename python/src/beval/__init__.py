"""beval — Behavioral evaluation framework for AI agents and LLM-powered systems.

See SPEC.md §3 for core concepts.
"""

from beval.adapters import AdapterInterface, load_agent
from beval.dsl import CaseBuilder, case, clear_case_registry, examples
from beval.graders import clear_grader_registry, grader, register_grader
from beval.runner import Runner
from beval.subject import normalize_subject
from beval.types import (
    CaseResult,
    EvalContext,
    EvaluationMode,
    Grade,
    GraderLayer,
    MetricCategory,
    RunConfig,
    RunResult,
    RunSummary,
    SkipMode,
    StageResult,
    Subject,
    TrialAggregation,
    TrialResult,
)

__all__ = [
    "AdapterInterface",
    "load_agent",
    "case",
    "clear_case_registry",
    "clear_grader_registry",
    "examples",
    "CaseBuilder",
    "grader",
    "register_grader",
    "Runner",
    "normalize_subject",
    "CaseResult",
    "EvalContext",
    "EvaluationMode",
    "Grade",
    "GraderLayer",
    "MetricCategory",
    "RunConfig",
    "RunResult",
    "RunSummary",
    "SkipMode",
    "StageResult",
    "Subject",
    "TrialAggregation",
    "TrialResult",
]
