"""Conformance fixture tests — validate cross-language fixtures load correctly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

# Locate the conformance fixtures relative to the repo root
_CONFORMANCE_DIR = Path(__file__).resolve().parents[2] / "conformance" / "fixtures"

# Collect fixture directories that have all three data files
_FIXTURE_DIRS = sorted(
    d
    for d in _CONFORMANCE_DIR.iterdir()
    if d.is_dir()
    and (d / "input.yaml").exists()
    and (d / "expected.json").exists()
    and (d / "subject.json").exists()
) if _CONFORMANCE_DIR.is_dir() else []

# Fixtures that also ship a config.yaml
_CONFIG_FIXTURE_DIRS = [d for d in _FIXTURE_DIRS if (d / "config.yaml").exists()]

# Fixtures that ship an expected-exit-code file
_EXIT_CODE_FIXTURE_DIRS = sorted(
    d
    for d in _CONFORMANCE_DIR.iterdir()
    if d.is_dir() and (d / "expected-exit-code").exists()
) if _CONFORMANCE_DIR.is_dir() else []


@pytest.mark.parametrize(
    "fixture_dir",
    _FIXTURE_DIRS,
    ids=[d.name for d in _FIXTURE_DIRS],
)
class TestConformanceFixtures:
    def test_input_yaml_loads(self, fixture_dir: Path):
        """Input YAML files must load as valid mappings."""
        data = yaml.safe_load((fixture_dir / "input.yaml").read_text())
        assert isinstance(data, dict)
        assert "cases" in data

    def test_expected_json_loads(self, fixture_dir: Path):
        """Expected JSON files must load and contain required fields."""
        data = json.loads((fixture_dir / "expected.json").read_text())
        assert isinstance(data, dict)
        assert "summary" in data
        assert "cases" in data

    def test_subject_json_loads(self, fixture_dir: Path):
        """Subject JSON files must load as valid JSON."""
        data = json.loads((fixture_dir / "subject.json").read_text())
        assert isinstance(data, dict)


@pytest.mark.parametrize(
    "fixture_dir",
    _CONFIG_FIXTURE_DIRS,
    ids=[d.name for d in _CONFIG_FIXTURE_DIRS],
)
class TestConformanceConfigFixtures:
    def test_config_yaml_loads(self, fixture_dir: Path):
        """Config YAML files must load as valid mappings."""
        data = yaml.safe_load((fixture_dir / "config.yaml").read_text())
        assert isinstance(data, dict)

    def test_expected_reflects_config(self, fixture_dir: Path):
        """Expected output includes config when config.yaml is provided."""
        data = json.loads(
            (fixture_dir / "expected.json").read_text(),
        )
        assert "config" in data


@pytest.mark.parametrize(
    "fixture_dir",
    _EXIT_CODE_FIXTURE_DIRS,
    ids=[d.name for d in _EXIT_CODE_FIXTURE_DIRS],
)
class TestConformanceExitCodes:
    def test_exit_code_is_valid_integer(self, fixture_dir: Path):
        """Expected exit code files must contain a single integer."""
        text = (fixture_dir / "expected-exit-code").read_text().strip()
        code = int(text)
        assert code in (0, 1, 2, 3), f"Unexpected exit code {code}"


class TestYamlSafety:
    """Verify malicious YAML is rejected by safe_load."""

    def test_malicious_yaml_rejected(self):
        malicious_path = _CONFORMANCE_DIR / "yaml-safety" / "malicious.yaml"
        if not malicious_path.exists():
            pytest.skip("malicious.yaml fixture not found")
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(malicious_path.read_text())


class TestConformanceConfigFormat:
    """Verify config fixtures work with both nested and flat formats."""

    def test_config_override_loads_flat(self):
        """Config-override fixture (flat format) loads correctly."""
        config_path = _CONFORMANCE_DIR / "config-override" / "config.yaml"
        if not config_path.exists():
            pytest.skip("config-override fixture not found")
        data = yaml.safe_load(config_path.read_text())
        assert isinstance(data, dict)

    def test_nested_eval_format_extracted(self):
        """A config with top-level ``eval`` key extracts the inner block."""
        import tempfile

        from beval.cli import _load_config_file

        nested = {"eval": {"thresholds": {"grade_pass": 0.8, "case_pass": 0.9}}}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp:
            yaml.safe_dump(nested, tmp)
            tmp_path = tmp.name
        try:
            result = _load_config_file(tmp_path)
            assert result == {"thresholds": {"grade_pass": 0.8, "case_pass": 0.9}}
        finally:
            Path(tmp_path).unlink()

    def test_flat_format_fallback(self):
        """A config without ``eval`` key returns flat keys directly."""
        import tempfile

        from beval.cli import _load_config_file

        flat = {"grade_pass_threshold": 0.6, "skip_mode": "strict"}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as tmp:
            yaml.safe_dump(flat, tmp)
            tmp_path = tmp.name
        try:
            result = _load_config_file(tmp_path)
            assert result == flat
        finally:
            Path(tmp_path).unlink()

    def test_none_path_returns_empty(self):
        """None config path returns empty dict."""
        from beval.cli import _load_config_file

        assert _load_config_file(None) == {}


# ---------------------------------------------------------------------------
# End-to-end conformance: run the Python CLI against each fixture
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture_dir",
    _EXIT_CODE_FIXTURE_DIRS,
    ids=[d.name for d in _EXIT_CODE_FIXTURE_DIRS],
)
class TestConformanceEndToEnd:
    """Run ``beval run`` on each conformance fixture and verify the exit code."""

    def test_exit_code_matches(self, fixture_dir: Path):
        from beval.cli import main

        expected_code = int(
            (fixture_dir / "expected-exit-code").read_text().strip()
        )

        argv = ["--json"]

        config_path = fixture_dir / "config.yaml"
        if config_path.is_file():
            argv += ["-c", str(config_path)]

        argv += [
            "run",
            "--cases", str(fixture_dir / "input.yaml"),
            "--subject", str(fixture_dir / "subject.json"),
        ]

        actual_code = main(argv)
        assert actual_code == expected_code, (
            f"{fixture_dir.name}: expected exit {expected_code}, got {actual_code}"
        )
