"""Tests for beval baseline snapshot management."""

from __future__ import annotations

import json

from beval.baseline import (
    clear_baseline,
    compare_baseline,
    load_baseline,
    save_baseline,
)

_BL_ATTR = "beval.baseline._DEFAULT_BASELINE_DIR"


class TestSaveAndLoad:
    def test_save_creates_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_BL_ATTR, str(tmp_path / ".beval"))
        data = {
            "summary": {"overall_score": 0.9, "metrics": {"relevance": 0.8}},
        }
        path = save_baseline(data)
        assert path.is_file()
        loaded = json.loads(path.read_text())
        assert loaded == data

    def test_load_returns_saved_data(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_BL_ATTR, str(tmp_path / ".beval"))
        data = {"summary": {"overall_score": 1.0, "metrics": {}}}
        save_baseline(data)
        loaded = load_baseline()
        assert loaded == data

    def test_load_returns_none_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_BL_ATTR, str(tmp_path / ".beval"))
        assert load_baseline() is None

    def test_save_overwrites_existing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_BL_ATTR, str(tmp_path / ".beval"))
        save_baseline({"v": 1})
        save_baseline({"v": 2})
        loaded = load_baseline()
        assert loaded == {"v": 2}


class TestClearBaseline:
    def test_clear_removes_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_BL_ATTR, str(tmp_path / ".beval"))
        save_baseline({"summary": {}})
        assert clear_baseline() is True
        assert load_baseline() is None

    def test_clear_returns_false_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(_BL_ATTR, str(tmp_path / ".beval"))
        assert clear_baseline() is False


class TestCompareBaseline:
    def test_no_regression(self):
        baseline = {"summary": {"overall_score": 0.8, "metrics": {"relevance": 0.8}}}
        current = {"summary": {"overall_score": 0.85, "metrics": {"relevance": 0.85}}}
        result = compare_baseline(current, baseline)
        assert not result["regressed"]
        assert result["overall_delta"] > 0

    def test_detects_overall_regression(self):
        baseline = {"summary": {"overall_score": 0.9, "metrics": {}}}
        current = {"summary": {"overall_score": 0.7, "metrics": {}}}
        result = compare_baseline(current, baseline)
        assert result["regressed"]
        regressions = result["regressions"]
        metrics = [r["metric"] for r in regressions]
        assert "overall_score" in metrics

    def test_detects_metric_regression(self):
        baseline = {"summary": {"overall_score": 0.9, "metrics": {"safety": 0.95}}}
        current = {"summary": {"overall_score": 0.9, "metrics": {"safety": 0.80}}}
        result = compare_baseline(current, baseline)
        assert result["regressed"]
        metrics = [r["metric"] for r in result["regressions"]]
        assert "safety" in metrics

    def test_custom_threshold(self):
        baseline = {"summary": {"overall_score": 0.9, "metrics": {"quality": 0.9}}}
        current = {"summary": {"overall_score": 0.88, "metrics": {"quality": 0.88}}}
        # Default threshold 0.05 → no regression (delta -0.02)
        assert not compare_baseline(current, baseline)["regressed"]
        # Tight threshold 0.01 → regression detected
        assert compare_baseline(current, baseline, threshold=0.01)["regressed"]

    def test_new_metric_not_regression(self):
        baseline = {"summary": {"overall_score": 0.9, "metrics": {}}}
        current = {"summary": {"overall_score": 0.9, "metrics": {"new_metric": 0.8}}}
        result = compare_baseline(current, baseline)
        assert not result["regressed"]
        assert "new_metric" in result["metric_deltas"]

    def test_empty_summaries(self):
        result = compare_baseline({}, {})
        assert not result["regressed"]
        assert result["overall_delta"] == 0.0
