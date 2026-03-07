"""A2A (Agent2Agent) adapter. See SPEC §13.4.2.

Uses the ``a2a-sdk`` package for HTTP-based agent communication.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from beval.adapters import AdapterInput, AdapterInterface
from beval.types import Subject


class A2AAdapter(AdapterInterface):
    """Adapter for agents using the Agent2Agent (A2A) protocol.

    Minimal implementation — will be expanded when tested
    against a real A2A agent.
    """

    def __init__(self, agent_def: dict[str, Any]) -> None:
        self._connection = agent_def.get("connection", {})
        self._timeout = agent_def.get("timeout", 30)
        self._retry = agent_def.get("retry", {})

        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any = None

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

        msg = (
            f"A2A adapter error after {max_attempts}"
            f" attempt(s): {last_exc}"
        )
        raise RuntimeError(msg)

    def close(self) -> None:
        """Release A2A client resources."""
        if self._loop is not None and not self._loop.is_closed():
            self._loop.close()
            self._loop = None
        self._client = None

    def _invoke_sync(self, query: str) -> str:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(
            self._invoke_async(query),
        )

    async def _invoke_async(self, query: str) -> str:
        """Async invocation via A2A SDK."""
        try:
            from a2a.client import A2AClient  # type: ignore[import-untyped]
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

        if self._client is None:
            self._client = await A2AClient.create(url=url)

        message = {
            "role": "user",
            "parts": [{"kind": "text", "text": query}],
        }

        response = await asyncio.wait_for(
            self._client.send_message(
                message=message,
                request_id=str(uuid.uuid4()),
            ),
            timeout=self._timeout,
        )

        # Extract text from response artifacts
        result = getattr(response, "result", response)
        parts: list[str] = []
        for artifact in getattr(result, "artifacts", []) or []:
            for part in getattr(artifact, "parts", []) or []:
                text = getattr(part, "text", None)
                if text:
                    parts.append(text)

        return "".join(parts) if parts else str(result)
