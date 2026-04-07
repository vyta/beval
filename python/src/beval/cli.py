"""CLI implementation for the beval framework.

Maps the cli.spec.yaml interface contract to argparse subcommands.
See SPEC.md §7 (Runner), §7.4 (Exit codes), and spec/cli.spec.yaml.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_SPEC_VERSION = "0.1.0"

# Exit codes per SPEC §7.4
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INPUT_ERROR = 2
EXIT_INFRA_ERROR = 3
EXIT_INTERNAL_ERROR = 4


def _get_version() -> str:
    """Get package version from metadata, falling back for dev installs."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("beval")
    except PackageNotFoundError:
        return "0.1.0-dev"


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser matching cli.spec.yaml."""
    parser = argparse.ArgumentParser(
        prog="beval",
        description=(
            "Behavioral evaluation framework for AI agents and LLM-powered systems."
        ),
    )

    # Global flags
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Path to eval.config.yaml configuration file.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Suppress non-essential output.",
    )
    parser.add_argument(
        "--no-color", action="store_true", default=False, help="Disable colored output."
    )
    parser.add_argument(
        "--json", action="store_true", default=False, help="Output results as JSON."
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands.")

    # --- run ---
    run_parser = subparsers.add_parser("run", help="Execute evaluation cases.")
    run_parser.add_argument(
        "--verbose", action="store_true", default=False, help="Enable verbose output."
    )
    run_parser.add_argument(
        "-m",
        "--mode",
        type=str,
        choices=["dev", "dev+process", "validation", "monitoring"],
        default="dev",
        help="Evaluation mode.",
    )
    run_parser.add_argument(
        "-l", "--label", type=str, default=None, help="Run label for traceability."
    )
    run_parser.add_argument(
        "--cases",
        type=str,
        default=None,
        help="Path to case YAML file or directory of case files.",
    )
    run_parser.add_argument(
        "--subject",
        type=str,
        default=None,
        help=(
            "Path to a JSON file containing canned system output (Subject). "
            "When provided, the runner uses this instead of invoking the live system."
        ),
    )
    run_parser.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
        help=(
            "Agent to evaluate. Accepts a path to an agent YAML file or a name "
            "defined in the configuration file's agents section. See SPEC §13."
        ),
    )
    run_parser.add_argument("--case", type=str, default=None, help="Filter by case ID.")
    run_parser.add_argument(
        "--category", type=str, default=None, help="Filter by category."
    )
    run_parser.add_argument(
        "-t",
        "--tag",
        type=str,
        nargs="*",
        default=None,
        help="Include only matching tags.",
    )
    run_parser.add_argument(
        "--exclude-tag",
        type=str,
        nargs="*",
        default=None,
        help="Exclude matching tags.",
    )
    run_parser.add_argument(
        "--trials", type=int, default=1, help="Number of trial executions per case."
    )
    run_parser.add_argument(
        "--trial-aggregation",
        type=str,
        choices=["mean", "median", "worst", "pass_at_k", "pass_all"],
        default="mean",
        help="Trial score aggregation strategy.",
    )
    run_parser.add_argument(
        "-o", "--output", type=str, default=None, help="Results output path."
    )
    run_parser.add_argument(
        "--format",
        type=str,
        choices=["json", "jsonl"],
        default="json",
        help="Results output format.",
    )
    run_parser.add_argument(
        "--use-cache",
        action="store_true",
        default=False,
        help="Use cached outputs.",
    )
    run_parser.add_argument(
        "--score-only",
        action="store_true",
        default=False,
        help="Re-score cached outputs.",
    )
    run_parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Disable caching for this run.",
    )
    run_parser.add_argument(
        "--save-baseline",
        action="store_true",
        default=False,
        help="Save results as baseline after run.",
    )
    run_parser.add_argument(
        "--compare-baseline",
        action="store_true",
        default=False,
        help="Compare results against baseline.",
    )
    run_parser.add_argument(
        "--regression-threshold",
        type=float,
        default=0.05,
        help="Fail if any metric drops more than this value from baseline.",
    )
    run_parser.add_argument(
        "--scrub",
        action="store_true",
        default=True,
        help="Scrub sensitive values from output (default).",
    )
    run_parser.add_argument(
        "--no-scrub",
        action="store_false",
        dest="scrub",
        help="Disable sensitive-value scrubbing.",
    )
    run_parser.add_argument(
        "--skip-mode",
        type=str,
        choices=["exclude", "optimistic", "strict"],
        default=None,
        help="Skip-grade aggregation mode.",
    )
    run_parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="LLM judge model identifier (overrides config/env).",
    )

    # --- validate ---
    validate_parser = subparsers.add_parser(
        "validate", help="Validate case files, configuration, and schemas."
    )
    validate_parser.add_argument(
        "--cases", type=str, default=None, help="Path to case files or directory."
    )
    validate_parser.add_argument(
        "--config",
        type=str,
        default=None,
        dest="validate_config",
        help="Path to config file.",
    )
    validate_parser.add_argument(
        "--schema", type=str, default=None, help="Path to schema file."
    )

    # --- compare ---
    compare_parser = subparsers.add_parser(
        "compare", help="Compare results across runs."
    )
    compare_parser.add_argument(
        "--results", type=str, nargs="*", default=None, help="Paths to result files."
    )
    compare_parser.add_argument(
        "-o", "--output", type=str, default=None, help="Path for comparison output."
    )
    compare_parser.add_argument(
        "--format",
        type=str,
        choices=["json", "table"],
        default="table",
        help="Output format.",
    )

    # --- baseline ---
    baseline_parser = subparsers.add_parser(
        "baseline", help="Manage baseline snapshots."
    )
    baseline_sub = baseline_parser.add_subparsers(
        dest="baseline_command", help="Baseline subcommands."
    )
    baseline_sub.add_parser("save", help="Save the most recent results as baseline.")
    baseline_sub.add_parser("show", help="Display the current baseline.")
    baseline_sub.add_parser("clear", help="Remove the saved baseline.")

    # --- cache ---
    cache_parser = subparsers.add_parser("cache", help="Manage the response cache.")
    cache_sub = cache_parser.add_subparsers(
        dest="cache_command", help="Cache subcommands."
    )
    cache_sub.add_parser("show", help="Display cache statistics.")
    cache_sub.add_parser("clear", help="Clear all cached responses.")

    # --- init ---
    init_parser = subparsers.add_parser("init", help="Initialize a new beval project.")
    init_parser.add_argument("--dir", type=str, default=".", help="Target directory.")

    # --- version ---
    subparsers.add_parser("version", help="Print version and build information.")

    # --- converse ---
    converse_parser = subparsers.add_parser(
        "converse", help="Run conversation simulation (§15)."
    )
    converse_sub = converse_parser.add_subparsers(
        dest="converse_command", help="Conversation subcommands."
    )
    converse_run = converse_sub.add_parser(
        "run", help="Execute a conversation simulation run."
    )
    converse_run.add_argument(
        "-m",
        "--mode",
        type=str,
        choices=["dev", "dev+process", "validation", "monitoring"],
        default="dev",
        help="Evaluation mode.",
    )
    converse_run.add_argument(
        "-l", "--label", type=str, default=None, help="Run label for traceability."
    )
    converse_run.add_argument(
        "-a",
        "--agent",
        type=str,
        default=None,
        help="Agent YAML file or config name (system under test).",
    )
    converse_run.add_argument(
        "--simulator-model",
        type=str,
        default=None,
        help="Shorthand: openai simulator model (overrides config/env).",
    )
    converse_run.add_argument(
        "--simulator-agent",
        type=str,
        default=None,
        help="Shorthand: ACP simulator command (overrides config/env).",
    )
    converse_run.add_argument(
        "--actor-count",
        type=int,
        default=None,
        help="Number of actors per persona/goal pair (overrides config).",
    )
    converse_run.add_argument(
        "--max-parallel",
        type=int,
        default=None,
        help="Maximum parallel actors (overrides config).",
    )
    converse_run.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Results output path.",
    )
    converse_run.add_argument(
        "--format",
        type=str,
        choices=["json", "jsonl"],
        default="json",
        help="Results output format.",
    )
    converse_run.add_argument(
        "--persona",
        type=str,
        default=None,
        help="Run only the persona with this ID.",
    )
    converse_run.add_argument(
        "--goal",
        type=str,
        default=None,
        help="Run only the goal with this ID.",
    )
    converse_run.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="LLM judge model identifier (overrides config/env).",
    )

    return parser


def _load_config_file(path: str | None) -> dict[str, Any]:
    """Load an eval.config.yaml file. Returns empty dict if path is None.

    Supports two formats:
    - Nested (config.schema.json compliant): top-level ``eval`` key
    - Flat (legacy): settings at top level
    """
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.is_file():
        msg = f"Configuration file not found: {path}"
        raise FileNotFoundError(msg)
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        msg = f"Expected a mapping in config file {path}, got {type(data).__name__}"
        raise ValueError(msg)
    # Nested format: extract eval block (config.schema.json §9.2)
    if "eval" in data and isinstance(data["eval"], dict):
        return data["eval"]
    # Flat format: backward compatibility
    return data


def _handle_env_overrides(args: argparse.Namespace) -> None:
    """Apply BEVAL_* environment variable overrides. See SPEC §9.3."""
    env_map = {
        "BEVAL_MODE": "mode",
        "BEVAL_OUTPUT_DIR": "output",
        "BEVAL_TRIALS": "trials",
        "BEVAL_CASES_DIR": "cases",
        "BEVAL_SUBJECT": "subject",
        "BEVAL_AGENT": "agent",
        "BEVAL_LLM_JUDGE_MODEL": "judge_model",
    }
    for env_var, attr in env_map.items():
        val = os.environ.get(env_var)
        if val is not None and getattr(args, attr, None) is None:
            if attr == "trials":
                setattr(args, attr, int(val))
            else:
                setattr(args, attr, val)

    # NO_COLOR support (clig.dev standard)
    if os.environ.get("NO_COLOR") is not None:
        args.no_color = True


def _cmd_version() -> int:
    """Handle the version command."""
    print(f"beval v{_get_version()} (spec v{_SPEC_VERSION})")
    return EXIT_PASS


def _cmd_run(args: argparse.Namespace) -> int:
    """Handle the run command. See SPEC §7."""
    from beval.loader import load_cases
    from beval.reporter import to_json, to_jsonl, write_json, write_jsonl
    from beval.runner import Runner
    from beval.types import (
        EvaluationMode,
        RunConfig,
        SkipMode,
        Subject,
        TrialAggregation,
    )

    # Validate required input
    if args.cases is None:
        print("Error: --cases is required", file=sys.stderr)
        return EXIT_INPUT_ERROR

    cases_path = Path(args.cases)
    if not cases_path.exists():
        print(f"Error: cases path not found: {args.cases}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Load cases from YAML
    try:
        case_defs = load_cases(args.cases)
    except (yaml.YAMLError, ValueError) as exc:
        print(f"Error: invalid case file: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if not case_defs:
        print("Error: no cases found", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Load canned subject if provided
    subject_data: dict[str, Any] | None = None
    if args.subject:
        subject_path = Path(args.subject)
        if not subject_path.is_file():
            print(f"Error: subject file not found: {args.subject}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        with open(subject_path, encoding="utf-8") as f:
            subject_data = json.load(f)

    # Build handler from subject file (for conformance / replay)
    handler = None
    adapter = None
    if subject_data is not None:

        def _subject_handler(**kwargs: Any) -> Subject:
            return Subject(
                input=subject_data.get("input", ""),
                output=subject_data.get("output", ""),
                completion_time=float(subject_data.get("completion_time", 0.0)),
                tool_calls=subject_data.get("tool_calls", []),
                spans=subject_data.get("spans", []),
                metadata=subject_data.get("metadata", {}),
            )

        handler = _subject_handler

    # Build config (CLI flags > config file > defaults)
    file_config = _load_config_file(args.config)

    # Thresholds: support nested format (config.schema.json) and flat keys (legacy)
    thresholds = file_config.get("thresholds", {})
    grade_pass_threshold = thresholds.get("grade_pass") or file_config.get(
        "grade_pass_threshold", 0.5
    )
    case_pass_threshold = thresholds.get("case_pass") or file_config.get(
        "case_pass_threshold", 0.7
    )

    # Skip mode: CLI > config file > default
    skip_mode = SkipMode.EXCLUDE
    if args.skip_mode:
        skip_mode = SkipMode(args.skip_mode)
    elif "skip_mode" in file_config:
        skip_mode = SkipMode(file_config["skip_mode"])

    # Metric weights
    metric_weights: dict[str, float] = file_config.get("metric_weights", {})

    # Resolve agent adapter (§13.5): CLI > config default > none
    agent_info: dict[str, str] | None = None
    if handler is None:
        agent_ref = getattr(args, "agent", None)
        config_agents = file_config.get("agents")

        # Fallback to config default agent if no CLI flag
        if agent_ref is None and config_agents:
            agent_ref = config_agents.get("default")

        if agent_ref is not None:
            from beval.adapters import (
                adapter_as_handler,
                create_adapter,
            )
            from beval.adapters import (
                load_agent as _load_agent,
            )

            try:
                agent_def = _load_agent(agent_ref, config_agents=config_agents)
                adapter = create_adapter(agent_def)
                handler = adapter_as_handler(adapter)
                agent_info = {
                    "name": agent_def["name"],
                    "protocol": agent_def["protocol"],
                }
            except SystemExit:
                raise
            except ImportError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return EXIT_INPUT_ERROR
            except Exception as exc:  # noqa: BLE001
                print(f"Error loading agent: {exc}", file=sys.stderr)
                return EXIT_INFRA_ERROR

    config = RunConfig(
        grade_pass_threshold=float(grade_pass_threshold),
        case_pass_threshold=float(case_pass_threshold),
        skip_mode=skip_mode,
        metric_weights=metric_weights,
        agent=agent_info,
    )

    # Mode: CLI > config file > default
    mode_str = args.mode
    if mode_str == "dev" and "mode" in file_config:
        mode_str = file_config["mode"]
    mode = EvaluationMode(mode_str)

    # Trials: CLI > config file > default
    trials = args.trials
    if trials == 1 and "trials" in file_config:
        trials = int(file_config["trials"])

    # Trial aggregation: CLI > config file > default
    trial_agg_str = args.trial_aggregation
    if trial_agg_str == "mean" and "trial_aggregation" in file_config:
        trial_agg_str = file_config["trial_aggregation"]
    trial_agg = TrialAggregation(trial_agg_str)

    # Output config from file (CLI --output still overrides)
    output_config = file_config.get("output", {})
    if not args.output and "dir" in output_config:
        args.output = output_config["dir"]
    if args.format == "json" and "format" in output_config:
        args.format = output_config["format"]

    # Console output: always show header + per-case progress (unless quiet/json)
    show_console = not args.quiet and not args.json
    verbose = args.verbose

    if show_console:
        _print_header(agent_info, len(case_defs), mode.value)

    spinner: _Spinner | None = None

    def _on_case_start(idx: int, total: int, case_def: Any) -> None:
        nonlocal spinner
        if show_console:
            _print_case_start(idx, total, case_def, verbose)
            spinner = _Spinner("Waiting for agent")
            spinner.start()

    def _on_case_complete(idx: int, total: int, case_def: Any, cr: Any) -> None:
        nonlocal spinner
        if spinner:
            spinner.stop()
            spinner = None
        if show_console:
            _print_case_result(idx, total, case_def, cr, verbose)

    # Build evaluators (judge) — precedence per §14.4:
    # 1. --judge-model CLI flag / BEVAL_LLM_JUDGE_MODEL env var (openai shorthand)
    # 2. eval.judge config block (explicit protocol)
    # 3. Legacy flat judge_model key (openai shorthand, backward compat)
    # 4. NullJudge implicitly (no judge configured)
    evaluators: dict[str, Any] = {}
    judge: Any = None
    judge_model = getattr(args, "judge_model", None)
    if judge_model is None:
        judge_model = file_config.get("judge_model")

    if judge_model:
        # Shorthand path: activates openai protocol with OPENAI_API_KEY from env
        from beval.judge import LLMJudge

        try:
            judge = LLMJudge(
                judge_model,
                grade_pass_threshold=config.grade_pass_threshold,
            )
        except ImportError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_INPUT_ERROR
    else:
        judge_config = file_config.get("judge")
        if judge_config and isinstance(judge_config, dict):
            from beval.judge import load_judge_from_config

            try:
                judge = load_judge_from_config(
                    judge_config,
                    grade_pass_threshold=config.grade_pass_threshold,
                )
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return EXIT_INPUT_ERROR
            except ImportError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return EXIT_INPUT_ERROR

    if judge is not None:
        evaluators["judge"] = judge

    runner = Runner(
        mode=mode,
        config=config,
        handler=handler,
        trials=trials,
        trial_aggregation=trial_agg,
        use_cache=getattr(args, "use_cache", False),
        score_only=getattr(args, "score_only", False),
        no_cache=getattr(args, "no_cache", False),
        evaluators=evaluators,
        on_case_start=_on_case_start,
        on_case_complete=_on_case_complete,
    )

    start_time = time.monotonic()

    # Execute (with adapter cleanup in finally)
    try:
        result = runner.run(
            case_defs,
            label=args.label,
            case_id=args.case,
            category=args.category,
            tags=args.tag,
            exclude_tags=getattr(args, "exclude_tag", None),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    finally:
        try:
            if adapter is not None:
                adapter.close()
        except Exception as close_exc:  # noqa: BLE001
            logger.warning("Error closing adapter: %s", close_exc)
        try:
            if judge is not None and hasattr(judge, "close"):
                judge.close()
        except Exception as close_exc:  # noqa: BLE001
            logger.warning("Error closing judge: %s", close_exc)

    elapsed = time.monotonic() - start_time

    # Print scorecard
    if show_console:
        _print_scorecard(result, verbose)

    # Strip subject_input/output from non-verbose results
    if not verbose:
        for cr in result.cases:
            cr.subject_input = None
            cr.subject_output = None

    # Output results
    scrub = getattr(args, "scrub", True)
    if args.output:
        output_path = Path(args.output)
        if output_path.is_dir():
            output_path = output_path / f"results.{args.format}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "jsonl":
            write_jsonl(result, str(output_path), scrub=scrub)
        else:
            write_json(result, str(output_path), scrub=scrub)
        if show_console:
            print(f"\n  Results saved to: {output_path}", file=sys.stderr)
        elif not args.quiet:
            print(f"Results written to {output_path}")
    elif args.format == "jsonl":
        print(to_jsonl(result, scrub=scrub))
    elif args.json or not sys.stdout.isatty():
        print(to_json(result, scrub=scrub))
    else:
        _print_summary(result)

    # Baseline support
    from beval.baseline import compare_baseline, load_baseline, save_baseline
    from beval.reporter import _prepare

    result_data = _prepare(result, scrub=scrub)

    if getattr(args, "save_baseline", False):
        bl_path = save_baseline(result_data)
        if not args.quiet:
            print(f"Baseline saved to {bl_path}")

    if getattr(args, "compare_baseline", False):
        bl = load_baseline()
        if bl is None:
            print("Warning: no baseline found to compare against", file=sys.stderr)
        else:
            threshold = getattr(args, "regression_threshold", 0.05)
            comparison = compare_baseline(result_data, bl, threshold=threshold)
            if comparison["regressed"]:
                if not args.quiet:
                    for r in comparison["regressions"]:
                        print(
                            f"Regression: {r['metric']} "
                            f"{r['baseline']:.3f} -> {r['current']:.3f} "
                            f"(delta: {r['delta']:+.3f})",
                            file=sys.stderr,
                        )
                return EXIT_FAIL

    # Determine exit code (§7.4): highest applicable code
    exit_code = EXIT_PASS
    for c in result.cases:
        if c.error is not None:
            exit_code = max(exit_code, EXIT_INFRA_ERROR)
        elif not c.passed:
            exit_code = max(exit_code, EXIT_FAIL)

    if show_console:
        status = (
            "Evaluation complete" if exit_code == EXIT_PASS else "Evaluation failed"
        )
        print(f"\n  {status} ({elapsed:.1f}s)\n", file=sys.stderr)

    return exit_code


class _Spinner:
    """Simple elapsed-time spinner for stderr."""

    _FRAMES = ["|", "/", "-", "\\"]

    def __init__(self, message: str) -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time = 0.0

    def start(self) -> None:
        self._start_time = time.monotonic()
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()
            self._thread = None
        # Clear the spinner line
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def _spin(self) -> None:
        idx = 0
        while not self._stop.wait(0.3):
            elapsed = time.monotonic() - self._start_time
            frame = self._FRAMES[idx % len(self._FRAMES)]
            sys.stderr.write(f"\r    {frame} {self._message} ({elapsed:.0f}s)")
            sys.stderr.flush()
            idx += 1


from beval.conversation.dashboard import _score_bar  # noqa: E402


def _truncate(text: str, max_len: int = 60) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _print_header(
    agent_info: dict[str, str] | None, total_cases: int, mode: str
) -> None:
    """Print the run header banner."""
    line = "=" * 70
    print(line, file=sys.stderr)
    if agent_info:
        name = agent_info.get("name", "unknown")
        protocol = agent_info.get("protocol", "unknown").upper()
        print(f"  {protocol} Agent ({name})", file=sys.stderr)
    else:
        print("  beval", file=sys.stderr)
    print(line, file=sys.stderr)
    print(f"  Cases: {total_cases}  |  Mode: {mode}", file=sys.stderr)
    print(file=sys.stderr)


def _print_case_start(idx: int, total: int, case_def: Any, verbose: bool) -> None:
    """Print case start line."""
    name = _truncate(case_def.name, 65)
    print(f"  [{idx + 1}/{total}] {name}", file=sys.stderr)
    givens = getattr(case_def, "givens", None) or {}
    query = givens.get("query", givens.get("a query", ""))
    if query:
        print(f"    Query: {_truncate(query, 75)}", file=sys.stderr)


def _print_case_result(
    idx: int, total: int, case_def: Any, cr: Any, verbose: bool
) -> None:
    """Print case result with grades."""
    status = "+" if cr.passed else "FAIL"
    name = _truncate(case_def.name, 40)
    print(
        f"    {status} {name} -- score: {cr.overall_score:.2f} "
        f"({cr.time_seconds:.1f}s)",
        file=sys.stderr,
    )

    if verbose:
        # Group grades by stage
        current_stage: str | None = None
        for g in cr.grades:
            stage_label = g.stage_name or ""
            if stage_label != current_stage:
                current_stage = stage_label
                if stage_label:
                    print(f"      -- {stage_label} --", file=sys.stderr)
            mark = "+" if g.passed else "x"
            if g.skipped:
                mark = "-"
            metric_tag = f"[{g.metric}]"
            detail = ""
            if g.detail:
                detail = f" -- {g.detail}"
            skipped_note = " (Skipped)" if g.skipped else ""
            print(
                f"      {mark} {g.score:.1f}  {metric_tag:<16s}"
                f"{g.criterion}{detail}{skipped_note}",
                file=sys.stderr,
            )

        # Print answer preview
        if cr.subject_output:
            print("      -- answer --", file=sys.stderr)
            preview = cr.subject_output.replace("\n", " ").strip()
            if len(preview) > 200:
                preview = preview[:200] + "..."
            print(f"      {preview}", file=sys.stderr)

    print(file=sys.stderr)


def _print_scorecard(result: Any, verbose: bool = False) -> None:
    """Print the final scorecard."""
    s = result.summary
    line = "=" * 70
    print(line, file=sys.stderr)
    print("  SCORECARD", file=sys.stderr)
    print(line, file=sys.stderr)
    print(
        f"  Overall: {s.overall_score:.2f}  ({s.passed}/{s.total} cases passed)",
        file=sys.stderr,
    )
    print(file=sys.stderr)

    # Metrics table
    if s.metrics:
        print(f"  {'Metric':<20s} {'Score':>6s}  Bar", file=sys.stderr)
        print(f"  {'-' * 20} {'-' * 6}  {'-' * 12}", file=sys.stderr)
        for metric, score in sorted(s.metrics.items()):
            bar = _score_bar(score)
            print(f"  {metric:<20s} {score:>5.2f}  {bar}", file=sys.stderr)
        print(file=sys.stderr)

    # Cases table
    print(
        f"  {'Case':<40s} {'Score':>6s}  Status",
        file=sys.stderr,
    )
    print(f"  {'-' * 40} {'-' * 6}  {'-' * 6}", file=sys.stderr)
    for cr in result.cases:
        name = _truncate(cr.name, 40)
        status = "+ PASS" if cr.passed else "x FAIL"
        if cr.error:
            status = "! ERR"
        print(f"  {name:<40s} {cr.overall_score:>5.2f}  {status}", file=sys.stderr)

        if verbose:
            # Per-case metric scores
            if cr.metric_scores:
                metrics = "  ".join(
                    f"{m}: {v:.2f}" for m, v in sorted(cr.metric_scores.items())
                )
                print(f"    Metrics: {metrics}", file=sys.stderr)
            # Query
            if cr.subject_input:
                preview = cr.subject_input.replace("\n", " ").strip()
                if len(preview) > 120:
                    preview = preview[:120] + "..."
                print(f"    Query: {preview}", file=sys.stderr)
            # Response
            if cr.subject_output:
                preview = cr.subject_output.replace("\n", " ").strip()
                if len(preview) > 120:
                    preview = preview[:120] + "..."
                print(f"    Response: {preview}", file=sys.stderr)

    # Avg time
    if result.cases:
        avg_time = sum(c.time_seconds for c in result.cases) / len(result.cases)
        print(file=sys.stderr)
        print(f"  Avg time: {avg_time:.1f}s", file=sys.stderr)

    print(line, file=sys.stderr)


def _print_summary(result: Any) -> None:
    """Print a human-readable summary to stdout."""
    s = result.summary
    print(
        f"Score: {s.overall_score:.2f}  "
        f"Passed: {s.passed}  Failed: {s.failed}  "
        f"Errored: {s.errored}  Total: {s.total}"
    )


def _cmd_validate(args: argparse.Namespace) -> int:
    """Handle the validate command. Validates case files and config."""
    from beval.schema import validate

    errors: list[str] = []

    # Validate case files
    cases_path = getattr(args, "cases", None)
    if cases_path:
        import yaml as _yaml

        p = Path(cases_path)
        files = list(p.glob("*.yaml")) + list(p.glob("*.yml")) if p.is_dir() else [p]
        for f in files:
            if not f.is_file():
                errors.append(f"File not found: {f}")
                continue
            with open(f, encoding="utf-8") as fh:
                try:
                    data = _yaml.safe_load(fh)
                except _yaml.YAMLError as exc:
                    errors.append(f"YAML parse error in {f}: {exc}")
                    continue
            case_errors = validate(data, "case.schema.json")
            for e in case_errors:
                errors.append(f"{f}: {e}")

    # Validate config file
    config_path = getattr(args, "validate_config", None)
    if config_path:
        try:
            data = _load_config_file(config_path)
            config_errors = validate(data, "config.schema.json")
            for e in config_errors:
                errors.append(f"config: {e}")
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))

    if not cases_path and not config_path:
        print("Error: provide --cases or --config to validate", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if errors:
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return EXIT_FAIL
    print("Validation passed.")
    return EXIT_PASS


def _cmd_compare(args: argparse.Namespace) -> int:
    """Handle the compare command. Compare results across runs."""
    results_paths = getattr(args, "results", None)
    if not results_paths or len(results_paths) < 2:
        print("Error: provide at least two --results paths", file=sys.stderr)
        return EXIT_INPUT_ERROR

    datasets: list[dict[str, Any]] = []
    for rp in results_paths:
        p = Path(rp)
        if not p.is_file():
            print(f"Error: results file not found: {rp}", file=sys.stderr)
            return EXIT_INPUT_ERROR
        with open(p, encoding="utf-8") as f:
            datasets.append(json.load(f))

    # Build per-metric comparison table
    all_metrics: set[str] = set()
    for ds in datasets:
        all_metrics.update(ds.get("summary", {}).get("metrics", {}).keys())

    rows: list[dict[str, Any]] = []
    for i, ds in enumerate(datasets):
        summary = ds.get("summary", {})
        row: dict[str, Any] = {
            "run": results_paths[i],
            "overall_score": summary.get("overall_score", 0.0),
        }
        for m in sorted(all_metrics):
            row[m] = summary.get("metrics", {}).get(m, None)
        rows.append(row)

    fmt = getattr(args, "format", "table")
    output_path = getattr(args, "output", None)

    if fmt == "json":
        output = json.dumps(rows, indent=2)
    else:
        # Simple table format
        cols = ["run", "overall_score", *sorted(all_metrics)]
        widths = {c: max(len(c), 8) for c in cols}
        for row in rows:
            for c in cols:
                widths[c] = max(widths[c], len(str(row.get(c, ""))))
        header = "  ".join(c.ljust(widths[c]) for c in cols)
        sep = "  ".join("-" * widths[c] for c in cols)
        lines = [header, sep]
        for row in rows:
            line = "  ".join(str(row.get(c, "")).ljust(widths[c]) for c in cols)
            lines.append(line)
        output = "\n".join(lines)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)

    return EXIT_PASS


def _cmd_baseline(args: argparse.Namespace) -> int:
    """Handle the baseline command."""
    from beval.baseline import clear_baseline, load_baseline

    sub = getattr(args, "baseline_command", None)
    if sub is None:
        print("Error: provide a subcommand: save, show, or clear", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if sub == "show":
        bl = load_baseline()
        if bl is None:
            print("No baseline saved.")
        else:
            print(json.dumps(bl, indent=2))
        return EXIT_PASS
    elif sub == "clear":
        removed = clear_baseline()
        if removed:
            print("Baseline cleared.")
        else:
            print("No baseline to clear.")
        return EXIT_PASS
    elif sub == "save":
        print(
            "Error: use 'beval run --save-baseline' to save results as baseline",
            file=sys.stderr,
        )
        return EXIT_INPUT_ERROR
    else:
        print(f"Error: unknown baseline subcommand: {sub}", file=sys.stderr)
        return EXIT_INPUT_ERROR


def _cmd_cache(args: argparse.Namespace) -> int:
    """Handle the cache command."""
    from beval.cache import cache_clear, cache_stats

    sub = getattr(args, "cache_command", None)
    if sub is None:
        print("Error: provide a subcommand: show or clear", file=sys.stderr)
        return EXIT_INPUT_ERROR

    if sub == "show":
        stats = cache_stats()
        print(f"Cache directory: {stats['directory']}")
        print(f"Entries: {stats['entries']}")
        size_kb = stats["size_bytes"] / 1024
        print(f"Size: {size_kb:.1f} KB")
        return EXIT_PASS
    elif sub == "clear":
        count = cache_clear()
        print(f"Cleared {count} cache entries.")
        return EXIT_PASS
    else:
        print(f"Error: unknown cache subcommand: {sub}", file=sys.stderr)
        return EXIT_INPUT_ERROR


def _cmd_init(args: argparse.Namespace) -> int:
    """Handle the init command. Scaffold a new beval project."""
    target = Path(getattr(args, "dir", "."))
    target.mkdir(parents=True, exist_ok=True)

    # Create eval.config.yaml
    config_path = target / "eval.config.yaml"
    if not config_path.exists():
        config_path.write_text(
            "# beval configuration\n"
            "# See SPEC.md §9 for configuration options.\n"
            "mode: dev\n"
            "grade_pass_threshold: 0.5\n"
            "case_pass_threshold: 0.7\n",
            encoding="utf-8",
        )

    # Create cases directory with example
    cases_dir = target / "cases"
    cases_dir.mkdir(exist_ok=True)
    example_path = cases_dir / "example.yaml"
    if not example_path.exists():
        example_path.write_text(
            "# Example evaluation case\n"
            "# See SPEC.md §3 for DSL syntax.\n"
            "cases:\n"
            "  - id: example_case\n"
            "    name: Example evaluation case\n"
            "    category: general\n"
            "    given:\n"
            '      query: "What is behavioral evaluation?"\n'
            "    grades:\n"
            "      - criterion: answer is relevant\n"
            "        score: 1.0\n"
            "        metric: relevance\n"
            "        layer: deterministic\n"
            "        passed: true\n"
            '        detail: "example grade"\n'
            "        skipped: false\n",
            encoding="utf-8",
        )

    print(f"Initialized beval project in {target.resolve()}")
    return EXIT_PASS


def _cmd_converse(args: argparse.Namespace) -> int:
    """Handle the converse command (§15)."""
    sub = getattr(args, "converse_command", None)
    if sub is None:
        print("Error: provide a subcommand: run", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if sub == "run":
        return _cmd_converse_run(args)
    print(f"Error: unknown converse subcommand: {sub}", file=sys.stderr)
    return EXIT_INPUT_ERROR


def _cmd_converse_run(args: argparse.Namespace) -> int:
    """Handle beval converse run (§15.14)."""
    import dataclasses
    import json as _json

    from beval.adapters import load_agent
    from beval.conversation.runner import ConversationRunner
    from beval.types import EvaluationMode, RunConfig

    # Suppress log noise when dashboard is active (TTY); keep WARNING otherwise
    use_dashboard = sys.stderr.isatty() and not getattr(args, "quiet", False)
    log_level = logging.ERROR if use_dashboard else logging.WARNING
    if not logging.root.handlers:
        logging.basicConfig(level=log_level, stream=sys.stderr,
                            format="  [%(levelname)s] %(message)s")
    else:
        logging.root.setLevel(log_level)

    # Load config file
    file_config = _load_config_file(getattr(args, "config", None))
    conv_config: dict[str, Any] = file_config.get("conversation", {})

    # ── Resolve agent (system under test) ────────────────────────────────
    agent_ref = getattr(args, "agent", None)
    config_agents = file_config.get("agents")
    if agent_ref is None and config_agents:
        agent_ref = config_agents.get("default")
    if agent_ref is None:
        print("Error: --agent is required (or set agents.default in config)", file=sys.stderr)  # noqa: E501
        return EXIT_INPUT_ERROR

    try:
        agent_def = load_agent(agent_ref, config_agents=config_agents)
    except SystemExit:
        print(f"Error: could not load agent: {agent_ref}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"Error loading agent: {exc}", file=sys.stderr)
        return EXIT_INFRA_ERROR

    # ── Resolve simulator (§15.6.6) ──────────────────────────────────────
    sim_model = getattr(args, "simulator_model", None) or os.environ.get(
        "BEVAL_SIMULATOR_MODEL"
    )
    sim_agent = getattr(args, "simulator_agent", None) or os.environ.get(
        "BEVAL_SIMULATOR_AGENT"
    )

    if sim_model and sim_agent:
        print(
            "Error: --simulator-model and --simulator-agent are mutually exclusive",
            file=sys.stderr,
        )
        return EXIT_INPUT_ERROR

    if sim_model:
        simulator_config: dict[str, Any] = {"protocol": "openai", "model": sim_model}
    elif sim_agent:
        simulator_config = {
            "protocol": "acp",
            "connection": {"transport": "stdio", "command": sim_agent.split()},
        }
    else:
        raw_sim = (conv_config.get("simulator") or {})
        if not raw_sim:
            print(
                "Error: no simulator configured. Use --simulator-model, "
                "--simulator-agent, BEVAL_SIMULATOR_MODEL, BEVAL_SIMULATOR_AGENT, "
                "or eval.conversation.simulator in config.",
                file=sys.stderr,
            )
            return EXIT_INPUT_ERROR
        simulator_config = raw_sim

    # ── Override conv_config with CLI flags ───────────────────────────────
    if getattr(args, "actor_count", None) is not None:
        conv_config = dict(conv_config)
        conv_config["actor_count"] = args.actor_count
    if getattr(args, "max_parallel", None) is not None:
        conv_config = dict(conv_config)
        conv_config["max_parallel_actors"] = args.max_parallel

    # ── Build RunConfig ───────────────────────────────────────────────────
    thresholds = file_config.get("thresholds", {})
    pass_score = float(thresholds.get("pass_score", 0.7))
    config = RunConfig(
        grade_pass_threshold=pass_score,
        case_pass_threshold=pass_score,
        pass_score=pass_score,
        case_pass_rate=float(thresholds.get("case_pass_rate", 0.9)),
        turn_pass_rate=float(thresholds.get("turn_pass_rate", 0.9)),
        conversation_pass_rate=float(thresholds.get("conversation_pass_rate", 0.9)),
        run_pass_rate=float(thresholds.get("run_pass_rate", 1.0)),
        min_satisfaction=float(thresholds["min_satisfaction"]) if "min_satisfaction" in thresholds else None,
    )

    # ── Evaluation mode ───────────────────────────────────────────────────
    mode_str = getattr(args, "mode", "dev")
    if mode_str == "dev" and "mode" in file_config:
        mode_str = file_config["mode"]
    mode = EvaluationMode(mode_str)

    # ── Judge (optional) ──────────────────────────────────────────────────
    evaluators: dict[str, Any] = {}
    judge_model = getattr(args, "judge_model", None)
    if judge_model is None:
        judge_model = file_config.get("judge_model")
    if judge_model:
        try:
            from beval.judge import LLMJudge

            evaluators["judge"] = LLMJudge(
                judge_model, grade_pass_threshold=config.grade_pass_threshold
            )
        except ImportError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_INPUT_ERROR
    else:
        judge_config = file_config.get("judge")
        if judge_config and isinstance(judge_config, dict):
            try:
                from beval.judge import load_judge_from_config

                evaluators["judge"] = load_judge_from_config(
                    judge_config, grade_pass_threshold=config.grade_pass_threshold
                )
            except (ValueError, ImportError) as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return EXIT_INPUT_ERROR

    # ── Run ───────────────────────────────────────────────────────────────
    config_file = getattr(args, "config", None)
    config_dir = Path(config_file).resolve().parent if config_file else None
    runner = ConversationRunner(
        agent_def=agent_def,
        simulator_config=simulator_config,
        conv_config=conv_config,
        mode=mode,
        config=config,
        evaluators=evaluators,
        config_dir=config_dir,
    )

    label = getattr(args, "label", None)
    output_path = getattr(args, "output", None)

    # ── Transcript dir ────────────────────────────────────────────────────
    transcript_dir: Path | None = None
    if output_path:
        _op = Path(output_path)
        # Treat as directory if no file extension (e.g. "results/") or already a dir
        base = _op if not _op.suffix else _op.parent
        transcript_dir = base / "transcripts"
        transcript_dir.mkdir(parents=True, exist_ok=True)

    # ── Conversation list (always computed for count + dashboard) ──────────
    from beval.conversation.runner import _build_conversations, load_personas_and_goals
    _personas, _goal_pool = load_personas_and_goals(conv_config, config_dir)
    _actor_count = int(conv_config.get("actor_count", 1))
    _convs = _build_conversations(
        _personas, _goal_pool, _actor_count,
        persona_filter=getattr(args, "persona", None),
        goal_filter=getattr(args, "goal", None),
    )
    n_convs = len(_convs)

    # ── Dashboard ─────────────────────────────────────────────────────────
    dashboard = None
    if use_dashboard:
        from beval.conversation.dashboard import _LiveDashboard
        _max_turns = int(conv_config.get("max_turns", 20))
        counts: dict[tuple[str, str], int] = {}
        for _p, _g, _ in _convs:
            key = (_p.id, _g.id)
            counts[key] = counts.get(key, 0) + 1
        _rows = [(pid, gid, cnt, _max_turns) for (pid, gid), cnt in counts.items()]
        dashboard = _LiveDashboard(_rows)
    print(f"\n  Starting {n_convs} conversation(s)..."
          + (f"  transcripts → {transcript_dir}" if transcript_dir else ""),
          file=sys.stderr, flush=True)

    # ── Feedback path ──────────────────────────────────────────────────────
    feedback_path: Path | None = None
    if output_path:
        _op2 = Path(output_path)
        fb_base = _op2 if not _op2.suffix else _op2.parent
        feedback_path = fb_base / "feedback.json"

    try:
        result = runner.run(
            label=label,
            persona_filter=getattr(args, "persona", None),
            goal_filter=getattr(args, "goal", None),
            dashboard=dashboard,
            transcript_dir=transcript_dir,
            feedback_path=feedback_path,
        )
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR
    finally:
        if dashboard:
            dashboard.finish()

    # ── Output ────────────────────────────────────────────────────────────
    def _to_dict(obj: Any) -> Any:
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, (list, tuple)):
            return [_to_dict(i) for i in obj]
        return obj

    result_dict = _to_dict(result)
    if output_path:
        p = Path(output_path)
        if p.is_dir():
            p = p / "conversation_results.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            _json.dump(result_dict, f, indent=2)
        if not args.quiet:
            print(f"\n  Results saved to: {p}", file=sys.stderr)
            if feedback_path and feedback_path.exists():
                print(f"  Feedback saved to: {feedback_path}", file=sys.stderr)
    else:
        print(_json.dumps(result_dict, indent=2))

    # Console summary
    s = result.summary
    if not args.quiet:
        # Determine overall pass/fail (same logic as exit code below)
        if s.total > 0:
            rate = s.passed / s.total
            run_passed = rate >= config.run_pass_rate
            if (
                run_passed
                and config.min_satisfaction is not None
                and s.avg_satisfaction is not None
                and s.avg_satisfaction < config.min_satisfaction
            ):
                run_passed = False
        else:
            run_passed = True
        verdict = "PASS" if run_passed else "FAIL"

        sat_str = f"  Sat: {s.avg_satisfaction:.2f}" if s.avg_satisfaction is not None else ""
        print(
            f"\n  {verdict}  Score: {s.overall_score:.2f}  "
            f"Goal rate: {s.goal_achievement_rate:.0%}  "
            f"Passed: {s.passed}/{s.total}  "
            f"Turns: {s.total_turns}"
            f"{sat_str}",
            file=sys.stderr,
        )

        # Failure details
        failed_convs = [c for c in result.conversations if not c.passed]
        if failed_convs:
            print(f"\n  Failed conversations ({len(failed_convs)}):", file=sys.stderr)
            for conv in failed_convs:
                print(f"\n    {conv.id}  (score={conv.overall_score:.2f}, {conv.termination_reason})", file=sys.stderr)
                # Turn-level failures
                failed_turns = [t for t in conv.turns if t.grades and not t.passed]
                if failed_turns:
                    for t in failed_turns:
                        failing_grades = [g for g in t.grades if not g.passed]
                        for g in failing_grades:
                            crit = g.criterion[:72]
                            print(f"      turn {t.turn_number}: {g.score:.2f} — {crit}", file=sys.stderr)
                # Conversation-level failures
                failing_conv_grades = [g for g in conv.grades if not g.passed]
                for g in failing_conv_grades:
                    crit = g.criterion[:72]
                    print(f"      conv:     {g.score:.2f} — {crit}", file=sys.stderr)

    # Exit code: pass if run pass rate threshold is met
    if result.summary.total > 0:
        rate = result.summary.passed / result.summary.total
        if rate < config.run_pass_rate:
            return EXIT_FAIL
        if (
            config.min_satisfaction is not None
            and result.summary.avg_satisfaction is not None
            and result.summary.avg_satisfaction < config.min_satisfaction
        ):
            if not args.quiet:
                print(
                    f"  FAIL: avg satisfaction {result.summary.avg_satisfaction:.2f}"
                    f" < min_satisfaction {config.min_satisfaction:.2f}",
                    file=sys.stderr,
                )
            return EXIT_FAIL
        return EXIT_PASS
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for beval."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    _handle_env_overrides(args)

    handlers = {
        "run": _cmd_run,
        "validate": _cmd_validate,
        "compare": _cmd_compare,
        "baseline": _cmd_baseline,
        "cache": _cmd_cache,
        "init": _cmd_init,
        "version": lambda _: _cmd_version(),
        "converse": _cmd_converse,
    }

    if args.command is None:
        parser.print_help()
        return EXIT_INPUT_ERROR

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return EXIT_INPUT_ERROR

    try:
        return handler(args)  # type: ignore[no-untyped-call]
    except NotImplementedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"Internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
