"""Live ANSI dashboard for conversation simulation runs (§15.7).

Displays one row per persona×goal pair, aggregating all actors for that pair.
Only activates when stderr is a TTY; callers check sys.stderr.isatty() first.
"""

from __future__ import annotations

import dataclasses
import sys
import threading
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    from beval.conversation.types import ConversationResult, TurnResult


_RED   = "\033[31m"
_GREEN = "\033[32m"
_RESET = "\033[0m"


def _color(text: str, code: str) -> str:
    return f"{code}{text}{_RESET}"


def _score_bar(score: float, width: int = 10) -> str:
    """Render a score as a block bar like [########--]."""
    filled = round(score * width)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


@dataclasses.dataclass
class _PersonaGoalRow:
    """Aggregated state for one persona×goal pair across all its actors."""

    persona_id: str
    goal_id: str
    total_actors: int   # actor_count for this pair
    max_turns: int      # from eval.conversation.max_turns config
    done: int = 0       # actors that have completed (any termination)
    failed: int = 0     # actors that completed with passed=False
    running: int = 0    # actors currently active
    score_sum: float = 0.0
    goals_achieved: int = 0
    achievement_score_sum: float = 0.0  # sum of goal_achievement_score (1.0 if achieved, else last progress)
    last_turn: int = 0     # highest turn seen across all running actors
    turns_sum: int = 0     # total turns across all completed actors
    running_progress_sum: float = 0.0  # sum of latest goal_progress for running actors
    running_progress_count: int = 0    # how many running actors have reported progress
    satisfaction_sum: float = 0.0
    satisfaction_count: int = 0

    @property
    def avg_score(self) -> float | None:
        return self.score_sum / self.done if self.done > 0 else None

    @property
    def goal_rate(self) -> float | None:
        return self.goals_achieved / self.done if self.done > 0 else None

    @property
    def avg_running_progress(self) -> float | None:
        return (self.running_progress_sum / self.running_progress_count
                if self.running_progress_count > 0 else None)

    @property
    def avg_satisfaction(self) -> float | None:
        return (self.satisfaction_sum / self.satisfaction_count
                if self.satisfaction_count > 0 else None)


class _LiveDashboard:
    """ANSI rewrite dashboard for concurrent conversation actors.

    One row per persona×goal pair; aggregates all actors for that pair.
    Thread-safe: all public methods acquire _lock before mutating state.
    """

    def __init__(
        self,
        rows: list[tuple[str, str, int, int]],
        # Each element: (persona_id, goal_id, total_actors, max_turns)
        *,
        stream: TextIO = sys.stderr,
    ) -> None:
        self._stream = stream
        self._lock = threading.Lock()
        self._row_keys: list[tuple[str, str]] = []
        self._rows: dict[tuple[str, str], _PersonaGoalRow] = {}
        for persona_id, goal_id, total_actors, max_turns in rows:
            key = (persona_id, goal_id)
            if key not in self._rows:
                self._row_keys.append(key)
                self._rows[key] = _PersonaGoalRow(
                    persona_id=persona_id,
                    goal_id=goal_id,
                    total_actors=total_actors,
                    max_turns=max_turns,
                )
        self._lines_written = 0

    # ── Public mutation methods ───────────────────────────────────────────

    def on_actor_start(self, persona_id: str, goal_id: str) -> None:
        with self._lock:
            row = self._rows.get((persona_id, goal_id))
            if row is not None:
                row.running += 1
            self._render()

    def on_turn_start(self, persona_id: str, goal_id: str, turn: int) -> None:
        with self._lock:
            row = self._rows.get((persona_id, goal_id))
            if row is not None:
                row.last_turn = max(row.last_turn, turn)
            self._render()

    def on_turn_complete(
        self, persona_id: str, goal_id: str, goal_progress: float
    ) -> None:
        with self._lock:
            row = self._rows.get((persona_id, goal_id))
            if row is not None:
                # Replace running progress with latest value (simple approximation
                # for multi-actor: last reported progress per actor not tracked
                # individually, so we accumulate and re-average)
                row.running_progress_sum += goal_progress
                row.running_progress_count += 1
            self._render()

    def on_actor_complete(
        self, persona_id: str, goal_id: str, result: Any
    ) -> None:
        with self._lock:
            row = self._rows.get((persona_id, goal_id))
            if row is not None:
                row.running = max(0, row.running - 1)
                row.done += 1
                row.score_sum += result.overall_score
                row.turns_sum += result.turn_count
                row.achievement_score_sum += result.goal_achievement_score
                if result.goal_achieved:
                    row.goals_achieved += 1
                if not getattr(result, "passed", True):
                    row.failed += 1
                if getattr(result, "feedback", None) is not None:
                    row.satisfaction_sum += result.feedback.satisfaction
                    row.satisfaction_count += 1
                if row.running == 0:
                    row.last_turn = 0
                    row.running_progress_sum = 0.0
                    row.running_progress_count = 0
            self._render()

    def finish(self) -> None:
        """Final render + newline so subsequent output starts on a clean line."""
        with self._lock:
            self._render()
            self._stream.write("\n")
            self._stream.flush()

    # ── Rendering ────────────────────────────────────────────────────────

    def _render(self) -> None:
        """Erase previous render and write fresh table. Must be called under lock."""
        lines = self._build_lines()
        if self._lines_written > 0:
            self._stream.write(f"\033[{self._lines_written}A")
        for line in lines:
            self._stream.write(f"\r{line}\033[K\n")
        self._stream.flush()
        self._lines_written = len(lines)

    def _build_lines(self) -> list[str]:
        lines: list[str] = []

        # Header
        lines.append(
            f"  {'Persona':<28}  {'Goal':<22}  {'Done':>9}  {'Fail':>4}"
            f"  {'Act':>4}  {'Turn':>6}  {'Score':<14}  {'Sat':>5}  {'Goal%':>6}"
        )
        lines.append("  " + "─" * 111)

        for key in self._row_keys:
            row = self._rows[key]
            persona_short = row.persona_id[:26]
            goal_short = row.goal_id[:20]
            done_cell = f"{row.done}/{row.total_actors}"
            if row.running > 0:
                turn_cell = f"{row.last_turn}/{row.max_turns}"
            elif row.done > 0:
                avg_turns = round(row.turns_sum / row.done)
                turn_cell = f"{avg_turns} turns"
            else:
                turn_cell = "--"
            completed = row.running == 0 and row.done > 0
            if row.avg_score is not None:
                score_val = f"{_score_bar(row.avg_score, 8)} {row.avg_score:.2f}"
                if completed:
                    score_cell = _color(score_val, _GREEN if row.avg_score >= 0.7 else _RED)
                else:
                    score_cell = score_val
                # Use goal_achievement_score avg (1.0=achieved, else last progress)
                # so a conversation that stopped at 88% shows 88%, not 0%
                avg_achievement = row.achievement_score_sum / row.done
                goal_pct_val = f"{avg_achievement:.0%}"
                if completed:
                    goal_pct = _color(goal_pct_val, _GREEN if avg_achievement >= 1.0 else _RED)
                else:
                    goal_pct = goal_pct_val
            else:
                score_cell = "--"
                goal_pct = "--"
            # Show live goal progress for running actors (overrides done rate)
            if row.running > 0 and row.avg_running_progress is not None:
                goal_pct = f"~{row.avg_running_progress:.0%}"
            sat_cell = f"{row.avg_satisfaction:.2f}" if row.avg_satisfaction is not None else "--"
            fail_cell = _color(f"{row.failed:>4}", _RED) if row.failed > 0 else f"{'0':>4}"
            lines.append(
                f"  {persona_short:<28}  {goal_short:<22}  {done_cell:>9}"
                f"  {fail_cell}  {row.running:>4}  {turn_cell:>6}  {score_cell:<14}"
                f"  {sat_cell:>5}  {goal_pct:>6}"
            )

        lines.append("  " + "─" * 111)

        # Summary
        total_done = sum(r.done for r in self._rows.values())
        total_all = sum(r.total_actors for r in self._rows.values())
        total_failed = sum(r.failed for r in self._rows.values())
        total_achieved = sum(r.goals_achieved for r in self._rows.values())
        total_score = sum(r.score_sum for r in self._rows.values())
        avg = total_score / total_done if total_done > 0 else 0.0
        goal_rate = total_achieved / total_done if total_done > 0 else 0.0
        total_sat_sum = sum(r.satisfaction_sum for r in self._rows.values())
        total_sat_count = sum(r.satisfaction_count for r in self._rows.values())
        sat_str = ""
        if total_sat_count > 0:
            sat_str = f"   Avg sat: {total_sat_sum / total_sat_count:.2f}"
        total_passed = total_done - total_failed
        lines.append(
            f"  Total: {total_done}/{total_all} done"
            f"   Passed: {total_passed}/{total_done}"
            f"   Goal rate: {goal_rate:.0%}"
            f"   Avg score: {avg:.2f}"
            f"{sat_str}"
        )

        return lines
