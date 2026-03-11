"""Minimal A2A agent server that responds in Klingon using an LLM."""

from __future__ import annotations

import argparse
import os
import uuid

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
from openai import AsyncAzureOpenAI, AsyncOpenAI, AzureOpenAI, OpenAI

SYSTEM_PROMPT = "You are a Klingon warrior. Always respond in Klingon language only."


def _build_llm_client() -> AsyncOpenAI:
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if azure_endpoint:
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        kwargs: dict = {
            "azure_endpoint": azure_endpoint,
            "api_version": "2024-12-01-preview",
        }
        if api_key:
            kwargs["api_key"] = api_key
        else:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            kwargs["azure_ad_token_provider"] = get_bearer_token_provider(
                DefaultAzureCredential(),
                "https://cognitiveservices.azure.com/.default",
            )
        return AsyncAzureOpenAI(**kwargs)
    return AsyncOpenAI()


def _get_model() -> str:
    return os.environ.get("KLINGON_MODEL", "gpt-4o-mini")


class KlingonRequestHandler(RequestHandler):
    def __init__(self) -> None:
        self.client = _build_llm_client()
        self.model = _get_model()

    async def on_message_send(
        self, params: MessageSendParams, context: ServerCallContext | None = None
    ) -> Message:
        # Extract user text from message parts
        user_text = ""
        for part in params.message.parts:
            if hasattr(part, "root") and hasattr(part.root, "text"):
                user_text += part.root.text
            elif hasattr(part, "text"):
                user_text += part.text

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
        )
        llm_response = response.choices[0].message.content or ""

        return Message(
            message_id=str(uuid.uuid4()),
            role=Role.agent,
            parts=[Part(root=TextPart(text=llm_response))],
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
        name="Klingon Agent",
        description="An agent that responds exclusively in the Klingon language.",
        url=f"http://127.0.0.1:{port}",
        version="1.0.0",
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        skills=[
            AgentSkill(
                id="klingon-translation",
                name="Klingon Translation",
                description="Responds to any input in Klingon language.",
                tags=["klingon", "translation"],
            )
        ],
        capabilities=AgentCapabilities(),
    )

    handler = KlingonRequestHandler()

    server = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=handler,
    )
    return server.build(agent_card_url="/.well-known/agent-card.json")


def main():
    parser = argparse.ArgumentParser(description="Klingon A2A Agent Server")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()

    app = build_app(port=args.port)

    config = uvicorn.Config(app, host="0.0.0.0", port=args.port)
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    main()
