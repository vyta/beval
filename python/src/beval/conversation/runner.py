"""Conversation simulation runner (§15.7, §15.8).

See spec/conversation-sim.spec.md for the normative specification.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import statistics
from pathlib import Path
from typing import Any

import yaml

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
) -> tuple[list[Persona], dict[str, Goal]]:
    """Load personas and goals from config sources (§15.3.2, §15.4.2).

    Returns (personas, goal_pool) where goal_pool is keyed by goal ID.
    Raises SystemExit(2) on invalid configuration.
    """
    goal_pool: dict[str, Goal] = {}
    persona_list: list[Persona] = []

    # Load goals first so persona goal-ID references can be validated
    for source in conv_config.get("goals", []):
        if "file" in source:
            path = Path(source["file"])
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
) -> list[tuple[Persona, Goal, int]]:
    """Build the (persona, goal, actor_index) list using persona-centric pairing (§15.1)."""  # noqa: E501
    conversations = []
    for persona in personas:
        for goal_id in persona.goals:
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


async def _run_all_actors(
    conversations: list[tuple[Persona, Goal, int]],
    agent_def: dict[str, Any],
    simulator_config: dict[str, Any],
    context: EvalContext,
    max_parallel_actors: int,
    run_timeout_seconds: float | None,
) -> list[ConversationResult]:
    """Run all actors concurrently with semaphore throttling (§15.7.2)."""
    sem = asyncio.Semaphore(max_parallel_actors)

    async def bounded(
        persona: Persona, goal: Goal, actor_index: int
    ) -> ConversationResult:
        async with sem:
            adapter = create_adapter(agent_def)
            simulator: UserSimulatorInterface = load_simulator_from_config(
                simulator_config
            )
            try:
                return await run_actor(
                    persona, goal, actor_index, adapter, simulator, context
                )
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
    ) -> None:
        self._agent_def = agent_def
        self._simulator_config = simulator_config
        self._conv_config = conv_config
        self._mode = mode
        self._config = config or RunConfig()
        self._evaluators = evaluators or {}

    def run(self, *, label: str | None = None) -> ConversationRunResult:
        """Load personas/goals, run all actors, return ConversationRunResult."""
        personas, goal_pool = load_personas_and_goals(self._conv_config)

        actor_count = int(self._conv_config.get("actor_count", 1))
        max_parallel = int(self._conv_config.get("max_parallel_actors", 1))
        run_timeout = self._conv_config.get("run_timeout_seconds")
        if run_timeout is not None:
            run_timeout = float(run_timeout)

        conversations = _build_conversations(personas, goal_pool, actor_count)
        if not conversations:
            logger.error("No conversations to run — check personas and goals configuration.")  # noqa: E501
            raise SystemExit(2)

        context = EvalContext(
            evaluators=self._evaluators,
            mode=self._mode,
            config=self._config,
        )

        results = asyncio.run(
            _run_all_actors(
                conversations,
                self._agent_def,
                self._simulator_config,
                context,
                max_parallel,
                run_timeout,
            )
        )

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
