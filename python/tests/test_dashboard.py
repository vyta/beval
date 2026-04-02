"""Tests for conversation/dashboard.py."""

from __future__ import annotations

import io

import pytest

from beval.conversation.dashboard import _LiveDashboard, _PersonaGoalRow, _score_bar


# ── _score_bar ────────────────────────────────────────────────────────────────


def test_score_bar_zero():
    assert _score_bar(0.0, width=10) == "[----------]"


def test_score_bar_full():
    assert _score_bar(1.0, width=10) == "[##########]"


def test_score_bar_half():
    assert _score_bar(0.5, width=10) == "[#####-----]"


def test_score_bar_width():
    bar = _score_bar(0.5, width=4)
    assert bar == "[##--]"
    assert len(bar) == 6  # 4 + 2 brackets


# ── _PersonaGoalRow helpers ───────────────────────────────────────────────────


def test_persona_goal_row_avg_score_no_done():
    row = _PersonaGoalRow("p", "g", 5, 20)
    assert row.avg_score is None


def test_persona_goal_row_avg_score():
    row = _PersonaGoalRow("p", "g", 5, 20, done=2, score_sum=1.0)
    assert row.avg_score == pytest.approx(0.5)


def test_persona_goal_row_goal_rate_no_done():
    row = _PersonaGoalRow("p", "g", 5, 20)
    assert row.goal_rate is None


def test_persona_goal_row_goal_rate():
    row = _PersonaGoalRow("p", "g", 5, 20, done=4, goals_achieved=3)
    assert row.goal_rate == pytest.approx(0.75)


# ── _LiveDashboard construction ───────────────────────────────────────────────


def _make_dashboard(n_rows: int = 2) -> tuple[_LiveDashboard, io.StringIO]:
    stream = io.StringIO()
    rows = [(f"persona_{i}", f"goal_{i}", 10, 20) for i in range(n_rows)]
    db = _LiveDashboard(rows, stream=stream)
    return db, stream


def test_dashboard_build_lines_count():
    db, _ = _make_dashboard(3)
    lines = db._build_lines()
    # header + separator + 3 rows + separator + summary = 7
    assert len(lines) == 7


def test_dashboard_build_lines_zero_rows():
    db, _ = _make_dashboard(0)
    lines = db._build_lines()
    # header + separator + separator + summary = 4
    assert len(lines) == 4


def test_dashboard_initial_status_waiting():
    db, _ = _make_dashboard(1)
    lines = db._build_lines()
    row_line = lines[2]  # after header + separator
    assert "--" in row_line  # score shows "--" when no actors done


# ── on_actor_start ────────────────────────────────────────────────────────────


def test_on_actor_start_increments_running():
    db, _ = _make_dashboard(1)
    db.on_actor_start("persona_0", "goal_0")
    assert db._rows[("persona_0", "goal_0")].running == 1


def test_on_actor_start_triggers_render():
    db, stream = _make_dashboard(1)
    db.on_actor_start("persona_0", "goal_0")
    assert stream.tell() > 0


# ── on_actor_complete ─────────────────────────────────────────────────────────


class _FakeResult:
    def __init__(self, overall_score: float, goal_achieved: bool, turn_count: int = 3):
        self.overall_score = overall_score
        self.goal_achieved = goal_achieved
        self.turn_count = turn_count
        self.goal_achievement_score = 1.0 if goal_achieved else overall_score


def test_on_actor_complete_decrements_running():
    db, _ = _make_dashboard(1)
    db.on_actor_start("persona_0", "goal_0")
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(0.8, True))
    assert db._rows[("persona_0", "goal_0")].running == 0


def test_on_actor_complete_increments_done():
    db, _ = _make_dashboard(1)
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(0.6, False))
    assert db._rows[("persona_0", "goal_0")].done == 1


def test_on_actor_complete_accumulates_score():
    db, _ = _make_dashboard(1)
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(0.4, False))
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(0.6, False))
    assert db._rows[("persona_0", "goal_0")].score_sum == pytest.approx(1.0)


def test_on_actor_complete_counts_goal_achieved():
    db, _ = _make_dashboard(1)
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(0.9, True))
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(0.3, False))
    assert db._rows[("persona_0", "goal_0")].goals_achieved == 1


def test_on_actor_complete_running_not_below_zero():
    db, _ = _make_dashboard(1)
    # Complete without start — running stays at 0
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(0.5, False))
    assert db._rows[("persona_0", "goal_0")].running == 0


# ── Summary line ──────────────────────────────────────────────────────────────


def test_summary_line_totals():
    db, _ = _make_dashboard(2)
    db.on_actor_complete("persona_0", "goal_0", _FakeResult(1.0, True))
    db.on_actor_complete("persona_1", "goal_1", _FakeResult(0.0, False))
    lines = db._build_lines()
    summary = lines[-1]
    assert "2/20" in summary   # 2 done out of 20 total (10 per pair)
    assert "50%" in summary    # 1/2 goal rate


# ── Rendering (cursor-up) ─────────────────────────────────────────────────────


def test_render_cursor_up_on_second_call():
    db, stream = _make_dashboard(1)
    db._render()
    lines_first = db._lines_written
    stream.seek(0)
    stream.truncate()
    db._render()
    output = stream.getvalue()
    # Should start with cursor-up escape sequence
    assert output.startswith(f"\033[{lines_first}A")


def test_render_lines_written_matches_build():
    db, _ = _make_dashboard(2)
    db._render()
    assert db._lines_written == len(db._build_lines())


# ── finish ────────────────────────────────────────────────────────────────────


def test_finish_writes_trailing_newline():
    db, stream = _make_dashboard(1)
    db.finish()
    output = stream.getvalue()
    assert output.endswith("\n")


# ── Unknown persona/goal key is ignored gracefully ────────────────────────────


def test_unknown_key_ignored():
    db, _ = _make_dashboard(1)
    db.on_actor_start("no_such_persona", "no_such_goal")  # should not raise
    db.on_actor_complete("no_such_persona", "no_such_goal", _FakeResult(0.5, False))
