"""Tests for the agent adapter system. See SPEC §13."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from beval.adapters import (
    AdapterInput,
    AdapterInterface,
    adapter_as_handler,
    create_adapter,
    load_agent,
)
from beval.types import EvalContext, Subject


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent_yaml(tmp_path: Path) -> Path:
    """Write a minimal valid agent YAML file."""
    p = tmp_path / "agent.yaml"
    p.write_text(
        yaml.dump(
            {
                "name": "test-agent",
                "protocol": "custom",
                "connection": {
                    "module": "my_mod",
                    "class": "MyAdapter",
                },
            }
        )
    )
    return p


@pytest.fixture()
def acp_agent_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "acp-agent.yaml"
    p.write_text(
        yaml.dump(
            {
                "name": "acp-test",
                "protocol": "acp",
                "connection": {
                    "transport": "stdio",
                    "command": ["echo", "hello"],
                },
                "timeout": 10,
            }
        )
    )
    return p


@pytest.fixture()
def a2a_agent_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "a2a-agent.yaml"
    p.write_text(
        yaml.dump(
            {
                "name": "a2a-test",
                "protocol": "a2a",
                "connection": {
                    "url": "https://agent.example.com",
                    "streaming": False,
                },
                "timeout": 10,
            }
        )
    )
    return p


class FakeAdapter(AdapterInterface):
    """Adapter stub for testing."""

    def __init__(self) -> None:
        self.closed = False
        self.last_input: AdapterInput | None = None

    def invoke(self, adapter_input: AdapterInput) -> Subject:
        self.last_input = adapter_input
        return Subject(
            input=adapter_input.query,
            output="fake response",
            completion_time=0.1,
        )

    def close(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# load_agent tests
# ---------------------------------------------------------------------------


class TestLoadAgent:
    def test_load_from_file(self, agent_yaml: Path) -> None:
        result = load_agent(str(agent_yaml))
        assert result["name"] == "test-agent"
        assert result["protocol"] == "custom"

    def test_file_not_found(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            load_agent("/nonexistent/agent.yaml")
        assert exc_info.value.code == 2

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump({"name": "x"}))
        with pytest.raises(SystemExit) as exc_info:
            load_agent(str(p))
        assert exc_info.value.code == 2

    def test_unknown_protocol(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text(
            yaml.dump(
                {"name": "x", "protocol": "unknown", "connection": {}}
            )
        )
        with pytest.raises(SystemExit) as exc_info:
            load_agent(str(p))
        assert exc_info.value.code == 2

    def test_env_var_resolution(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_KEY", "resolved_value")
        p = tmp_path / "env.yaml"
        p.write_text(
            yaml.dump(
                {
                    "name": "env-agent",
                    "protocol": "custom",
                    "connection": {
                        "module": "mod",
                        "class": "Cls",
                        "config": {"key": "${TEST_KEY}"},
                    },
                }
            )
        )
        result = load_agent(str(p))
        assert result["connection"]["config"]["key"] == "resolved_value"

    def test_missing_env_var(self, tmp_path: Path) -> None:
        p = tmp_path / "env.yaml"
        p.write_text(
            yaml.dump(
                {
                    "name": "env-agent",
                    "protocol": "custom",
                    "connection": {
                        "module": "mod",
                        "class": "Cls",
                        "config": {"key": "${NONEXISTENT_VAR_12345}"},
                    },
                }
            )
        )
        # Ensure the var is not set
        os.environ.pop("NONEXISTENT_VAR_12345", None)
        with pytest.raises(SystemExit) as exc_info:
            load_agent(str(p))
        assert exc_info.value.code == 2

    def test_bare_name_lookup(self) -> None:
        config_agents = {
            "definitions": [
                {
                    "name": "my-agent",
                    "protocol": "custom",
                    "connection": {"module": "m", "class": "C"},
                }
            ]
        }
        result = load_agent("my-agent", config_agents=config_agents)
        assert result["name"] == "my-agent"

    def test_bare_name_not_found(self) -> None:
        config_agents = {"definitions": []}
        with pytest.raises(SystemExit) as exc_info:
            load_agent("missing", config_agents=config_agents)
        assert exc_info.value.code == 2

    def test_bare_name_no_config(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            load_agent("missing")
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# create_adapter tests
# ---------------------------------------------------------------------------


class TestCreateAdapter:
    def test_dispatches_acp(self) -> None:
        agent_def = {
            "name": "a",
            "protocol": "acp",
            "connection": {"transport": "stdio", "command": ["echo"]},
        }
        with patch("beval.adapters.acp.ACPAdapter") as mock_cls:
            mock_cls.return_value = MagicMock()
            adapter = create_adapter(agent_def)
            mock_cls.assert_called_once_with(agent_def)

    def test_dispatches_a2a(self) -> None:
        agent_def = {
            "name": "a",
            "protocol": "a2a",
            "connection": {"url": "http://x"},
        }
        with patch("beval.adapters.a2a.A2AAdapter") as mock_cls:
            mock_cls.return_value = MagicMock()
            adapter = create_adapter(agent_def)
            mock_cls.assert_called_once_with(agent_def)

    def test_dispatches_custom(self) -> None:
        agent_def = {
            "name": "a",
            "protocol": "custom",
            "connection": {"module": "m", "class": "C"},
        }
        with patch("beval.adapters.custom.CustomAdapter") as mock_cls:
            mock_cls.return_value = MagicMock()
            adapter = create_adapter(agent_def)
            mock_cls.assert_called_once_with(agent_def)

    def test_unknown_protocol(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            create_adapter({"protocol": "nope"})
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# adapter_as_handler tests
# ---------------------------------------------------------------------------


class TestAdapterAsHandler:
    def test_wraps_invoke(self) -> None:
        adapter = FakeAdapter()
        handler = adapter_as_handler(adapter)

        result = handler(
            case_def=None,
            givens={"query": "hello"},
            context=EvalContext(),
            stage=None,
            stage_name=None,
            prior_subject=None,
        )

        assert isinstance(result, Subject)
        assert result.output == "fake response"
        assert adapter.last_input is not None
        assert adapter.last_input.query == "hello"

    def test_extracts_query_from_givens(self) -> None:
        adapter = FakeAdapter()
        handler = adapter_as_handler(adapter)

        handler(givens={"a query": "test query"})

        assert adapter.last_input is not None
        assert adapter.last_input.query == "test query"


# ---------------------------------------------------------------------------
# CustomAdapter tests
# ---------------------------------------------------------------------------


class TestCustomAdapter:
    def test_loads_module_and_class(self) -> None:
        mock_adapter_instance = FakeAdapter()
        mock_cls = MagicMock(return_value=mock_adapter_instance)
        mock_module = MagicMock()
        mock_module.MyAdapter = mock_cls

        agent_def = {
            "name": "custom-test",
            "protocol": "custom",
            "connection": {
                "module": "fake_module",
                "class": "MyAdapter",
                "config": {"key": "val"},
            },
        }

        with patch("importlib.import_module", return_value=mock_module):
            from beval.adapters.custom import CustomAdapter

            adapter = CustomAdapter(agent_def)
            mock_cls.assert_called_once_with({"key": "val"})

            # Verify delegation
            inp = AdapterInput(query="hi", givens={}, context=EvalContext())
            result = adapter.invoke(inp)
            assert result.output == "fake response"

    def test_missing_module(self) -> None:
        agent_def = {
            "protocol": "custom",
            "connection": {"module": "nonexistent_xyz_123", "class": "X"},
        }
        with pytest.raises(SystemExit) as exc_info:
            from beval.adapters.custom import CustomAdapter

            CustomAdapter(agent_def)
        assert exc_info.value.code == 2

    def test_missing_class(self) -> None:
        mock_module = MagicMock(spec=[])  # empty module
        agent_def = {
            "protocol": "custom",
            "connection": {"module": "fake", "class": "Missing"},
        }
        with patch("importlib.import_module", return_value=mock_module):
            with pytest.raises(SystemExit) as exc_info:
                from beval.adapters.custom import CustomAdapter

                CustomAdapter(agent_def)
            assert exc_info.value.code == 2

    def test_no_module_or_class(self) -> None:
        agent_def = {"protocol": "custom", "connection": {}}
        with pytest.raises(SystemExit) as exc_info:
            from beval.adapters.custom import CustomAdapter

            CustomAdapter(agent_def)
        assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# ACP adapter tests (mocked SDK)
# ---------------------------------------------------------------------------


class TestACPAdapter:
    def test_invoke_stdio(self) -> None:
        from beval.adapters.acp import ACPAdapter

        adapter = ACPAdapter(
            {
                "name": "acp-test",
                "protocol": "acp",
                "connection": {
                    "transport": "stdio",
                    "command": ["echo", "hi"],
                },
                "timeout": 5,
            }
        )

        # Mock the async invoke
        mock_response = MagicMock()
        mock_response.text = "agent response"

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "sess-1"

        import asyncio

        async def mock_new_session():
            return mock_session

        async def mock_prompt(query, session_id=None, on_text_chunk=None):
            return mock_response

        async def mock_spawn(client, command, env=None):
            return MagicMock()

        mock_client.new_session = mock_new_session
        mock_client.prompt = mock_prompt

        with patch("beval.adapters.acp.ACPAdapter._invoke_async") as mock_invoke:

            async def fake_invoke(query: str) -> str:
                return "mocked output"

            mock_invoke.side_effect = fake_invoke

            inp = AdapterInput(query="test", givens={}, context=EvalContext())
            result = adapter.invoke(inp)

            assert isinstance(result, Subject)
            assert result.output == "mocked output"
            assert result.completion_time > 0

        adapter.close()

    def test_retry_on_error(self) -> None:
        from beval.adapters.acp import ACPAdapter

        adapter = ACPAdapter(
            {
                "name": "retry-test",
                "protocol": "acp",
                "connection": {"transport": "stdio", "command": ["x"]},
                "retry": {"max_attempts": 2, "backoff": 0.01},
            }
        )

        call_count = 0

        async def failing_invoke(query: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("fail")
            return "ok"

        with patch.object(adapter, "_invoke_async", side_effect=failing_invoke):
            inp = AdapterInput(query="test", givens={}, context=EvalContext())
            result = adapter.invoke(inp)
            assert result.output == "ok"
            assert call_count == 2

        adapter.close()

    def test_no_retry_on_auth_error(self) -> None:
        from beval.adapters.acp import ACPAdapter

        adapter = ACPAdapter(
            {
                "name": "auth-test",
                "protocol": "acp",
                "connection": {"transport": "stdio", "command": ["x"]},
                "retry": {"max_attempts": 3, "backoff": 0.01},
            }
        )

        call_count = 0

        async def auth_failing(query: str) -> str:
            nonlocal call_count
            call_count += 1
            raise PermissionError("auth denied")

        with patch.object(adapter, "_invoke_async", side_effect=auth_failing):
            inp = AdapterInput(query="test", givens={}, context=EvalContext())
            with pytest.raises(RuntimeError, match="auth"):
                adapter.invoke(inp)
            # Should not retry on auth error
            assert call_count == 1

        adapter.close()


# ---------------------------------------------------------------------------
# A2A adapter tests (mocked SDK)
# ---------------------------------------------------------------------------


class TestA2AAdapter:
    def test_invoke(self) -> None:
        from beval.adapters.a2a import A2AAdapter

        adapter = A2AAdapter(
            {
                "name": "a2a-test",
                "protocol": "a2a",
                "connection": {
                    "url": "https://agent.example.com",
                    "streaming": False,
                },
                "timeout": 5,
            }
        )

        async def fake_invoke(query: str) -> str:
            return "a2a response"

        with patch.object(adapter, "_invoke_async", side_effect=fake_invoke):
            inp = AdapterInput(query="test", givens={}, context=EvalContext())
            result = adapter.invoke(inp)

            assert isinstance(result, Subject)
            assert result.output == "a2a response"
            assert result.metadata["adapter"] == "a2a"

        adapter.close()


# ---------------------------------------------------------------------------
# CLI --agent integration tests
# ---------------------------------------------------------------------------


class TestCLIAgent:
    def test_agent_flag_loads_adapter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Integration test: --agent flag resolves and uses an adapter."""
        from beval.cli import main

        # Write a case file
        cases_path = tmp_path / "cases.yaml"
        cases_path.write_text(
            yaml.dump(
                {
                    "cases": [
                        {
                            "id": "t1",
                            "name": "Test",
                            "category": "test",
                            "given": {"query": "hello"},
                            "grades": [
                                {
                                    "criterion": "c",
                                    "score": 1.0,
                                    "metric": "quality",
                                    "layer": "deterministic",
                                    "passed": True,
                                    "detail": "ok",
                                }
                            ],
                        }
                    ]
                }
            )
        )

        # Write an agent file
        agent_path = tmp_path / "agent.yaml"
        agent_path.write_text(
            yaml.dump(
                {
                    "name": "cli-test-agent",
                    "protocol": "custom",
                    "connection": {
                        "module": "fake_mod",
                        "class": "FakeClass",
                    },
                }
            )
        )

        # Mock the adapter loading to avoid real module import
        fake_adapter = FakeAdapter()
        with patch("beval.adapters.create_adapter", return_value=fake_adapter):
            with patch("beval.adapters.load_agent") as mock_load:
                mock_load.return_value = {
                    "name": "cli-test-agent",
                    "protocol": "custom",
                    "connection": {},
                }
                # The case uses pre-resolved grades so handler is not actually called
                # but the agent info should appear in config
                exit_code = main(
                    ["run", "--cases", str(cases_path), "--agent", str(agent_path)]
                )
                assert exit_code == 0
                mock_load.assert_called_once()

    def test_beval_agent_env_var(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BEVAL_AGENT env var is picked up as fallback."""
        from beval.cli import _handle_env_overrides

        import argparse

        ns = argparse.Namespace(agent=None, mode="dev", output=None,
                                trials=1, cases=None, subject=None,
                                judge_model=None, no_color=False)
        monkeypatch.setenv("BEVAL_AGENT", "env-agent")
        _handle_env_overrides(ns)
        assert ns.agent == "env-agent"


# ---------------------------------------------------------------------------
# RunConfig.agent field tests
# ---------------------------------------------------------------------------


class TestRunConfigAgent:
    def test_agent_field_default_none(self) -> None:
        from beval.types import RunConfig

        config = RunConfig()
        assert config.agent is None

    def test_agent_field_set(self) -> None:
        from beval.types import RunConfig

        config = RunConfig(agent={"name": "x", "protocol": "acp"})
        assert config.agent == {"name": "x", "protocol": "acp"}


# ---------------------------------------------------------------------------
# Reporter strips agent=None
# ---------------------------------------------------------------------------


class TestReporterAgentField:
    def test_agent_none_stripped(self) -> None:
        from beval.reporter import _strip_defaults

        d = {
            "grade_pass_threshold": 0.5,
            "case_pass_threshold": 0.7,
            "agent": None,
        }
        result = _strip_defaults(d)
        assert "agent" not in result

    def test_agent_present_kept(self) -> None:
        from beval.reporter import _strip_defaults

        d = {
            "grade_pass_threshold": 0.5,
            "case_pass_threshold": 0.7,
            "agent": {"name": "x", "protocol": "acp"},
        }
        result = _strip_defaults(d)
        assert result["agent"] == {"name": "x", "protocol": "acp"}
