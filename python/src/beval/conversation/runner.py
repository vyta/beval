"""Conversation simulation runner (§15.7, §15.8).

See spec/conversation-sim.spec.md for the normative specification.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import logging
import statistics
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml


# ── ACP SDK noise suppression ─────────────────────────────────────────────────

class _SuppressACPTaskDestroyed(logging.Filter):
    """Drop 'Task was destroyed but it is pending!' from the asyncio logger.

    These come from the ACP SDK's TaskSupervisor respawning background tasks
    (Sender.loop, Connection.receive, Dispatcher.loop) after cancellation.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        return "Task was destroyed" not in record.getMessage()


_acp_filters_installed = False


def _install_acp_noise_filters() -> None:
    """Install once-per-process filters to suppress ACP SDK cleanup noise."""
    global _acp_filters_installed
    if _acp_filters_installed:
        return
    _acp_filters_installed = True

    # 1. Suppress "Task was destroyed" from asyncio logger
    logging.getLogger("asyncio").addFilter(_SuppressACPTaskDestroyed())

    # 2. Suppress "Exception ignored in: <coroutine>" for ACP SDK coroutines
    _orig_hook = sys.unraisablehook

    def _filtered_hook(args: sys.UnraisableHookArgs) -> None:
        obj = args.object
        if obj is not None:
            qualname = getattr(obj, "__qualname__", "") or ""
            # Suppress ACP SDK coroutine finalizer noise and the stdlib
            # Queue.get/Queue.__anext__ wakeup failures that accompany it
            if any(name in qualname for name in (
                "MessageSender", "DefaultMessageDispatcher",
                "Connection._receive", "_QueueIterator",
                "Queue.get",  # stdlib asyncio queue woken up after loop close
            )):
                return
        _orig_hook(args)

    sys.unraisablehook = _filtered_hook

if TYPE_CHECKING:
    from beval.conversation.dashboard import _LiveDashboard

from beval.adapters import create_adapter
from beval.conversation.actor import run_actor
from beval.conversation.simulator import (
    UserSimulatorInterface,
    load_simulator_from_config,
)
from beval.conversation.types import (
    ConversationResult,
    ConversationRunResult,
    ConversationRunSummary,
    Goal,
    GoalGiven,
    GoalStage,
    Persona,
    PersonaTraits,
)
from beval.types import EvalContext, EvaluationMode, RunConfig

logger = logging.getLogger(__name__)


def load_personas_and_goals(
    conv_config: dict[str, Any],
    config_dir: Path | None = None,
) -> tuple[list[Persona], dict[str, Goal]]:
    """Load personas and goals from config sources (§15.3.2, §15.4.2).

    Returns (personas, goal_pool) where goal_pool is keyed by goal ID.
    Raises SystemExit(2) on invalid configuration.
    """
    base_dir = config_dir or Path.cwd()
    goal_pool: dict[str, Goal] = {}
    persona_list: list[Persona] = []

    # Load goals first so persona goal-ID references can be validated
    for source in conv_config.get("goals", []):
        if "file" in source:
            path = Path(source["file"])
            if not path.is_absolute():
                path = base_dir / path
            if not path.is_file():
                logger.error("Goal file not found: %s", path)
                raise SystemExit(2)
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            raw_goals = data.get("goals", [])
        else:
            raw_goals = [source]

        for g in raw_goals:
            goal_id = g["id"]
            if goal_id in goal_pool:
                logger.warning("Duplicate goal id '%s'; last definition wins.", goal_id)
            raw_given = g.get("given") or {}
            given = GoalGiven(
                objective=raw_given.get("objective", ""),
                max_turns=int(raw_given.get("max_turns", 20)),
                timeout_seconds=float(raw_given.get("timeout_seconds", 600)),
            )
            stages = []
            for s in g.get("stages") or []:
                when = s.get("when", "")
                if when.lower() not in ("each turn", "on finish"):
                    logger.error("Unknown goal stage 'when' value: %r", when)
                    raise SystemExit(2)
                stages.append(GoalStage(when=when, then=list(s.get("then") or [])))
            goal_pool[goal_id] = Goal(
                id=goal_id,
                name=g["name"],
                tags=list(g.get("tags") or []),
                given=given,
                stages=stages,
            )

    # Load personas
    for source in conv_config.get("personas", []):
        if "file" in source:
            path = Path(source["file"])
            if not path.is_absolute():
                path = base_dir / path
            if not path.is_file():
                logger.error("Persona file not found: %s", path)
                raise SystemExit(2)
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            raw_personas = data.get("personas", [])
        else:
            raw_personas = [source]

        for p in raw_personas:
            goal_ids = list(p.get("goals") or [])
            if not goal_ids:
                logger.error("Persona '%s' has no goals.", p.get("id"))
                raise SystemExit(2)
            raw_traits = p.get("traits") or {}
            traits = (
                PersonaTraits(
                    tone=raw_traits.get("tone"),
                    expertise=raw_traits.get("expertise"),
                    patience=raw_traits.get("patience"),
                    verbosity=raw_traits.get("verbosity"),
                    language=raw_traits.get("language", "en"),
                    style_notes=raw_traits.get("style_notes"),
                )
                if raw_traits
                else None
            )
            persona_list.append(
                Persona(
                    id=p["id"],
                    name=p["name"],
                    description=p["description"],
                    goals=goal_ids,
                    traits=traits,
                    metadata=p.get("metadata"),
                )
            )

    # Validate persona goal references
    for persona in persona_list:
        for goal_id in persona.goals:
            if goal_id not in goal_pool:
                logger.error(
                    "Persona '%s' references unknown goal '%s'", persona.id, goal_id
                )
                raise SystemExit(2)

    return persona_list, goal_pool


def _build_conversations(
    personas: list[Persona],
    goal_pool: dict[str, Goal],
    actor_count: int,
    persona_filter: str | None = None,
    goal_filter: str | None = None,
) -> list[tuple[Persona, Goal, int]]:
    """Build the (persona, goal, actor_index) list using persona-centric pairing (§15.1)."""  # noqa: E501
    conversations = []
    for persona in personas:
        if persona_filter and persona.id != persona_filter:
            continue
        for goal_id in persona.goals:
            if goal_filter and goal_id != goal_filter:
                continue
            goal = goal_pool[goal_id]
            for actor_index in range(1, actor_count + 1):
                conversations.append((persona, goal, actor_index))
    return conversations


def _make_cancelled_result(persona: Persona, goal: Goal, actor_index: int) -> ConversationResult:  # noqa: E501
    actor_id = f"{persona.id}:{goal.id}:{actor_index}"
    return ConversationResult(
        id=actor_id,
        name=f"{persona.name} → {goal.name} (actor {actor_index})",
        category=f"{persona.id}/{goal.id}",
        persona_id=persona.id,
        goal_id=goal.id,
        actor_index=actor_index,
        overall_score=0.0,
        goal_achievement_score=0.0,
        passed=False,
        goal_achieved=False,
        termination_reason="cancelled",
        turn_count=0,
        time_seconds=0.0,
        metric_scores={},
        error="Run timeout exceeded",
        turns=[],
        grades=[],
    )


def _to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses and collections to JSON-serializable dicts."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dict(i) for i in obj]
    return obj


async def _run_all_actors(
    conversations: list[tuple[Persona, Goal, int]],
    agent_def: dict[str, Any],
    simulator_config: dict[str, Any],
    context: EvalContext,
    max_parallel_actors: int,
    run_timeout_seconds: float | None,
    dashboard: "_LiveDashboard | None" = None,
    transcript_dir: Path | None = None,
) -> list[ConversationResult]:
    """Run all actors concurrently with semaphore throttling (§15.7.2)."""
    sem = asyncio.Semaphore(max_parallel_actors)

    async def bounded(
        persona: Persona, goal: Goal, actor_index: int
    ) -> ConversationResult:
        async with sem:
            actor_id = f"{persona.id}:{goal.id}:{actor_index}"

            if dashboard:
                dashboard.on_actor_start(persona.id, goal.id)
            else:
                print(f"  → {actor_id}", file=sys.stderr, flush=True)

            adapter = create_adapter(agent_def)
            simulator: UserSimulatorInterface = load_simulator_from_config(
                simulator_config
            )

            safe_id = actor_id.replace(":", "_")
            transcript_path = (
                transcript_dir / f"{safe_id}.json" if transcript_dir is not None else None
            )
            turns_so_far: list[Any] = []

            def _write_transcript(data: Any) -> None:
                if transcript_path is None:
                    return
                try:
                    with open(transcript_path, "w", encoding="utf-8") as f:
                        json.dump(_to_dict(data), f, indent=2)
                except OSError as exc:
                    logger.warning(
                        "Could not write transcript for %s: %s", actor_id, exc
                    )

            # Write stub immediately so the file exists as soon as actor starts
            _write_transcript({
                "id": actor_id,
                "persona_id": persona.id,
                "goal_id": goal.id,
                "actor_index": actor_index,
                "status": "in_progress",
                "turns": [],
            })

            def on_turn(aid: str, turn: int, query: str) -> None:
                if dashboard:
                    dashboard.on_turn_start(persona.id, goal.id, turn)
                else:
                    preview = query[:70].replace("\n", " ")
                    print(f"    [{aid}] turn {turn}: {preview}", file=sys.stderr, flush=True)
                # Write user message immediately — before agent responds
                _write_transcript({
                    "id": actor_id,
                    "persona_id": persona.id,
                    "goal_id": goal.id,
                    "actor_index": actor_index,
                    "status": "in_progress",
                    "turns": turns_so_far + [{
                        "turn_number": turn,
                        "user_message": query,
                        "agent_response": None,
                    }],
                })

            def on_turn_complete(aid: str, turn_result: Any) -> None:
                turns_so_far.append(turn_result)
                if dashboard:
                    dashboard.on_turn_complete(
                        persona.id, goal.id, turn_result.goal_progress
                    )
                _write_transcript({
                    "id": actor_id,
                    "persona_id": persona.id,
                    "goal_id": goal.id,
                    "actor_index": actor_index,
                    "status": "in_progress",
                    "turns": turns_so_far,
                })

            try:
                result = await run_actor(
                    persona, goal, actor_index, adapter, simulator, context,
                    on_turn=on_turn,
                    on_turn_complete=on_turn_complete,
                )

                if dashboard:
                    dashboard.on_actor_complete(persona.id, goal.id, result)
                else:
                    status = "✓" if result.goal_achieved else "✗"
                    print(
                        f"  {status} {actor_id}: score={result.overall_score:.2f}"
                        f"  turns={result.turn_count}"
                        f"  [{result.termination_reason}]",
                        file=sys.stderr,
                        flush=True,
                    )

                # Overwrite with the complete ConversationResult
                _write_transcript(result)

                return result
            finally:
                try:
                    adapter.close()
                except Exception:  # noqa: BLE001, S110
                    pass
                try:
                    await simulator.close()
                except Exception:  # noqa: BLE001, S110
                    pass

    tasks = [
        asyncio.create_task(bounded(persona, goal, actor_index))
        for persona, goal, actor_index in conversations
    ]
    done, pending = await asyncio.wait(tasks, timeout=run_timeout_seconds)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    results: list[ConversationResult] = []
    for (persona, goal, actor_index), task in zip(conversations, tasks, strict=False):
        if task in pending:
            results.append(_make_cancelled_result(persona, goal, actor_index))
        elif task.cancelled() or task.exception() is not None:
            exc = task.exception() if not task.cancelled() else None
            logger.warning("Actor %s:%s:%d failed: %s", persona.id, goal.id, actor_index, exc)  # noqa: E501
            results.append(_make_cancelled_result(persona, goal, actor_index))
        else:
            results.append(task.result())

    # Cancel lingering ACP SDK background tasks (Sender.loop, Connection.receive,
    # Dispatcher.loop). Loop up to 5 rounds since TaskSupervisor may respawn tasks.
    loop = asyncio.get_running_loop()
    loop.set_exception_handler(lambda _l, _ctx: None)  # silence cleanup warnings
    for _ in range(5):
        lingering = {t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()}
        if not lingering:
            break
        for t in lingering:
            t.cancel()
        await asyncio.gather(*lingering, return_exceptions=True)

    return results


def _build_summary(
    results: list[ConversationResult],
    config: RunConfig,
) -> ConversationRunSummary:
    """Compute ConversationRunSummary from results (§15.10.4)."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    errored = sum(
        1
        for r in results
        if r.termination_reason in ("agent_error", "simulator_error")
    )
    cancelled = sum(1 for r in results if r.termination_reason == "cancelled")
    failed = total - passed - errored - cancelled
    goal_achieved_count = sum(1 for r in results if r.goal_achieved)
    total_turns = sum(r.turn_count for r in results)

    overall_score = statistics.mean(r.overall_score for r in results) if results else 0.0  # noqa: E501
    goal_achievement_rate = goal_achieved_count / total if total > 0 else 0.0

    goal_achieved_turns = [r.turn_count for r in results if r.goal_achieved]
    mean_turns_to_goal = (
        statistics.mean(goal_achieved_turns) if goal_achieved_turns else None
    )

    metric_sums: dict[str, float] = {}
    metric_counts: dict[str, int] = {}
    for r in results:
        for m, s in r.metric_scores.items():
            metric_sums[m] = metric_sums.get(m, 0.0) + s
            metric_counts[m] = metric_counts.get(m, 0) + 1
    metrics = {m: metric_sums[m] / metric_counts[m] for m in metric_sums}

    return ConversationRunSummary(
        overall_score=overall_score,
        goal_achievement_rate=goal_achievement_rate,
        passed=passed,
        failed=failed,
        errored=errored,
        cancelled=cancelled,
        total=total,
        total_turns=total_turns,
        mean_turns_to_goal=mean_turns_to_goal,
        metrics=metrics,
    )


class ConversationRunner:
    """Orchestrates a full conversation simulation run (§15.7)."""

    def __init__(
        self,
        *,
        agent_def: dict[str, Any],
        simulator_config: dict[str, Any],
        conv_config: dict[str, Any],
        mode: EvaluationMode = EvaluationMode.DEV,
        config: RunConfig | None = None,
        evaluators: dict[str, Any] | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self._agent_def = agent_def
        self._simulator_config = simulator_config
        self._conv_config = conv_config
        self._mode = mode
        self._config = config or RunConfig()
        self._evaluators = evaluators or {}
        self._config_dir = config_dir

    def run(
        self,
        *,
        label: str | None = None,
        persona_filter: str | None = None,
        goal_filter: str | None = None,
        dashboard: "_LiveDashboard | None" = None,
        transcript_dir: Path | None = None,
    ) -> ConversationRunResult:
        """Load personas/goals, run all actors, return ConversationRunResult."""
        personas, goal_pool = load_personas_and_goals(self._conv_config, self._config_dir)

        actor_count = int(self._conv_config.get("actor_count", 1))
        max_parallel = int(self._conv_config.get("max_parallel_actors", 1))
        run_timeout = self._conv_config.get("run_timeout_seconds")
        if run_timeout is not None:
            run_timeout = float(run_timeout)

        conversations = _build_conversations(
            personas, goal_pool, actor_count, persona_filter, goal_filter
        )
        if not conversations:
            logger.error("No conversations to run — check personas and goals configuration.")  # noqa: E501
            raise SystemExit(2)

        context = EvalContext(
            evaluators=self._evaluators,
            mode=self._mode,
            config=self._config,
        )

        async def _run() -> list[ConversationResult]:
            try:
                return await _run_all_actors(
                    conversations,
                    self._agent_def,
                    self._simulator_config,
                    context,
                    max_parallel,
                    run_timeout,
                    dashboard=dashboard,
                    transcript_dir=transcript_dir,
                )
            finally:
                # Close evaluators (e.g. ACPJudge) while the loop is still running
                for evaluator in self._evaluators.values():
                    if callable(getattr(evaluator, "close", None)):
                        try:
                            evaluator.close()
                        except Exception:  # noqa: BLE001, S110
                            pass

        # Suppress ACP SDK cleanup noise. The SDK's TaskSupervisor keeps background
        # tasks (Sender.loop, Connection.receive, Dispatcher.loop) alive past loop
        # close, producing "Task was destroyed" log messages and "Exception ignored"
        # unraisable warnings. Install permanent per-process filters targeting only
        # those sources so all other asyncio warnings remain visible.
        _install_acp_noise_filters()

        results = asyncio.run(_run())

        summary = _build_summary(results, self._config)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        return ConversationRunResult(
            mode=self._mode.value,
            config={
                "grade_pass_threshold": self._config.grade_pass_threshold,
                "case_pass_threshold": self._config.case_pass_threshold,
            },
            summary=summary,
            conversations=results,
            label=label,
            timestamp=timestamp,
        )
