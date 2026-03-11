"""Tests for LLM judge. See SPEC §10."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

from beval.judge import LLMJudge, NullJudge
from beval.types import GraderLayer


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
