"""Tests for the agent adapter system. See SPEC §13."""

from __future__ import annotations

import os
from pathlib import Path
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
        p.write_text(yaml.dump({"name": "x", "protocol": "unknown", "connection": {}}))
        with pytest.raises(SystemExit) as exc_info:
            load_agent(str(p))
        assert exc_info.value.code == 2

    def test_env_var_resolution(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
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

    def test_env_var_default_used(self, tmp_path: Path) -> None:
        """${VAR:-default} uses default when VAR is unset."""
        p = tmp_path / "env.yaml"
        p.write_text(
            yaml.dump(
                {
                    "name": "env-agent",
                    "protocol": "custom",
                    "connection": {
                        "module": "mod",
                        "class": "Cls",
                        "host": "${BEVAL_TEST_HOST:-127.0.0.1}",
                        "port": "${BEVAL_TEST_PORT:-3000}",
                    },
                }
            )
        )
        os.environ.pop("BEVAL_TEST_HOST", None)
        os.environ.pop("BEVAL_TEST_PORT", None)
        result = load_agent(str(p))
        assert result["connection"]["host"] == "127.0.0.1"
        assert result["connection"]["port"] == "3000"

    def test_env_var_default_overridden(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """${VAR:-default} uses env value when VAR is set."""
        monkeypatch.setenv("BEVAL_TEST_HOST", "10.0.0.1")
        p = tmp_path / "env.yaml"
        p.write_text(
            yaml.dump(
                {
                    "name": "env-agent",
                    "protocol": "custom",
                    "connection": {
                        "module": "mod",
                        "class": "Cls",
                        "host": "${BEVAL_TEST_HOST:-127.0.0.1}",
                    },
                }
            )
        )
        result = load_agent(str(p))
        assert result["connection"]["host"] == "10.0.0.1"

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
            create_adapter(agent_def)
            mock_cls.assert_called_once_with(agent_def, auto_approve=False)

    def test_dispatches_a2a(self) -> None:
        agent_def = {
            "name": "a",
            "protocol": "a2a",
            "connection": {"url": "http://x"},
        }
        with patch("beval.adapters.a2a.A2AAdapter") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_adapter(agent_def)
            mock_cls.assert_called_once_with(agent_def)

    def test_dispatches_custom(self) -> None:
        agent_def = {
            "name": "a",
            "protocol": "custom",
            "connection": {"module": "m", "class": "C"},
        }
        with patch("beval.adapters.custom.CustomAdapter") as mock_cls:
            mock_cls.return_value = MagicMock()
            create_adapter(agent_def)
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

    def test_build_httpx_client_no_auth(self) -> None:
        """No auth produces a plain httpx client with no extra headers."""
        from beval.adapters.a2a import A2AAdapter

        adapter = A2AAdapter(
            {
                "name": "a2a-test",
                "protocol": "a2a",
                "connection": {"url": "https://agent.example.com"},
            }
        )

        client = adapter._build_httpx_client()
        # No Authorization header injected
        assert "Authorization" not in client.headers
        # AsyncClient uses aclose(); skip in sync test

    def test_build_httpx_client_api_key(self) -> None:
        """api_key auth injects the configured header."""
        from beval.adapters.a2a import A2AAdapter

        adapter = A2AAdapter(
            {
                "name": "a2a-test",
                "protocol": "a2a",
                "connection": {
                    "url": "https://agent.example.com",
                    "auth": {
                        "type": "api_key",
                        "header": "X-Api-Key",
                        "value": "secret-123",
                    },
                },
            }
        )

        client = adapter._build_httpx_client()
        assert client.headers["X-Api-Key"] == "secret-123"
        # AsyncClient uses aclose(); skip in sync test

    def test_build_httpx_client_bearer(self) -> None:
        """bearer auth uses DefaultAzureCredential and injects Authorization header."""
        from beval.adapters.a2a import A2AAdapter

        adapter = A2AAdapter(
            {
                "name": "a2a-test",
                "protocol": "a2a",
                "connection": {
                    "url": "https://agent.example.com",
                    "auth": {
                        "type": "bearer",
                        "scope": "https://my-scope/.default",
                    },
                },
            }
        )

        mock_credential = MagicMock()
        mock_token_provider = MagicMock(return_value="fake-token-xyz")

        with patch("beval.adapters.a2a.A2AAdapter._build_httpx_client"):
            # Call the real method but with mocked azure deps
            pass

        # Test by mocking the azure.identity imports
        with patch.dict(
            "sys.modules",
            {
                "azure": MagicMock(),
                "azure.identity": MagicMock(
                    DefaultAzureCredential=MagicMock(return_value=mock_credential),
                    get_bearer_token_provider=MagicMock(
                        return_value=mock_token_provider
                    ),
                ),
            },
        ):
            # Call the real _build_httpx_client
            client = A2AAdapter._build_httpx_client(adapter)
            assert client.headers["Authorization"] == "Bearer fake-token-xyz"
            # AsyncClient uses aclose(); skip in sync test

    def test_invoke_async_failure_raises(self) -> None:
        """ClientFactory.connect failure raises RuntimeError via invoke."""
        from beval.adapters.a2a import A2AAdapter

        adapter = A2AAdapter(
            {
                "name": "a2a-test",
                "protocol": "a2a",
                "connection": {"url": "https://agent.example.com"},
                "retry": {"max_attempts": 1},
            }
        )

        async def mock_invoke_async(query):
            raise ConnectionError("Cannot reach agent")

        with patch.object(adapter, "_invoke_async", mock_invoke_async):
            with pytest.raises(RuntimeError, match="Cannot reach agent"):
                adapter.invoke(
                    AdapterInput(
                        query="hello",
                        stage=1,
                        stage_name="test",
                        givens={},
                        context=EvalContext(),
                    )
                )

    def test_send_message_extracts_text(self) -> None:
        """Verify text is extracted from Message response parts."""
        import asyncio

        from a2a.types import Message, Part, Role, TextPart

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

        response_message = Message(
            message_id="test-id",
            role=Role.agent,
            parts=[Part(root=TextPart(text="response text"))],
        )

        mock_client = MagicMock()

        async def mock_send_message(**kwargs):
            yield response_message

        mock_client.send_message = mock_send_message

        async def mock_connect(*args, **kwargs):
            return mock_client

        mock_httpx = MagicMock()

        async def mock_aclose():
            pass

        mock_httpx.aclose = mock_aclose

        with patch("a2a.client.ClientFactory.connect", mock_connect):
            with patch.object(adapter, "_build_httpx_client", return_value=mock_httpx):
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(adapter._invoke_async("hello"))
                    assert result == "response text"
                finally:
                    loop.close()


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
        import argparse

        from beval.cli import _handle_env_overrides

        ns = argparse.Namespace(
            agent=None,
            mode="dev",
            output=None,
            trials=1,
            cases=None,
            subject=None,
            judge_model=None,
            no_color=False,
        )
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


# ---------------------------------------------------------------------------
# Permission policy tests (_EvalClient allow-list)
# ---------------------------------------------------------------------------


class TestPermissionPolicy:
    """Tests for _EvalClient's tool permission allow-list."""

    @pytest.fixture()
    def _mock_acp_schema(self):
        """Ensure ACP schema types are importable."""
        pytest.importorskip("acp.schema")

    def _make_tool_call(self, title: str) -> MagicMock:
        tc = MagicMock()
        tc.title = title
        tc.tool_call_id = "tc-1"
        return tc

    def _make_options(self) -> list[MagicMock]:
        opt = MagicMock()
        opt.option_id = "allow_once"
        opt.kind = "allow"
        return [opt]

    @pytest.mark.usefixtures("_mock_acp_schema")
    def test_default_denies_all(self) -> None:
        """No allow_tools → deny all tool calls."""
        import asyncio

        from acp.schema import DeniedOutcome

        from beval.adapters.acp import _EvalClient

        client = _EvalClient()  # default: allow_tools=None
        tc = self._make_tool_call("web_search")
        result = asyncio.run(
            client.request_permission(self._make_options(), "s1", tc)
        )
        assert isinstance(result.outcome, DeniedOutcome)

    @pytest.mark.usefixtures("_mock_acp_schema")
    def test_wildcard_approves_all(self) -> None:
        """allow_tools=["*"] approves every tool call."""
        import asyncio

        from acp.schema import AllowedOutcome

        from beval.adapters.acp import _EvalClient

        client = _EvalClient(allow_tools=["*"])
        tc = self._make_tool_call("anything")
        result = asyncio.run(
            client.request_permission(self._make_options(), "s1", tc)
        )
        assert isinstance(result.outcome, AllowedOutcome)

    @pytest.mark.usefixtures("_mock_acp_schema")
    def test_pattern_match_approves(self) -> None:
        """Glob pattern matches the tool title."""
        import asyncio

        from acp.schema import AllowedOutcome

        from beval.adapters.acp import _EvalClient

        client = _EvalClient(allow_tools=["web_*"])
        tc = self._make_tool_call("web_search")
        result = asyncio.run(
            client.request_permission(self._make_options(), "s1", tc)
        )
        assert isinstance(result.outcome, AllowedOutcome)

    @pytest.mark.usefixtures("_mock_acp_schema")
    def test_pattern_mismatch_denies(self) -> None:
        """Tool title not matching any pattern is denied."""
        import asyncio

        from acp.schema import DeniedOutcome

        from beval.adapters.acp import _EvalClient

        client = _EvalClient(allow_tools=["web_*"])
        tc = self._make_tool_call("delete_file")
        result = asyncio.run(
            client.request_permission(self._make_options(), "s1", tc)
        )
        assert isinstance(result.outcome, DeniedOutcome)

    def test_auto_approve_overrides_config(self) -> None:
        """ACPAdapter with auto_approve=True ignores config allow_tools."""
        from beval.adapters.acp import ACPAdapter

        adapter = ACPAdapter(
            {
                "name": "test",
                "protocol": "acp",
                "connection": {"transport": "stdio", "command": ["echo"]},
                "permissions": {"allow_tools": []},  # would deny all
            },
            auto_approve=True,
        )
        assert adapter._client._allow_tools == ["*"]

    def test_config_allow_tools_read(self) -> None:
        """ACPAdapter reads allow_tools from agent_def permissions."""
        from beval.adapters.acp import ACPAdapter

        adapter = ACPAdapter(
            {
                "name": "test",
                "protocol": "acp",
                "connection": {"transport": "stdio", "command": ["echo"]},
                "permissions": {"allow_tools": ["read_*", "search"]},
            },
        )
        assert adapter._client._allow_tools == ["read_*", "search"]
