"""ACP (Agent Client Protocol) adapter. See SPEC §13.4.1.

Uses the ``agent-client-protocol`` SDK for JSON-RPC 2.0 over stdio/tcp.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from beval.adapters import AdapterInput, AdapterInterface
from beval.types import Subject


class _EvalClient:
    """Minimal ACP Client callback handler.

    Only two callbacks are needed — the SDK handles missing methods
    automatically. Follows the pattern from the ACP SDK quickstart.
    """

    def __init__(self) -> None:
        self.chunks: list[str] = []

    def clear(self) -> None:
        self.chunks.clear()

    async def session_update(
        self,
        session_id: str,  # noqa: ARG002
        update: Any,
        **kwargs: Any,  # noqa: ARG002
    ) -> None:
        """Accumulate text from AgentMessageChunk updates."""
        try:
            from acp.schema import AgentMessageChunk, TextContentBlock  # type: ignore[import-untyped]  # noqa: I001
        except ImportError:
            return

        if isinstance(update, AgentMessageChunk):
            if isinstance(update.content, TextContentBlock):
                self.chunks.append(update.content.text)

    async def request_permission(
        self,
        options: Any,
        session_id: str,  # noqa: ARG002
        tool_call: Any,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> Any:
        """Auto-approve all permission requests during evaluation."""
        try:
            from acp.schema import AllowedOutcome, RequestPermissionResponse  # type: ignore[import-untyped]  # noqa: I001
        except ImportError:
            return None

        chosen_id = options[0].option_id if options else "allow_once"
        for opt in options or []:
            if "allow" in (getattr(opt, "kind", "") or "").lower():
                chosen_id = opt.option_id
                break

        return RequestPermissionResponse(
            outcome=AllowedOutcome(
                outcome="selected", option_id=chosen_id,
            ),
        )


class ACPAdapter(AdapterInterface):
    """Adapter for agents using the Agent Client Protocol (ACP).

    Supports both stdio and tcp transports per §13.4.1.
    """

    def __init__(self, agent_def: dict[str, Any]) -> None:
        self._agent_def = agent_def
        self._connection = agent_def.get("connection", {})
        self._timeout = agent_def.get("timeout", 30)
        self._retry = agent_def.get("retry", {})
        self._env = agent_def.get("env", {})
        self._transport = self._connection.get("transport", "stdio")

        # Lazy-initialized async resources
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client = _EvalClient()
        self._conn: Any = None  # ClientSideConnection
        self._process: Any = None
        self._ctx_manager: Any = None
        self._session_id: str | None = None

    def invoke(self, adapter_input: AdapterInput) -> Subject:
        """Connect (if needed), create session, prompt, and return Subject."""
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
                    metadata={
                        "adapter": "acp",
                        "transport": self._transport,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                exc_str = str(exc).lower()
                if "auth" in exc_str or "permission" in exc_str:
                    break
                if attempt < max_attempts - 1:
                    time.sleep(backoff * (2**attempt))

        msg = (
            f"ACP adapter error after {max_attempts}"
            f" attempt(s): {last_exc}"
        )
        raise RuntimeError(msg)

    def close(self) -> None:
        """Release ACP connection resources."""
        if self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.run_until_complete(self._close_async())
            except Exception:  # noqa: BLE001, S110
                pass  # Best-effort cleanup
            finally:
                self._loop.close()
                self._loop = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def _invoke_sync(self, query: str) -> str:
        """Synchronous wrapper over the async ACP SDK."""
        loop = self._get_loop()
        return loop.run_until_complete(self._invoke_async(query))

    async def _invoke_async(self, query: str) -> str:
        """Async invocation: connect → initialize → new_session → prompt."""
        try:
            from acp import PROTOCOL_VERSION, connect_to_agent, spawn_agent_process, text_block  # type: ignore[import-untyped]  # noqa: I001, E501
        except ImportError as exc:
            msg = (
                "ACP adapter requires the 'agent-client-protocol' "
                "package. Install it with: pip install beval[acp]"
            )
            raise ImportError(msg) from exc

        if self._conn is None:
            if self._transport == "stdio":
                command = self._connection.get("command", [])
                if not command:
                    msg = (
                        "ACP stdio transport requires "
                        "'command' in connection"
                    )
                    raise ValueError(msg)
                subprocess_env = dict(os.environ)
                subprocess_env.update(
                    self._connection.get("env", {}),
                )
                subprocess_env.update(self._env)
                cwd = self._connection.get("cwd")
                self._ctx_manager = spawn_agent_process(
                    self._client,
                    command[0],
                    *command[1:],
                    env=subprocess_env,
                    cwd=cwd,
                    transport_kwargs={"limit": 10 * 1024 * 1024},
                )
                self._conn, self._process = (
                    await self._ctx_manager.__aenter__()
                )
            elif self._transport == "tcp":
                host = self._connection.get("host", "127.0.0.1")
                port = self._connection.get("port", 3000)
                reader, writer = await asyncio.open_connection(
                    host, port,
                )
                self._conn = connect_to_agent(
                    self._client, writer, reader,
                )
            else:
                msg = f"Unknown ACP transport: {self._transport}"
                raise ValueError(msg)

            await asyncio.wait_for(
                self._conn.initialize(
                    protocol_version=PROTOCOL_VERSION,
                ),
                timeout=self._timeout,
            )

        if self._session_id is None:
            cwd = self._connection.get("cwd") or os.getcwd()
            resp = await asyncio.wait_for(
                self._conn.new_session(cwd=cwd, mcp_servers=[]),
                timeout=self._timeout,
            )
            self._session_id = resp.session_id

        self._client.clear()

        await asyncio.wait_for(
            self._conn.prompt(
                prompt=[text_block(query)],
                session_id=self._session_id,
            ),
            timeout=self._timeout,
        )

        return "".join(self._client.chunks)

    async def _close_async(self) -> None:
        """Async cleanup of ACP resources."""
        try:
            if self._ctx_manager is not None:
                await self._ctx_manager.__aexit__(None, None, None)
                self._ctx_manager = None
            elif self._conn is not None:
                await self._conn.close()
        except Exception:  # noqa: BLE001, S110
            pass  # Best-effort cleanup

        self._conn = None
        self._process = None
        self._session_id = None
