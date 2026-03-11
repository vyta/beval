"""Runner orchestration for the beval framework.

Executes cases against a system, dispatches to graders, and collects results.
See SPEC.md §7 (Runner Contract).
"""

from __future__ import annotations

import statistics
import time
from typing import Any

from beval.dsl import CaseBuilder, CaseDefinition, get_registered_cases
from beval.graders import resolve_grade
from beval.types import (
    CaseResult,
    EvalContext,
    EvaluationMode,
    Grade,
    RunConfig,
    RunResult,
    RunSummary,
    SkipMode,
    StageResult,
    Subject,
    TrialAggregation,
    TrialResult,
)


def _expand_cases(case_defs: list[CaseDefinition]) -> list[CaseDefinition]:
    """Expand parameterised cases into independent instances. See SPEC §3.3."""
    expanded: list[CaseDefinition] = []
    for case_def in case_defs:
        if case_def.examples:
            for idx, row in enumerate(case_def.examples):
                instance = CaseDefinition(
                    id=f"{case_def.id}[{idx}]",
                    name=case_def.name,
                    category=case_def.category,
                    tags=list(case_def.tags),
                    func=case_def.func,
                    examples=None,
                    grades=case_def.grades,
                )
                # Store example row for the builder to access
                instance._example_row = row  # type: ignore[attr-defined]
                expanded.append(instance)
        else:
            expanded.append(case_def)
    return expanded


def _filter_cases(
    case_defs: list[CaseDefinition],
    *,
    case_id: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
) -> list[CaseDefinition]:
    """Filter cases by ID, category, and tags. See SPEC §7.3."""
    result = case_defs
    if case_id is not None:
        result = [c for c in result if c.id == case_id]
    if category is not None:
        result = [c for c in result if c.category == category]
    if tags:
        tag_set = set(tags)
        result = [c for c in result if tag_set.intersection(c.tags)]
    if exclude_tags:
        ex_set = set(exclude_tags)
        result = [c for c in result if not ex_set.intersection(c.tags)]
    return result


def _aggregate_grades(
    grades: list[Grade],
    config: RunConfig,
) -> float:
    """Compute overall score from grades honouring skip mode and weights.

    See SPEC §5.2 (default aggregation), §5.5 (weighted scoring), §6.2 (skip modes).
    """
    effective: list[tuple[Grade, float]] = []

    for g in grades:
        if g.skipped:
            if config.skip_mode == SkipMode.EXCLUDE:
                continue
            elif config.skip_mode == SkipMode.OPTIMISTIC:
                effective.append((g, 1.0))
            else:  # STRICT
                effective.append((g, 0.0))
        else:
            effective.append((g, g.score))

    if not effective:
        return 0.0

    if config.metric_weights:
        total_w = 0.0
        weighted_sum = 0.0
        for g, score in effective:
            w = config.metric_weights.get(g.metric, 1.0)
            weighted_sum += score * w
            total_w += w
        raw = weighted_sum / total_w if total_w else 0.0
    else:
        raw = sum(s for _, s in effective) / len(effective)

    return max(0.0, min(1.0, raw))


def _metric_scores(grades: list[Grade], config: RunConfig) -> dict[str, float]:
    """Compute per-metric average scores."""
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for g in grades:
        if g.skipped and config.skip_mode == SkipMode.EXCLUDE:
            continue
        score = g.score
        if g.skipped and config.skip_mode == SkipMode.OPTIMISTIC:
            score = 1.0
        elif g.skipped and config.skip_mode == SkipMode.STRICT:
            score = 0.0
        sums[g.metric] = sums.get(g.metric, 0.0) + score
        counts[g.metric] = counts.get(g.metric, 0) + 1
    return {m: sums[m] / counts[m] for m in sums}


class Runner:
    """Orchestrates case execution. See SPEC §7."""

    def __init__(
        self,
        *,
        mode: EvaluationMode = EvaluationMode.DEV,
        config: RunConfig | None = None,
        handler: Any | None = None,
        trials: int = 1,
        trial_aggregation: TrialAggregation = TrialAggregation.MEAN,
        use_cache: bool = False,
        score_only: bool = False,
        no_cache: bool = False,
        background_givens: dict[str, Any] | None = None,
        evaluators: dict[str, Any] | None = None,
        on_case_start: Any | None = None,
        on_case_complete: Any | None = None,
    ) -> None:
        self.mode = mode
        self.config = config or RunConfig()
        self.handler = handler
        self.trials = max(1, trials)
        self.trial_aggregation = trial_aggregation
        self.use_cache = use_cache
        self.score_only = score_only
        self.no_cache = no_cache
        self.background_givens: dict[str, Any] = background_givens or {}
        self.evaluators: dict[str, Any] = evaluators or {}
        self.on_case_start = on_case_start
        self.on_case_complete = on_case_complete

    def run(
        self,
        cases: list[CaseDefinition] | None = None,
        *,
        label: str | None = None,
        case_id: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
    ) -> RunResult:
        """Execute evaluation cases and return aggregated results."""
        case_defs = cases or get_registered_cases()

        # Expand parameterised cases (§3.3)
        case_defs = _expand_cases(case_defs)

        # Apply filters (§7.3)
        case_defs = _filter_cases(
            case_defs,
            case_id=case_id,
            category=category,
            tags=tags,
            exclude_tags=exclude_tags,
        )

        context = EvalContext(
            mode=self.mode, config=self.config, evaluators=self.evaluators
        )
        case_results: list[CaseResult] = []

        total = len(case_defs)
        for idx, case_def in enumerate(case_defs):
            if self.on_case_start:
                self.on_case_start(idx, total, case_def)
            if self.trials > 1:
                result = self._run_trials(case_def, context)
            else:
                result = self._run_case(case_def, context)
            case_results.append(result)
            if self.on_case_complete:
                self.on_case_complete(idx, total, case_def, result)

        summary = self._build_summary(case_results)

        return RunResult(
            label=label,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            mode=self.mode,
            config=self.config,
            summary=summary,
            cases=case_results,
        )

    # ------------------------------------------------------------------
    # Multi-trial support (§11)
    # ------------------------------------------------------------------

    def _run_trials(
        self, case_def: CaseDefinition, context: EvalContext
    ) -> CaseResult:
        """Execute multiple trials for a case and aggregate. See SPEC §11."""
        trial_results: list[CaseResult] = []
        for _ in range(self.trials):
            trial_results.append(self._run_case(case_def, context))

        scores = [t.overall_score for t in trial_results]
        passes = [t.passed for t in trial_results]

        if self.trial_aggregation == TrialAggregation.MEAN:
            agg_score = statistics.mean(scores)
        elif self.trial_aggregation == TrialAggregation.MEDIAN:
            agg_score = statistics.median(scores)
        elif self.trial_aggregation == TrialAggregation.WORST:
            agg_score = min(scores)
        else:
            agg_score = statistics.mean(scores)

        if self.trial_aggregation == TrialAggregation.PASS_ALL:
            agg_passed = all(passes)
        elif self.trial_aggregation == TrialAggregation.PASS_AT_K:
            k = max(1, self.config.pass_at_k)
            agg_passed = sum(1 for p in passes if p) >= k
        else:
            agg_passed = agg_score >= self.config.case_pass_threshold

        stddev = statistics.stdev(scores) if len(scores) > 1 else 0.0
        pass_count = sum(1 for p in passes if p)
        total_time = sum(t.time_seconds for t in trial_results)

        # Merge metric scores across trials
        all_metrics: dict[str, list[float]] = {}
        for t in trial_results:
            for m, s in t.metric_scores.items():
                all_metrics.setdefault(m, []).append(s)
        metric_scores = {m: statistics.mean(vals) for m, vals in all_metrics.items()}

        per_trial = [
            TrialResult(trial=i + 1, overall_score=t.overall_score, passed=t.passed)
            for i, t in enumerate(trial_results)
        ]

        # Use the last trial's grades in the result
        last = trial_results[-1]
        error = next((t.error for t in trial_results if t.error), None)

        return CaseResult(
            id=case_def.id,
            name=case_def.name,
            category=case_def.category,
            overall_score=agg_score,
            passed=agg_passed,
            time_seconds=total_time,
            metric_scores=metric_scores,
            error=error,
            grades=last.grades,
            stages=last.stages,
            trials=self.trials,
            per_trial=per_trial,
            score_stddev=stddev,
            score_min=min(scores),
            score_max=max(scores),
            pass_rate=f"{pass_count}/{self.trials}",
            high_variance=stddev > 0.15,
        )

    # ------------------------------------------------------------------
    # Single-case execution
    # ------------------------------------------------------------------

    def _run_case(self, case_def: CaseDefinition, context: EvalContext) -> CaseResult:
        """Execute a single case including multi-stage support."""
        start = time.monotonic()

        # Pre-resolved grades bypass grader matching (SPEC §3.6)
        if case_def.grades is not None:
            return self._run_preresolved(case_def, context, start)

        if case_def.func is not None:
            return self._run_func_case(case_def, context, start)

        elapsed = time.monotonic() - start
        return CaseResult(
            id=case_def.id,
            name=case_def.name,
            category=case_def.category,
            overall_score=0.0,
            passed=False,
            time_seconds=elapsed,
            metric_scores={},
            error="Case has neither a function nor pre-resolved grades",
            grades=[],
        )

    def _run_preresolved(
        self,
        case_def: CaseDefinition,
        context: EvalContext,
        start: float,
    ) -> CaseResult:
        """Handle pre-resolved grades including multi-stage from YAML. See SPEC §3.6."""
        grades = list(case_def.grades)  # type: ignore[arg-type]
        elapsed = time.monotonic() - start

        # Detect multi-stage from stage fields on grades
        stage_nums = {g.stage for g in grades if g.stage is not None}
        stages: list[StageResult] | None = None
        error: str | None = None

        if stage_nums:
            stages = []
            for sn in sorted(stage_nums):
                sg = [g for g in grades if g.stage == sn]
                s_name = sg[0].stage_name or "" if sg else ""
                non_skipped = [g for g in sg if not g.skipped]
                s_score = (
                    sum(g.score for g in non_skipped) / len(non_skipped)
                    if non_skipped
                    else 0.0
                )
                s_passed = all(g.passed for g in sg)
                stages.append(
                    StageResult(
                        stage=sn,
                        name=s_name,
                        score=s_score,
                        passed=s_passed,
                        grade_count=len(sg),
                    )
                )

        # Check for stage errors from YAML stage definitions
        if hasattr(case_def, "_stage_errors"):
            for stage_num, err_msg in case_def._stage_errors.items():  # noqa: SLF001
                error = f"Stage {stage_num} failed: {err_msg}"

        overall = _aggregate_grades(grades, self.config)
        ms = _metric_scores(grades, self.config)

        return CaseResult(
            id=case_def.id,
            name=case_def.name,
            category=case_def.category,
            overall_score=overall,
            passed=(
                overall >= self.config.case_pass_threshold
                if error is None
                else False
            ),
            time_seconds=elapsed,
            metric_scores=ms,
            error=error,
            grades=grades,
            stages=stages,
        )

    def _run_func_case(
        self,
        case_def: CaseDefinition,
        context: EvalContext,
        start: float,
    ) -> CaseResult:
        """Execute a function-based case with multi-stage support."""
        builder = CaseBuilder()

        # Inject background givens; case-level values win (§3.4)
        if self.background_givens:
            builder._givens.update(self.background_givens)

        try:
            case_def.func(builder)  # type: ignore[misc]
        except Exception as exc:  # noqa: BLE001
            elapsed = time.monotonic() - start
            return CaseResult(
                id=case_def.id,
                name=case_def.name,
                category=case_def.category,
                overall_score=0.0,
                passed=False,
                time_seconds=elapsed,
                metric_scores={},
                error=str(exc),
                grades=[],
            )

        # Multi-stage support (§3.5)
        if len(builder._whens) > 1:
            return self._run_multistage(case_def, builder, context, start)

        # Single-stage: invoke the system and grade
        subject = self._invoke_system(case_def, builder, context)
        grades = []
        for criterion, args in builder._thens:
            grade = resolve_grade(criterion, list(args), subject, context)
            grades.append(grade)

        elapsed = time.monotonic() - start
        overall = _aggregate_grades(grades, self.config)
        ms = _metric_scores(grades, self.config)

        return CaseResult(
            id=case_def.id,
            name=case_def.name,
            category=case_def.category,
            overall_score=overall,
            passed=overall >= self.config.case_pass_threshold,
            time_seconds=elapsed,
            metric_scores=ms,
            error=None,
            grades=grades,
        )

    def _run_multistage(
        self,
        case_def: CaseDefinition,
        builder: CaseBuilder,
        context: EvalContext,
        start: float,
    ) -> CaseResult:
        """Execute a multi-stage pipeline. See SPEC §3.5."""
        # Group thens by the when that precedes them
        stage_groups = self._group_stages(builder)
        all_grades: list[Grade] = []
        stage_results: list[StageResult] = []
        prior_subject: Subject | None = None
        error: str | None = None

        for stage_idx, (when_text, thens) in enumerate(stage_groups):
            stage_num = stage_idx + 1

            if error is not None:
                # Halt subsequent stages (§7.2)
                for criterion, _args in thens:
                    all_grades.append(
                        Grade(
                            criterion=criterion,
                            score=0.0,
                            metric="quality",
                            passed=False,
                            detail=f"Stage {stage_num} did not execute: {error}",
                            layer="deterministic",
                            stage=stage_num,
                            stage_name=when_text,
                        )
                    )
                stage_results.append(
                    StageResult(
                        stage=stage_num,
                        name=when_text,
                        score=0.0,
                        passed=False,
                        grade_count=len(thens),
                    )
                )
                continue

            try:
                if prior_subject is None:
                    # Stage 1: invoke the agent
                    subject = self._invoke_system(
                        case_def,
                        builder,
                        context,
                        stage=stage_num,
                        stage_name=when_text,
                        prior_subject=prior_subject,
                    )
                else:
                    # Subsequent stages: reuse prior output, just update stage metadata
                    subject = Subject(
                        input=prior_subject.input,
                        output=prior_subject.output,
                        completion_time=prior_subject.completion_time,
                        tool_calls=prior_subject.tool_calls,
                        spans=prior_subject.spans,
                        metadata=prior_subject.metadata,
                        stage=stage_num,
                        stage_name=when_text,
                        prior_subject=prior_subject,
                    )
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                for criterion, _args in thens:
                    all_grades.append(
                        Grade(
                            criterion=criterion,
                            score=0.0,
                            metric="quality",
                            passed=False,
                            detail=f"Stage {stage_num} failed: {error}",
                            layer="deterministic",
                            stage=stage_num,
                            stage_name=when_text,
                        )
                    )
                stage_results.append(
                    StageResult(
                        stage=stage_num,
                        name=when_text,
                        score=0.0,
                        passed=False,
                        grade_count=len(thens),
                    )
                )
                continue

            stage_grades: list[Grade] = []
            for criterion, args in thens:
                grade = resolve_grade(criterion, list(args), subject, context)
                # Annotate with stage info
                grade = Grade(
                    criterion=grade.criterion,
                    score=grade.score,
                    metric=grade.metric,
                    passed=grade.passed,
                    detail=grade.detail,
                    layer=grade.layer,
                    skipped=grade.skipped,
                    stage=stage_num,
                    stage_name=when_text,
                )
                stage_grades.append(grade)

            all_grades.extend(stage_grades)
            non_skipped = [g for g in stage_grades if not g.skipped]
            s_score = (
                sum(g.score for g in non_skipped) / len(non_skipped)
                if non_skipped
                else 0.0
            )
            stage_results.append(
                StageResult(
                    stage=stage_num,
                    name=when_text,
                    score=s_score,
                    passed=all(g.passed for g in stage_grades),
                    grade_count=len(stage_grades),
                )
            )
            prior_subject = subject

        elapsed = time.monotonic() - start
        overall = _aggregate_grades(all_grades, self.config)
        ms = _metric_scores(all_grades, self.config)

        return CaseResult(
            id=case_def.id,
            name=case_def.name,
            category=case_def.category,
            overall_score=overall,
            passed=(
                overall >= self.config.case_pass_threshold
                if error is None
                else False
            ),
            time_seconds=elapsed,
            metric_scores=ms,
            error=error,
            grades=all_grades,
            stages=stage_results,
            subject_output=(
                prior_subject.answer if prior_subject else None
            ),
        )

    @staticmethod
    def _group_stages(
        builder: CaseBuilder,
    ) -> list[tuple[str, list[tuple[str, tuple[Any, ...]]]]]:
        """Group then-clauses by the preceding when-clause.

        Uses explicit stage boundaries tracked by CaseBuilder when available.
        Falls back to even distribution for legacy or edge cases.
        """
        if not builder._whens:
            return []

        # Use tracked stage boundaries when available (CaseBuilder._stage_thens)
        if builder._stage_thens and len(builder._stage_thens) == len(builder._whens):
            return list(zip(builder._whens, builder._stage_thens, strict=True))

        # Fallback: distribute thens evenly across whens
        n_stages = len(builder._whens)
        n_thens = len(builder._thens)
        per_stage = n_thens // n_stages if n_stages else n_thens
        remainder = n_thens % n_stages if n_stages else 0

        groups: list[tuple[str, list[tuple[str, tuple[Any, ...]]]]] = []
        idx = 0
        for i, when_text in enumerate(builder._whens):
            count = per_stage + (1 if i < remainder else 0)
            groups.append((when_text, list(builder._thens[idx : idx + count])))
            idx += count
        return groups

    def _invoke_system(
        self,
        case_def: CaseDefinition,
        builder: CaseBuilder,
        context: EvalContext,
        *,
        stage: int | None = None,
        stage_name: str | None = None,
        prior_subject: Subject | None = None,
    ) -> Subject:
        """Invoke the system handler or build a stub Subject.

        Respects caching flags: --use-cache, --score-only, --no-cache (§9.4).
        """
        givens_input = builder._givens.get(
            "query", builder._givens.get("a query", "")
        )

        # Cache lookup when enabled
        if (self.use_cache or self.score_only) and not self.no_cache:
            from beval.cache import get_cached_subject

            cached = get_cached_subject(case_def.id, givens_input)
            if cached is not None:
                return cached
            if self.score_only:
                msg = f"No cached subject for case '{case_def.id}'"
                raise RuntimeError(msg)

        if self.handler is not None:
            subject: Subject = self.handler(
                case_def=case_def,
                givens=builder._givens,
                context=context,
                stage=stage,
                stage_name=stage_name,
                prior_subject=prior_subject,
            )
        else:
            # Stub subject for cases without a handler
            subject = Subject(
                input=givens_input,
                output="",
                completion_time=0.0,
                stage=stage,
                stage_name=stage_name,
                prior_subject=prior_subject,
            )

        # Cache the result when caching is enabled
        if not self.no_cache and (self.use_cache or self.score_only):
            from beval.cache import put_cached_subject

            put_cached_subject(case_def.id, subject)

        return subject

    def _build_summary(self, cases: list[CaseResult]) -> RunSummary:
        """Build aggregate summary from case results."""
        passed = sum(1 for c in cases if c.passed)
        errored = sum(1 for c in cases if c.error is not None)
        failed = len(cases) - passed - errored
        non_errored = [c for c in cases if c.error is None]
        overall = (
            sum(c.overall_score for c in non_errored) / len(non_errored)
            if non_errored
            else 0.0
        )
        overall = max(0.0, min(1.0, overall))

        # Aggregate metric scores
        metrics: dict[str, float] = {}
        metric_counts: dict[str, int] = {}
        for c in non_errored:
            for m, s in c.metric_scores.items():
                metrics[m] = metrics.get(m, 0.0) + s
                metric_counts[m] = metric_counts.get(m, 0) + 1
        for m in metrics:
            metrics[m] /= metric_counts[m]

        return RunSummary(
            overall_score=overall,
            passed=passed,
            failed=failed,
            errored=errored,
            total=len(cases),
            metrics=metrics,
        )
