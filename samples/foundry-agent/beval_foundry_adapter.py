"""beval custom adapter for Microsoft Foundry Agent Service."""

from __future__ import annotations

import time
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.identity import DefaultAzureCredential

from beval.adapters import AdapterInput, AdapterInterface
from beval.types import Subject


class FoundryAdapter(AdapterInterface):
    """Connects beval to a Microsoft Foundry prompt agent."""

    def __init__(self, config: dict[str, Any]) -> None:
        endpoint = config.get("endpoint")
        if not endpoint:
            import sys

            print(
                "Error: set FOUNDRY_PROJECT_ENDPOINT (adapter config 'endpoint' is required).",
                file=sys.stderr,
            )
            raise SystemExit(2)

        self._agent_name = config.get("agent_name")
        self._model = config.get("model", "gpt-4o")
        self._credential = DefaultAzureCredential()
        self._client = AIProjectClient(
            endpoint=endpoint,
            credential=self._credential,
        )
        self._openai = self._client.get_openai_client()
        self._conversation_id: str | None = None

    def invoke(self, adapter_input: AdapterInput) -> Subject:
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
            raise SystemExit(3) from exc
        except HttpResponseError as exc:
            raise RuntimeError(
                f"Foundry API error (status {exc.status_code}): {exc.message}"
            ) from exc
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
