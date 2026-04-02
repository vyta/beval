"""Minimal A2A agent server — Klingon language tutor using an LLM.

Maintains per-session conversation history keyed by A2A context_id so that
multi-turn conversations stay coherent across calls.
"""

from __future__ import annotations

import argparse
import os
import uuid
from collections import defaultdict
from typing import Any

import uvicorn
from a2a.server.apps.jsonrpc import A2AFastAPIApplication
from a2a.server.request_handlers import RequestHandler
from a2a.server.context import ServerCallContext
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Message,
    MessageSendParams,
    Part,
    Role,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils.errors import ServerError
from openai import AsyncAzureOpenAI, AsyncOpenAI

SYSTEM_PROMPT = """\
You are Mok'tar, a Klingon language tutor serving on a Federation starship.
Your mission is to help humans learn to communicate with Klingons.

Guidelines:
- Respond primarily in Klingon (tlhIngan Hol)
- After each Klingon phrase or sentence, provide the English translation in parentheses
- Be patient but warrior-like — honour those who make the effort to learn
- Build on what was discussed earlier in the conversation
- Teach vocabulary and phrases relevant to what the human wants to accomplish
- When the human attempts Klingon, acknowledge their effort and gently correct if needed
- Use authentic Klingon vocabulary where possible (nuqneH, Qapla', tlhIngan maH, etc.)
"""


def _build_llm_client() -> AsyncOpenAI:
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    if not azure_endpoint:
        return AsyncOpenAI()

    api_key = os.environ.get("AZURE_OPENAI_API_KEY")

    # Azure AI Foundry project endpoints (/v1 path) use the standard OpenAI
    # client — they do not accept api-version query parameters.
    if "/v1" in azure_endpoint or "services.ai.azure.com" in azure_endpoint:
        if api_key:
            return AsyncOpenAI(api_key=api_key, base_url=azure_endpoint)
        # Entra ID: get bearer token for the Foundry scope
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        scope = os.environ.get("AZURE_TOKEN_SCOPE", "https://ai.azure.com/.default")
        token_provider = get_bearer_token_provider(DefaultAzureCredential(), scope)
        return AsyncOpenAI(
            api_key="placeholder",
            base_url=azure_endpoint,
            default_headers={"Authorization": f"Bearer {token_provider()}"},
        )

    # Classic Azure OpenAI (openai.azure.com / cognitiveservices.azure.com)
    # — uses AzureOpenAI with api-version.
    kwargs: dict[str, Any] = {
        "azure_endpoint": azure_endpoint,
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    }
    if api_key:
        kwargs["api_key"] = api_key
    else:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        scope = os.environ.get("AZURE_TOKEN_SCOPE", "https://cognitiveservices.azure.com/.default")
        kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
            DefaultAzureCredential(), scope
        )
    return AsyncAzureOpenAI(**kwargs)


def _get_model() -> str:
    return os.environ.get("KLINGON_MODEL", "o4-mini")


def _extract_text(message: Message) -> str:
    parts = []
    for part in message.parts:
        if hasattr(part, "root") and hasattr(part.root, "text"):
            parts.append(part.root.text)
        elif hasattr(part, "text"):
            parts.append(part.text)
    return "".join(parts)


class KlingonRequestHandler(RequestHandler):
    def __init__(self) -> None:
        self.client = _build_llm_client()
        self.model = _get_model()
        # Per-session history: context_id → list of {"role": ..., "content": ...}
        self._history: dict[str, list[dict[str, str]]] = defaultdict(list)

    async def on_message_send(
        self, params: MessageSendParams, context: ServerCallContext | None = None
    ) -> Message:
        user_text = _extract_text(params.message)
        context_id = params.message.context_id or str(uuid.uuid4())

        # Append user turn to session history
        self._history[context_id].append({"role": "user", "content": user_text})

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self._history[context_id]

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        reply = response.choices[0].message.content or ""

        # Append assistant turn to session history
        self._history[context_id].append({"role": "assistant", "content": reply})

        return Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(text=reply))],
            context_id=context_id,
        )

    async def on_message_send_stream(self, params):
        raise ServerError(UnsupportedOperationError())

    async def on_cancel_task(self, params):
        raise ServerError(UnsupportedOperationError())

    async def on_get_task(self, params):
        raise ServerError(UnsupportedOperationError())

    async def on_set_task_push_notification_config(self, params):
        raise ServerError(UnsupportedOperationError())

    async def on_get_task_push_notification_config(self, params):
        raise ServerError(UnsupportedOperationError())

    async def on_delete_task_push_notification_config(self, params):
        raise ServerError(UnsupportedOperationError())

    async def on_list_task_push_notification_config(self, params):
        raise ServerError(UnsupportedOperationError())

    async def on_resubscribe_to_task(self, params):
        raise ServerError(UnsupportedOperationError())


def build_app(port: int = 8000):
    agent_card = AgentCard(
        name="Klingon Language Tutor",
        description=(
            "Mok'tar — a Klingon language tutor who teaches tlhIngan Hol "
            "through multi-turn conversation with English translations."
        ),
        url=f"http://127.0.0.1:{port}",
        version="2.0.0",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            AgentSkill(
                id="klingon-tutoring",
                name="Klingon Language Tutoring",
                description=(
                    "Teaches tlhIngan Hol through interactive conversation. "
                    "Provides Klingon phrases with English translations and "
                    "builds vocabulary across a multi-turn session."
                ),
                tags=["klingon", "language", "tutoring"],
            )
        ],
        capabilities=AgentCapabilities(),
    )

    handler = KlingonRequestHandler()
    server = A2AFastAPIApplication(agent_card=agent_card, http_handler=handler)
    return server.build(agent_card_url="/.well-known/agent-card.json")


def main():
    parser = argparse.ArgumentParser(description="Klingon Language Tutor A2A Agent")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()
    app = build_app(port=args.port)
    config = uvicorn.Config(app, host="0.0.0.0", port=args.port)
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
