"""A2A (Agent2Agent) adapter. See SPEC §13.4.2.

Uses the ``a2a-sdk`` package for HTTP-based agent communication.
Supports ``none``, ``api_key``, and ``bearer`` (Azure Entra ID) auth.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from beval.adapters import AdapterInput, AdapterInterface
from beval.types import Subject

logger = logging.getLogger(__name__)


def _extract_artifact_text(artifact: Any) -> str:
    """Extract concatenated text from an A2A Artifact's parts."""
    parts = []
    for part in getattr(artifact, "parts", []) or []:
        root = getattr(part, "root", part)
        text = getattr(root, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


class A2AAdapter(AdapterInterface):
    """Adapter for agents using the Agent2Agent (A2A) protocol.

    Maintains ``context_id`` across calls so multi-turn conversation simulation
    works correctly — subsequent messages are routed to the same server-side
    conversation context rather than starting a fresh task each turn.

    Auth modes (``connection.auth.type``):
      - ``none`` (default): plain httpx client
      - ``api_key``: inject ``{header: value}`` into httpx headers
      - ``bearer``: Azure Entra ID via ``DefaultAzureCredential``
    """

    def __init__(self, agent_def: dict[str, Any]) -> None:
        self._connection = agent_def.get("connection", {})
        self._timeout = agent_def.get("timeout", 30)
        self._retry = agent_def.get("retry", {})
        self._context_id: str | None = None  # maintained across turns

    def invoke(self, adapter_input: AdapterInput) -> Subject:
        """Send message to A2A agent and return Subject."""
        max_attempts = self._retry.get("max_attempts", 1)
        backoff = self._retry.get("backoff", 1.0)

        query = adapter_input.query
        if isinstance(query, list):
            for msg in reversed(query):
                if msg.get("role") == "user":
                    query = msg.get("content", "")
                    break
            else:
                query = ""

        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                start = time.monotonic()
                output = self._invoke_sync(str(query))
                elapsed = time.monotonic() - start
                return Subject(
                    input=adapter_input.query,
                    output=output,
                    completion_time=elapsed,
                    stage=adapter_input.stage,
                    stage_name=adapter_input.stage_name,
                    prior_subject=adapter_input.prior_subject,
                    metadata={"adapter": "a2a"},
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                exc_str = str(exc).lower()
                if "401" in exc_str or "403" in exc_str:
                    break
                if attempt < max_attempts - 1:
                    time.sleep(backoff * (2**attempt))

        exc_detail = repr(last_exc) if last_exc else "unknown error"
        msg = f"A2A adapter error after {max_attempts} attempt(s): {exc_detail}"
        raise RuntimeError(msg)

    def close(self) -> None:
        """Release A2A client resources."""

    def _invoke_sync(self, query: str) -> str:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._invoke_async(query),
            )
        finally:
            loop.close()

    def _build_httpx_client(self) -> Any:
        """Build an httpx.AsyncClient with appropriate auth headers."""
        import httpx

        timeout = httpx.Timeout(self._timeout)
        auth_config = self._connection.get("auth", {})
        auth_type = auth_config.get("type", "none")

        if auth_type == "bearer":
            try:
                from azure.identity import (
                    DefaultAzureCredential,
                    get_bearer_token_provider,
                )
            except ImportError as exc:
                msg = (
                    "Bearer auth requires 'azure-identity'. "
                    "Install it with: pip install azure-identity"
                )
                raise ImportError(msg) from exc

            scope = auth_config.get(
                "scope", "https://cognitiveservices.azure.com/.default"
            )
            token_provider = get_bearer_token_provider(DefaultAzureCredential(), scope)
            headers = {"Authorization": f"Bearer {token_provider()}"}
            return httpx.AsyncClient(headers=headers, timeout=timeout)

        if auth_type == "api_key":
            header = auth_config.get("header", "Authorization")
            value = auth_config.get("value", "")
            return httpx.AsyncClient(headers={header: value}, timeout=timeout)

        # auth_type == "none" or unrecognized
        return httpx.AsyncClient(timeout=timeout)

    async def _invoke_async(self, query: str) -> str:
        """Async invocation via A2A SDK using ClientFactory.

        Passes ``context_id`` on every call after the first so the agent
        can maintain conversation state across turns.
        """
        try:
            from a2a.client import ClientConfig, ClientFactory
            from a2a.types import Message, Role
        except ImportError as exc:
            msg = (
                "A2A adapter requires the 'a2a-sdk' package. "
                "Install it with: pip install beval[a2a]"
            )
            raise ImportError(msg) from exc

        url = self._connection.get("url", "")
        if not url:
            msg = "A2A connection requires 'url'"
            raise ValueError(msg)

        httpx_client = self._build_httpx_client()
        streaming = self._connection.get("streaming", True)

        try:
            config = ClientConfig(
                httpx_client=httpx_client,
                streaming=streaming,
            )

            client = await ClientFactory.connect(
                agent=url,
                client_config=config,
            )

            from a2a.types import Part, TextPart
            from uuid import uuid4

            message = Message(
                role=Role.user,
                parts=[Part(root=TextPart(text=query))],
                message_id=str(uuid4()),
                context_id=self._context_id,  # None on first turn, set thereafter
            )

            collected: list[str] = []
            seen: set[str] = set()

            def _add(text: str) -> None:
                if text and text not in seen:
                    seen.add(text)
                    collected.append(text)

            async for event in client.send_message(request=message):
                obj = event[0] if isinstance(event, tuple) else event
                cid = getattr(obj, "context_id", None)
                if cid:
                    self._context_id = cid

                if isinstance(event, Message):
                    for part in getattr(event, "parts", []) or []:
                        text = getattr(getattr(part, "root", part), "text", None)
                        if text:
                            _add(text)
                elif isinstance(event, tuple):
                    task, update = event
                    # Artifact from streaming update event
                    upd_art = getattr(update, "artifact", None)
                    if upd_art:
                        _add(_extract_artifact_text(upd_art))
                    # Artifacts from final task state
                    for art in getattr(task, "artifacts", []) or []:
                        _add(_extract_artifact_text(art))

            return "\n\n".join(collected)
        finally:
            await httpx_client.aclose()
