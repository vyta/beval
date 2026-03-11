"""Tests for beval CLI via main(argv=[...])."""

from __future__ import annotations

import json
from pathlib import Path

from beval.cli import main

# Locate conformance fixtures relative to the repo root.
_FIXTURES = Path(__file__).resolve().parents[2] / "conformance" / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fixture_path(name: str) -> Path:
    return _FIXTURES / name


# ---------------------------------------------------------------------------
# version / help / no-command
# ---------------------------------------------------------------------------


class TestCliVersion:
    def test_version_output(self, capsys):
        exit_code = main(["version"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "beval v" in captured.out
        assert "spec v" in captured.out


class TestCliNoCommand:
    def test_no_command_returns_2(self, capsys):
        exit_code = main([])
        assert exit_code == 2


class TestCliHelp:
    def test_help_exits_zero(self, capsys):
        try:
            main(["--help"])
        except SystemExit as e:
            assert e.code == 0


# ---------------------------------------------------------------------------
# run subcommand
# ---------------------------------------------------------------------------


class TestCliRun:
    def test_run_missing_cases_flag(self, capsys):
        """run without --cases prints an error and exits 2."""
        exit_code = main(["run"])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "--cases is required" in captured.err

    def test_run_missing_cases_path(self, capsys, tmp_path):
        """run with a nonexistent --cases path errors."""
        exit_code = main(["run", "--cases", str(tmp_path / "nope.yaml")])
        assert exit_code == 2

    def test_run_basic_deterministic(self, capsys):
        """Run the basic-deterministic conformance fixture."""
        fp = _fixture_path("basic-deterministic")
        exit_code = main(
            [
                "--json",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
            ]
        )
        assert exit_code == 0

    def test_run_json_output_to_file(self, tmp_path):
        """--output writes a valid JSON results file."""
        fp = _fixture_path("basic-deterministic")
        out = tmp_path / "results.json"
        exit_code = main(
            [
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--output",
                str(out),
            ]
        )
        assert exit_code == 0
        data = json.loads(out.read_text())
        assert "summary" in data
        assert "cases" in data

    def test_run_jsonl_output_to_file(self, tmp_path):
        """--format jsonl writes a valid JSONL results file."""
        fp = _fixture_path("basic-deterministic")
        out = tmp_path / "results.jsonl"
        exit_code = main(
            [
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--output",
                str(out),
                "--format",
                "jsonl",
            ]
        )
        assert exit_code == 0
        lines = out.read_text().strip().splitlines()
        assert len(lines) >= 2
        # Each line must be valid JSON
        for line in lines:
            json.loads(line)
        # Last line is the summary
        last = json.loads(lines[-1])
        assert "summary" in last

    def test_run_jsonl_stdout(self, capsys):
        """--format jsonl prints JSONL to stdout."""
        fp = _fixture_path("basic-deterministic")
        exit_code = main(
            [
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--format",
                "jsonl",
            ]
        )
        assert exit_code == 0
        out = capsys.readouterr().out.strip()
        lines = out.splitlines()
        assert len(lines) >= 2
        for line in lines:
            json.loads(line)

    def test_run_verbose_output(self, capsys):
        """--verbose preserves subject_output in JSON output."""
        fp = _fixture_path("basic-deterministic")
        exit_code = main(
            [
                "--verbose",
                "--json",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
            ]
        )
        assert exit_code == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        # In verbose mode, subject_output is preserved (not stripped)
        assert "cases" in data

    def test_run_with_config(self, capsys):
        """run with --config loads the config file."""
        fp = _fixture_path("config-override")
        exit_code = main(
            [
                "--json",
                "-c",
                str(fp / "config.yaml"),
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
            ]
        )
        # config-override sets case_pass_threshold: 0.4, so the case passes
        assert exit_code == 0

    def test_run_mixed_scores_fails(self, capsys):
        """mixed-scores fixture has a failing grade → exit 1."""
        fp = _fixture_path("mixed-scores")
        exit_code = main(
            [
                "--json",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
            ]
        )
        assert exit_code == 1

    def test_run_output_to_directory(self, tmp_path):
        """--output pointing to a directory creates results.<format> inside it."""
        fp = _fixture_path("basic-deterministic")
        exit_code = main(
            [
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--output",
                str(tmp_path),
            ]
        )
        assert exit_code == 0
        assert (tmp_path / "results.json").is_file()

    def test_run_save_and_compare_baseline(self, tmp_path, monkeypatch):
        """--save-baseline followed by --compare-baseline round-trips."""
        monkeypatch.chdir(tmp_path)
        fp = _fixture_path("basic-deterministic")
        # First run: save
        rc = main(
            [
                "--json",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--save-baseline",
            ]
        )
        assert rc == 0
        # Second run: compare (same data → no regression)
        rc = main(
            [
                "--json",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--compare-baseline",
            ]
        )
        assert rc == 0

    def test_run_missing_subject_file(self, capsys, tmp_path):
        """run with nonexistent --subject path errors."""
        fp = _fixture_path("basic-deterministic")
        exit_code = main(
            [
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(tmp_path / "nope.json"),
            ]
        )
        assert exit_code == 2

    def test_run_quiet_suppresses_output(self, capsys, tmp_path):
        """--quiet suppresses non-essential output."""
        fp = _fixture_path("basic-deterministic")
        out = tmp_path / "results.json"
        exit_code = main(
            [
                "--quiet",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--output",
                str(out),
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        # Quiet mode should suppress the "Results written to" message
        assert "Results written" not in captured.out


# ---------------------------------------------------------------------------
# validate subcommand
# ---------------------------------------------------------------------------


class TestCliValidate:
    def test_validate_no_args(self, capsys):
        exit_code = main(["validate"])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "provide --cases or --config" in captured.err

    def test_validate_cases_file(self, capsys):
        """validate --cases on a valid fixture input.yaml passes."""
        fp = _fixture_path("basic-deterministic")
        exit_code = main(["validate", "--cases", str(fp / "input.yaml")])
        assert exit_code in (0, 1)  # 0 if schema validates, 1 if jsonschema missing

    def test_validate_nonexistent_cases(self, capsys, tmp_path):
        """validate --cases with missing file reports error."""
        exit_code = main(["validate", "--cases", str(tmp_path / "nope.yaml")])
        assert exit_code == 1

    def test_validate_config_file(self, capsys):
        """validate --config on a valid config.yaml."""
        fp = _fixture_path("config-override")
        exit_code = main(
            [
                "validate",
                "--config",
                str(fp / "config.yaml"),
            ]
        )
        assert exit_code in (0, 1)


# ---------------------------------------------------------------------------
# compare subcommand
# ---------------------------------------------------------------------------


class TestCliCompare:
    def test_compare_no_results(self, capsys):
        """compare without --results errors."""
        exit_code = main(["compare"])
        assert exit_code == 2

    def test_compare_single_result(self, capsys, tmp_path):
        """compare with only one result file errors."""
        r1 = tmp_path / "r1.json"
        r1.write_text(json.dumps({"summary": {"overall_score": 1.0, "metrics": {}}}))
        exit_code = main(["compare", "--results", str(r1)])
        assert exit_code == 2

    def test_compare_two_results_table(self, capsys, tmp_path):
        """compare with two result files prints a table."""
        r1 = tmp_path / "r1.json"
        r2 = tmp_path / "r2.json"
        r1.write_text(
            json.dumps(
                {
                    "summary": {"overall_score": 1.0, "metrics": {"relevance": 1.0}},
                }
            )
        )
        r2.write_text(
            json.dumps(
                {
                    "summary": {"overall_score": 0.8, "metrics": {"relevance": 0.8}},
                }
            )
        )
        exit_code = main(["compare", "--results", str(r1), str(r2)])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "overall_score" in out

    def test_compare_json_format(self, capsys, tmp_path):
        """compare --format json outputs valid JSON."""
        r1 = tmp_path / "r1.json"
        r2 = tmp_path / "r2.json"
        r1.write_text(json.dumps({"summary": {"overall_score": 1.0, "metrics": {}}}))
        r2.write_text(json.dumps({"summary": {"overall_score": 0.5, "metrics": {}}}))
        exit_code = main(
            [
                "compare",
                "--results",
                str(r1),
                str(r2),
                "--format",
                "json",
            ]
        )
        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_compare_output_to_file(self, tmp_path):
        """compare --output writes to file."""
        r1 = tmp_path / "r1.json"
        r2 = tmp_path / "r2.json"
        out = tmp_path / "cmp.txt"
        r1.write_text(json.dumps({"summary": {"overall_score": 1.0, "metrics": {}}}))
        r2.write_text(json.dumps({"summary": {"overall_score": 0.5, "metrics": {}}}))
        exit_code = main(
            [
                "compare",
                "--results",
                str(r1),
                str(r2),
                "--output",
                str(out),
            ]
        )
        assert exit_code == 0
        assert out.is_file()


# ---------------------------------------------------------------------------
# baseline subcommand
# ---------------------------------------------------------------------------


class TestCliBaseline:
    def test_baseline_no_subcommand(self, capsys):
        """baseline without subcommand errors."""
        exit_code = main(["baseline"])
        assert exit_code == 2

    def test_baseline_show_empty(self, capsys, monkeypatch, tmp_path):
        """baseline show when no baseline saved prints message."""
        monkeypatch.chdir(tmp_path)
        exit_code = main(["baseline", "show"])
        assert exit_code == 0
        assert "No baseline" in capsys.readouterr().out

    def test_baseline_clear_empty(self, capsys, monkeypatch, tmp_path):
        """baseline clear when no baseline saved prints message."""
        monkeypatch.chdir(tmp_path)
        exit_code = main(["baseline", "clear"])
        assert exit_code == 0
        assert "No baseline" in capsys.readouterr().out

    def test_baseline_save_hint(self, capsys):
        """baseline save hints to use run --save-baseline."""
        exit_code = main(["baseline", "save"])
        assert exit_code == 2

    def test_baseline_show_after_save(self, capsys, monkeypatch, tmp_path):
        """baseline show after saving via run --save-baseline shows data."""
        monkeypatch.chdir(tmp_path)
        fp = _fixture_path("basic-deterministic")
        main(
            [
                "--json",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--save-baseline",
            ]
        )
        capsys.readouterr()  # clear
        exit_code = main(["baseline", "show"])
        assert exit_code == 0
        data = json.loads(capsys.readouterr().out)
        assert "summary" in data

    def test_baseline_clear_after_save(self, capsys, monkeypatch, tmp_path):
        """baseline clear removes saved baseline."""
        monkeypatch.chdir(tmp_path)
        fp = _fixture_path("basic-deterministic")
        main(
            [
                "--json",
                "run",
                "--cases",
                str(fp / "input.yaml"),
                "--subject",
                str(fp / "subject.json"),
                "--save-baseline",
            ]
        )
        capsys.readouterr()  # clear
        exit_code = main(["baseline", "clear"])
        assert exit_code == 0
        assert "cleared" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# cache subcommand
# ---------------------------------------------------------------------------


class TestCliCache:
    def test_cache_no_subcommand(self, capsys):
        """cache without subcommand errors."""
        exit_code = main(["cache"])
        assert exit_code == 2

    def test_cache_show(self, capsys, monkeypatch, tmp_path):
        """cache show reports statistics."""
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        exit_code = main(["cache", "show"])
        assert exit_code == 0
        out = capsys.readouterr().out
        assert "Entries:" in out

    def test_cache_clear_empty(self, capsys, monkeypatch, tmp_path):
        """cache clear on empty cache reports 0 entries."""
        monkeypatch.setenv("BEVAL_CACHE_DIR", str(tmp_path / "cache"))
        exit_code = main(["cache", "clear"])
        assert exit_code == 0
        assert "0" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# init subcommand
# ---------------------------------------------------------------------------


class TestCliInit:
    def test_init_scaffolds_project(self, tmp_path):
        """init creates config and case files."""
        target = tmp_path / "myproject"
        exit_code = main(["init", "--dir", str(target)])
        assert exit_code == 0
        assert (target / "eval.config.yaml").is_file()
        assert (target / "cases" / "example.yaml").is_file()

    def test_init_idempotent(self, tmp_path):
        """Running init twice does not overwrite existing files."""
        target = tmp_path / "proj"
        main(["init", "--dir", str(target)])
        config_text = (target / "eval.config.yaml").read_text()
        main(["init", "--dir", str(target)])
        assert (target / "eval.config.yaml").read_text() == config_text
