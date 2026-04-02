"""Tests for LLM judge. See SPEC §10 and spec/judges.spec.md §14."""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

from beval.judge import (
    ACPJudge,
    LLMJudge,
    NullJudge,
    _ACPJudgeClient,
    _extract_json,
    load_judge_from_config,
)
from beval.types import GraderLayer


class TestExtractJson:
    def test_clean_json(self):
        assert _extract_json('{"score": 0.5}') == '{"score": 0.5}'

    def test_info_prefix_lines(self):
        raw = 'Info: Retrying...\n{"score": 0.8}'
        assert _extract_json(raw) == '{"score": 0.8}'

    def test_nested_braces(self):
        raw = 'prefix {"a": {"b": 1}} suffix'
        assert _extract_json(raw) == '{"a": {"b": 1}}'

    def test_no_json_returns_original(self):
        assert _extract_json("no braces here") == "no braces here"


class TestNullJudge:
    def test_returns_skipped_grade(self):
        judge = NullJudge()
        grade = judge.evaluate("criterion", "answer")
        assert grade.skipped is True
        assert grade.score == 0.0
        assert grade.layer == GraderLayer.AI_JUDGED


class TestLLMJudge:
    @patch("openai.OpenAI")
    def test_evaluate_success(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {"score": 0.85, "reasoning": "Good answer with details."}
        )
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o", grade_pass_threshold=0.5)
        grade = judge.evaluate(
            "the answer should be comprehensive",
            "Here is a detailed answer about materials.",
            context={"input": "What materials?"},
        )

        assert grade.score == 0.85
        assert grade.passed is True
        assert grade.layer == GraderLayer.AI_JUDGED
        assert "Good answer" in grade.detail
        assert grade.skipped is not True

        # Verify API was called with correct model
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"

    @patch("openai.OpenAI")
    def test_evaluate_low_score_fails(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {"score": 0.3, "reasoning": "Missing key details."}
        )
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o", grade_pass_threshold=0.5)
        grade = judge.evaluate("criterion", "bad answer")

        assert grade.score == 0.3
        assert grade.passed is False

    @patch("openai.OpenAI")
    def test_evaluate_clamps_score(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {"score": 1.5, "reasoning": "Over the top."}
        )
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o")
        grade = judge.evaluate("criterion", "answer")
        assert grade.score == 1.0

    @patch("openai.OpenAI")
    def test_evaluate_handles_markdown_fences(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = '```json\n{"score": 0.9, "reasoning": "Great."}\n```'
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o")
        grade = judge.evaluate("criterion", "answer")
        assert grade.score == 0.9

    @patch("openai.OpenAI")
    def test_evaluate_handles_invalid_json(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json at all"
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o")
        grade = judge.evaluate("criterion", "answer")
        assert grade.score == 0.0
        assert grade.passed is False
        assert "Invalid judge response" in grade.detail

    @patch("openai.OpenAI")
    def test_evaluate_salvages_truncated_json(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '```json\n{"score": 0.45, "reasoning": '
            '"The answer partially meets the criterion but'
        )
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o")
        grade = judge.evaluate("criterion", "answer")
        assert grade.score == 0.45
        assert "(truncated)" in grade.detail

    @patch("openai.OpenAI")
    def test_evaluate_handles_api_error(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        judge = LLMJudge("gpt-4o")
        grade = judge.evaluate("criterion", "answer")
        assert grade.score == 0.0
        assert "Judge error" in grade.detail

    @patch("openai.OpenAI")
    def test_prompt_contains_answer_tags(self, mock_openai_cls):
        """SPEC §10.3: delimit evaluated content in judge prompts."""
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {"score": 0.8, "reasoning": "ok"}
        )
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o")
        judge.evaluate("criterion", "my answer text", context={"input": "question"})

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_msg = messages[1]["content"]
        assert "<answer>" in user_msg
        assert "</answer>" in user_msg
        assert "my answer text" in user_msg


class TestLLMJudgeAzure:
    @patch.dict(
        os.environ,
        {
            "AZURE_OPENAI_ENDPOINT": "https://myresource.openai.azure.com",
            "AZURE_OPENAI_API_KEY": "test-key",
        },
        clear=False,
    )
    @patch("openai.AzureOpenAI")
    @patch("openai.OpenAI")
    def test_azure_api_key_auth(self, mock_openai_cls, mock_azure_cls):
        mock_azure_cls.return_value = MagicMock()
        LLMJudge("gpt-4o")
        mock_azure_cls.assert_called_once_with(
            api_key="test-key",
            azure_endpoint="https://myresource.openai.azure.com",
            api_version="2024-12-01-preview",
        )
        mock_openai_cls.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "AZURE_OPENAI_ENDPOINT": "https://myresource.openai.azure.com",
        },
        clear=False,
    )
    @patch("openai.AzureOpenAI")
    @patch("openai.OpenAI")
    def test_azure_entra_id_auth(self, mock_openai_cls, mock_azure_cls):
        mock_azure_cls.return_value = MagicMock()
        mock_cred = MagicMock()
        mock_provider = MagicMock()
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": ""}, clear=False):
            os.environ.pop("AZURE_OPENAI_API_KEY", None)
            with (
                patch("azure.identity.DefaultAzureCredential", return_value=mock_cred),
                patch(
                    "azure.identity.get_bearer_token_provider",
                    return_value=mock_provider,
                ) as mock_get_token,
            ):
                LLMJudge("gpt-4o")
                mock_get_token.assert_called_once_with(
                    mock_cred,
                    "https://cognitiveservices.azure.com/.default",
                )
                mock_azure_cls.assert_called_once_with(
                    azure_ad_token_provider=mock_provider,
                    azure_endpoint="https://myresource.openai.azure.com",
                    api_version="2024-12-01-preview",
                )
                mock_openai_cls.assert_not_called()

    @patch.dict(os.environ, {}, clear=False)
    @patch("openai.AzureOpenAI")
    @patch("openai.OpenAI")
    def test_standard_openai_when_no_azure_env(self, mock_openai_cls, mock_azure_cls):
        """Falls back to standard OpenAI() when no AZURE_OPENAI_ENDPOINT."""
        mock_openai_cls.return_value = MagicMock()
        # Ensure no Azure env vars
        env = os.environ.copy()
        env.pop("AZURE_OPENAI_ENDPOINT", None)
        with patch.dict(os.environ, env, clear=True):
            LLMJudge("gpt-4o")
            mock_openai_cls.assert_called_once_with()
            mock_azure_cls.assert_not_called()


class TestLLMJudgeExplicitConfig:
    """Tests for LLMJudge with explicit config params (protocol: openai §14.3)."""

    @patch("openai.OpenAI")
    def test_explicit_api_key_and_base_url(self, mock_openai_cls):
        mock_openai_cls.return_value = MagicMock()
        LLMJudge("gpt-4o", api_key="sk-test", base_url="https://proxy.example.com/v1")
        mock_openai_cls.assert_called_once_with(
            api_key="sk-test", base_url="https://proxy.example.com/v1"
        )

    @patch("openai.OpenAI")
    def test_max_answer_chars_truncates(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {"score": 0.7, "reasoning": "ok"}
        )
        mock_client.chat.completions.create.return_value = mock_response

        judge = LLMJudge("gpt-4o", max_answer_chars=10)
        long_answer = "A" * 100
        judge.evaluate("criterion", long_answer, context={"input": "q"})

        call_kwargs = mock_client.chat.completions.create.call_args
        user_msg = call_kwargs.kwargs["messages"][1]["content"]
        # Only first 10 chars of answer should appear between answer tags
        assert "A" * 10 in user_msg
        assert "A" * 11 not in user_msg

    @patch("openai.AzureOpenAI")
    @patch("openai.OpenAI")
    def test_explicit_entra_id_auth(self, mock_openai_cls, mock_azure_cls):
        mock_azure_cls.return_value = MagicMock()
        mock_cred = MagicMock()
        mock_provider = MagicMock()
        with (
            patch("azure.identity.DefaultAzureCredential", return_value=mock_cred),
            patch(
                "azure.identity.get_bearer_token_provider",
                return_value=mock_provider,
            ),
        ):
            LLMJudge(
                "gpt-4o",
                base_url="https://myresource.openai.azure.com",
                auth="entra_id",
            )
            mock_azure_cls.assert_called_once_with(
                azure_ad_token_provider=mock_provider,
                azure_endpoint="https://myresource.openai.azure.com",
                api_version="2024-12-01-preview",
            )
            mock_openai_cls.assert_not_called()


class TestLoadJudgeFromConfig:
    """Tests for load_judge_from_config factory (§14.4)."""

    @patch("openai.OpenAI")
    def test_openai_protocol(self, mock_openai_cls):
        mock_openai_cls.return_value = MagicMock()
        judge = load_judge_from_config(
            {"protocol": "openai", "model": "gpt-4o", "api_key": "sk-test"}
        )
        assert isinstance(judge, LLMJudge)

    def test_acp_protocol(self):
        judge = load_judge_from_config(
            {
                "protocol": "acp",
                "connection": {"transport": "stdio", "command": ["copilot", "--acp"]},
                "timeout": 60,
            }
        )
        assert isinstance(judge, ACPJudge)

    @patch.dict(os.environ, {"MY_API_KEY": "resolved-key"})
    @patch("openai.OpenAI")
    def test_resolves_env_vars(self, mock_openai_cls):
        mock_openai_cls.return_value = MagicMock()
        judge = load_judge_from_config(
            {"protocol": "openai", "model": "gpt-4o", "api_key": "${MY_API_KEY}"}
        )
        assert isinstance(judge, LLMJudge)
        # The resolved key should have been passed to OpenAI
        mock_openai_cls.assert_called_once_with(api_key="resolved-key")

    def test_resolves_env_var_with_default(self):
        judge = load_judge_from_config(
            {
                "protocol": "acp",
                "connection": {
                    "transport": "tcp",
                    "host": "${JUDGE_HOST:-127.0.0.1}",
                    "port": "${JUDGE_PORT:-3001}",
                },
            }
        )
        assert isinstance(judge, ACPJudge)

    def test_missing_env_var_raises(self):
        import pytest

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing environment variable"):
                load_judge_from_config(
                    {
                        "protocol": "openai",
                        "model": "gpt-4o",
                        "api_key": "${NONEXISTENT_VAR}",
                    }
                )

    def test_unknown_protocol_raises(self):
        import pytest

        with pytest.raises(ValueError, match="Unknown judge protocol"):
            load_judge_from_config({"protocol": "unknown"})

    def test_openai_missing_model_raises(self):
        import pytest

        with pytest.raises(ValueError, match="model is required"):
            load_judge_from_config({"protocol": "openai"})

    def test_acp_missing_connection_raises(self):
        import pytest

        with pytest.raises(ValueError, match="connection is required"):
            load_judge_from_config({"protocol": "acp"})


class TestACPJudge:
    """Tests for ACPJudge (§14.2)."""

    def _make_mock_acp(self):
        """Build mock ACP module objects."""
        mock_acp = MagicMock()
        mock_acp.PROTOCOL_VERSION = "1.0"
        mock_acp.text_block = lambda t: t

        mock_conn = MagicMock()
        mock_conn.initialize = AsyncMock()
        mock_conn.new_session = AsyncMock(return_value=MagicMock(session_id="sess-123"))
        mock_conn.prompt = AsyncMock()
        mock_conn.close = AsyncMock()

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=(mock_conn, MagicMock()))
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_acp.spawn_agent_process = MagicMock(return_value=mock_ctx)
        return mock_acp, mock_conn

    def test_evaluate_success(self):
        judge = ACPJudge(
            {"transport": "stdio", "command": ["copilot", "--acp"]},
            grade_pass_threshold=0.5,
            timeout=30,
        )
        response_json = json.dumps({"score": 0.8, "reasoning": "Good answer."})

        with patch.object(judge, "_evaluate_sync", return_value=response_json):
            grade = judge.evaluate(
                "the answer should be relevant",
                "My answer",
                context={"input": "What is X?"},
            )

        assert grade.score == 0.8
        assert grade.passed is True
        assert grade.detail == "Good answer."
        assert grade.skipped is not True

    def test_evaluate_fresh_session_per_call(self):
        """Each evaluate() creates a new session (§14.2.4)."""
        judge = ACPJudge(
            {"transport": "stdio", "command": ["copilot", "--acp"]},
            timeout=30,
        )
        response_json = json.dumps({"score": 0.7, "reasoning": "ok"})

        with patch.object(
            judge,
            "_evaluate_sync",
            return_value=response_json,
        ) as mock_sync:
            judge.evaluate("crit", "answer1")
            judge.evaluate("crit", "answer2")
            assert mock_sync.call_count == 2

        # Confirm no session ID is cached between calls (unlike the ACP adapter)
        assert not hasattr(judge, "_session_id")

    def test_evaluate_api_error_returns_score_zero(self):
        judge = ACPJudge(
            {"transport": "stdio", "command": ["copilot", "--acp"]},
            timeout=30,
        )
        with patch.object(judge, "_evaluate_sync", side_effect=RuntimeError("timeout")):
            grade = judge.evaluate("criterion", "answer")

        assert grade.score == 0.0
        assert grade.passed is False
        assert "Judge error" in grade.detail
        assert grade.skipped is not True

    def test_parse_response_invalid_json(self):
        judge = ACPJudge({"transport": "stdio", "command": ["copilot"]}, timeout=30)
        grade = judge._parse_response("not json", "criterion")
        assert grade.score == 0.0
        assert "Invalid judge response" in grade.detail

    def test_parse_response_clamps_score(self):
        judge = ACPJudge({"transport": "stdio", "command": ["copilot"]}, timeout=30)
        grade = judge._parse_response(
            json.dumps({"score": 2.5, "reasoning": "too high"}), "criterion"
        )
        assert grade.score == 1.0

    def test_parse_response_strips_markdown_fences(self):
        judge = ACPJudge({"transport": "stdio", "command": ["copilot"]}, timeout=30)
        raw = '```json\n{"score": 0.6, "reasoning": "ok"}\n```'
        grade = judge._parse_response(raw, "criterion")
        assert grade.score == 0.6

    def test_parse_response_ignores_info_lines_before_json(self):
        """Copilot may emit 'Info: Retrying...' lines before the JSON payload."""
        judge = ACPJudge({"transport": "stdio", "command": ["copilot"]}, timeout=30)
        raw = (
            "Info: Request failed due to a transient API error. Retrying...\n"
            "Info: Request failed due to a transient API error. Retrying...\n"
            '{"score": 0.75, "reasoning": "Good answer."}'
        )
        grade = judge._parse_response(raw, "criterion")
        assert grade.score == 0.75
        assert grade.detail == "Good answer."

    def test_close_is_noop_when_not_connected(self):
        judge = ACPJudge({"transport": "stdio", "command": ["copilot"]}, timeout=30)
        judge.close()  # Should not raise

    def test_combined_prompt_contains_answer(self):
        """ACP judge prompt includes criterion, input, and answer."""
        from beval.judge import _ACP_JUDGE_PROMPT_TEMPLATE

        prompt = _ACP_JUDGE_PROMPT_TEMPLATE.format(
            criterion="the answer should be concise",
            input="What is Python?",
            answer="Python is a language.",
        )
        assert "Python is a language." in prompt
        assert "the answer should be concise" in prompt
        assert "What is Python?" in prompt


class TestACPJudgeClient:
    def test_request_permission_exists(self):
        client = _ACPJudgeClient()
        assert callable(getattr(client, "request_permission", None))

    def test_selects_allow_option_when_present(self):
        mock_allow = MagicMock()
        mock_allow.option_id = "allow_once"
        mock_allow.kind = "allow"
        mock_deny = MagicMock()
        mock_deny.option_id = "deny"
        mock_deny.kind = "deny"

        mock_response = MagicMock()
        mock_outcome = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "acp.schema": MagicMock(
                    AllowedOutcome=MagicMock(return_value=mock_outcome),
                    RequestPermissionResponse=MagicMock(return_value=mock_response),
                ),
            },
        ):
            client = _ACPJudgeClient()
            result = asyncio.run(
                client.request_permission(
                    options=[mock_deny, mock_allow],
                    session_id="s1",
                    tool_call=MagicMock(),
                )
            )

        assert result is mock_response

    def test_falls_back_to_first_option_when_no_allow(self):
        mock_opt = MagicMock()
        mock_opt.option_id = "first"
        mock_opt.kind = "other"

        mock_response = MagicMock()
        mock_outcome = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "acp.schema": MagicMock(
                    AllowedOutcome=MagicMock(return_value=mock_outcome),
                    RequestPermissionResponse=MagicMock(return_value=mock_response),
                ),
            },
        ):
            client = _ACPJudgeClient()
            result = asyncio.run(
                client.request_permission(
                    options=[mock_opt],
                    session_id="s1",
                    tool_call=MagicMock(),
                )
            )

        assert result is mock_response

    def test_returns_none_when_acp_not_installed(self):
        with patch.dict("sys.modules", {"acp.schema": None}):
            client = _ACPJudgeClient()
            result = asyncio.run(
                client.request_permission(
                    options=[],
                    session_id="s1",
                    tool_call=MagicMock(),
                )
            )
        assert result is None
