"""Core type definitions for the beval framework.

See SPEC.md §3 (Core Concepts), §6 (Scoring Model), §7.2 (Subject).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MetricCategory(str, Enum):
    """Named quality dimension for score grouping. See SPEC §6.4."""

    LATENCY = "latency"
    COVERAGE = "coverage"
    RELEVANCE = "relevance"
    GROUNDEDNESS = "groundedness"
    CORRECTNESS = "correctness"
    QUALITY = "quality"
    SAFETY = "safety"
    COST = "cost"


class GraderLayer(str, Enum):
    """Grader layer classification. See SPEC §5.1.

    Built-in layers are enumerated here. Custom layer strings are also
    accepted by Grade (see §4.4).
    """

    DETERMINISTIC = "deterministic"
    PROCESS = "process"
    AI_JUDGED = "ai_judged"


class EvaluationMode(str, Enum):
    """Evaluation mode controlling which grader layers are active. See SPEC §8."""

    DEV = "dev"
    DEV_PROCESS = "dev+process"
    VALIDATION = "validation"
    MONITORING = "monitoring"


class SkipMode(str, Enum):
    """Skip-grade aggregation mode. See SPEC §6.2."""

    EXCLUDE = "exclude"
    OPTIMISTIC = "optimistic"
    STRICT = "strict"


class TrialAggregation(str, Enum):
    """Trial score aggregation strategy. See SPEC §11.2."""

    MEAN = "mean"
    MEDIAN = "median"
    WORST = "worst"
    PASS_AT_K = "pass_at_k"  # noqa: S105
    PASS_ALL = "pass_all"  # noqa: S105


def _clamp_score(value: float) -> float:
    """Clamp a score to the 0.0..1.0 range. See SPEC §5.1."""
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class Grade:
    """Result of executing one grader against a case. See SPEC §6.2.

    The ``layer`` field accepts both :class:`GraderLayer` enum values and
    arbitrary strings for custom layers (§4.4).
    """

    criterion: str
    score: float
    metric: str
    passed: bool
    detail: str | None
    layer: str  # GraderLayer or custom layer string (§4.4)
    skipped: bool = False
    stage: int | None = None
    stage_name: str | None = None

    def __post_init__(self) -> None:
        """Enforce 0.0..1.0 score range per SPEC §5.1."""
        object.__setattr__(self, "score", _clamp_score(self.score))


@dataclass(frozen=True)
class Subject:
    """Normalized system output exposed to graders. See SPEC §2.2."""

    input: str | list[dict[str, Any]]
    output: str | list[dict[str, Any]]
    completion_time: float
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    spans: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    stage: int | None = None
    stage_name: str | None = None
    prior_subject: Subject | None = None

    @property
    def query(self) -> str:
        """Convenience alias: input as string. See SPEC §2.2."""
        if isinstance(self.input, str):
            return self.input
        for msg in reversed(self.input):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    @property
    def answer(self) -> str:
        """Convenience alias: output as string. See SPEC §2.2."""
        if isinstance(self.output, str):
            return self.output
        for msg in reversed(self.output):
            if msg.get("role") == "assistant":
                return msg.get("content", "")
        return ""


@dataclass
class CaseResult:
    """Aggregated evaluation result for a single case. See SPEC §12."""

    id: str
    name: str
    category: str
    overall_score: float
    passed: bool
    time_seconds: float
    metric_scores: dict[str, float]
    error: str | None
    grades: list[Grade]
    stages: list[StageResult] | None = None
    trials: int | None = None
    per_trial: list[TrialResult] | None = None
    score_stddev: float | None = None
    score_min: float | None = None
    score_max: float | None = None
    pass_rate: str | None = None
    high_variance: bool = False
    subject_output: str | None = None


@dataclass(frozen=True)
class StageResult:
    """Per-stage summary for multi-stage cases."""

    stage: int
    name: str
    score: float
    passed: bool
    grade_count: int


@dataclass(frozen=True)
class TrialResult:
    """Result of a single trial execution."""

    trial: int
    overall_score: float
    passed: bool


@dataclass
class RunResult:
    """Complete result of an evaluation run. See SPEC §12."""

    timestamp: str
    mode: EvaluationMode
    config: RunConfig
    summary: RunSummary
    cases: list[CaseResult]
    label: str | None = None


@dataclass(frozen=True)
class RunConfig:
    """Non-sensitive configuration snapshot for a run. See SPEC §9.2."""

    grade_pass_threshold: float = 0.5
    case_pass_threshold: float = 0.7
    skip_mode: SkipMode = SkipMode.EXCLUDE
    metric_weights: dict[str, float] = field(default_factory=dict)
    active_layers: frozenset[str] | None = None
    pass_at_k: int = 1
    agent: dict[str, str] | None = None


@dataclass
class EvalContext:
    """Runtime context passed to grader handlers. See SPEC §4.3."""

    evaluators: dict[str, Any] = field(default_factory=dict)
    mode: EvaluationMode = EvaluationMode.DEV
    config: RunConfig = field(default_factory=RunConfig)

    @property
    def llm_judge(self) -> Any | None:
        """Backward-compatible alias for evaluators["judge"]. See SPEC §4.3."""
        return self.evaluators.get("judge")


@dataclass
class RunSummary:
    """Aggregate summary across all cases in a run."""

    overall_score: float
    passed: int
    failed: int
    errored: int
    total: int
    metrics: dict[str, float]
