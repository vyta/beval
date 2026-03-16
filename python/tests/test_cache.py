"""Tests for beval response cache."""

from __future__ import annotations

from beval.cache import (
    cache_clear,
    cache_stats,
    get_cached_subject,
    put_cached_subject,
)
from beval.types import Subject


def _make_subject(**kwargs) -> Subject:
    defaults = {
        "input": "What is AI?",
        "output": "Artificial intelligence.",
        "completion_time": 1.5,
    }
    defaults.update(kwargs)
    return Subject(**defaults)


class TestPutAndGet:
    def test_round_trip(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        subject = _make_subject()
        put_cached_subject("case1", subject)
        cached = get_cached_subject("case1", subject.input)
        assert cached is not None
        assert cached.output == subject.output
        assert cached.completion_time == subject.completion_time

    def test_get_miss(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        assert get_cached_subject("no_such_case", "query") is None

    def test_different_inputs_different_keys(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        s1 = _make_subject(input="question A")
        s2 = _make_subject(input="question B")
        put_cached_subject("case1", s1)
        put_cached_subject("case1", s2)
        assert get_cached_subject("case1", "question A") is not None
        assert get_cached_subject("case1", "question B") is not None

    def test_scrubs_sensitive_values(self, monkeypatch, tmp_path):
        """Cached data should have sensitive keys redacted."""
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        subject = _make_subject(metadata={"api_key": "secret123", "model": "gpt"})
        put_cached_subject("case_secret", subject)
        # Read the raw cache file to verify scrubbing
        import json

        cache_files = list((tmp_path / "cache").glob("*.json"))
        assert len(cache_files) == 1
        data = json.loads(cache_files[0].read_text())
        assert data["metadata"]["api_key"] == "***REDACTED***"
        assert data["metadata"]["model"] == "gpt"


class TestCacheStats:
    def test_empty_cache(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        stats = cache_stats()
        assert stats["entries"] == 0
        assert stats["size_bytes"] == 0

    def test_stats_after_put(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        put_cached_subject("c1", _make_subject())
        put_cached_subject("c2", _make_subject(input="other"))
        stats = cache_stats()
        assert stats["entries"] == 2
        assert stats["size_bytes"] > 0


class TestCacheClear:
    def test_clear_empty(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        assert cache_clear() == 0

    def test_clear_removes_entries(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        put_cached_subject("c1", _make_subject())
        put_cached_subject("c2", _make_subject(input="other"))
        removed = cache_clear()
        assert removed == 2
        assert cache_stats()["entries"] == 0

    def test_get_after_clear_returns_none(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        subject = _make_subject()
        put_cached_subject("c1", subject)
        cache_clear()
        assert get_cached_subject("c1", subject.input) is None
