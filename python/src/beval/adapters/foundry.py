"""Foundry Agent Service adapter. See SPEC §13.4.

Uses the ``azure-ai-projects`` SDK with Entra ID authentication.
Requires ``azure-ai-projects`` and ``azure-identity`` packages.
"""

from __future__ import annotations

import time
from typing import Any

from beval.adapters import AdapterInput, AdapterInterface
from beval.types import Subject


class FoundryAdapter(AdapterInterface):
    """Adapter for Microsoft Foundry prompt agents.

    Uses ``AIProjectClient`` from the ``azure-ai-projects`` SDK to invoke
    agents via the OpenAI-compatible Responses API.

    Configuration (``connection`` keys):
      - ``endpoint``: Foundry project endpoint (required)
      - ``agent_name``: Name of the Foundry agent to invoke
      - ``model``: Fallback model when agent_name is not set (default: gpt-4o)
    """

    def __init__(self, agent_def: dict[str, Any]) -> None:
        try:
            from azure.ai.projects import AIProjectClient
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise ImportError(
                "Foundry adapter requires azure-ai-projects and azure-identity. "
                "Install with: pip install beval[foundry]"
            ) from exc

        connection = agent_def.get("connection", {})
        config = connection.get("config", connection)
        endpoint = config.get("endpoint")
        if not endpoint:
            import sys

            print(
                "Error: set FOUNDRY_PROJECT_ENDPOINT "
                "(adapter config 'endpoint' is required).",
                file=sys.stderr,
            )
            raise SystemExit(2)

        self._agent_name = config.get("agent_name")
        self._model = config.get("model", "gpt-4o")
        self._timeout = agent_def.get("timeout", 60)
        self._credential = DefaultAzureCredential()
        self._client = AIProjectClient(
            endpoint=endpoint,
            credential=self._credential,
        )
        self._openai = self._client.get_openai_client()
        self._conversation_id: str | None = None

    def invoke(self, adapter_input: AdapterInput) -> Subject:
        from azure.core.exceptions import ClientAuthenticationError

        query = adapter_input.query
        if isinstance(query, list):
            query = " ".join(
                m.get("content", "") for m in query if isinstance(m, dict)
            )

        start = time.monotonic()

        kwargs: dict[str, Any] = {"input": query}

        if self._agent_name:
            kwargs["extra_body"] = {
                "agent_reference": {
                    "name": self._agent_name,
                    "type": "agent_reference",
                }
            }
        else:
            kwargs["model"] = self._model

        if self._conversation_id:
            kwargs["conversation"] = self._conversation_id

        try:
            response = self._openai.responses.create(**kwargs)
        except ClientAuthenticationError as exc:
            import sys

            print(
                "Error: authentication failed when calling Foundry "
                "(run 'az login' and ensure you have access to the project).",
                file=sys.stderr,
            )
            raise SystemExit(3) from exc
        except TimeoutError as exc:
            raise RuntimeError(f"Foundry API timed out: {exc}") from exc

        elapsed = time.monotonic() - start

        if hasattr(response, "conversation") and response.conversation:
            self._conversation_id = response.conversation

        output_text = getattr(response, "output_text", "") or ""

        return Subject(
            input=query,
            output=output_text,
            completion_time=elapsed,
            metadata={
                "response_id": getattr(response, "id", None),
                "model": getattr(response, "model", self._model),
                "agent_name": self._agent_name,
            },
        )

    def close(self) -> None:
        if self._conversation_id:
            try:
                self._openai.conversations.delete(self._conversation_id)
            except Exception:  # noqa: S110, BLE001
                pass
        self._client.close()
        self._credential.close()
