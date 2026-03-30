"""UserSimulator interface and built-in implementations (§15.6).

See spec/conversation-sim.spec.md §15.6 for the normative specification.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from beval.conversation.types import DynamicCase, Goal, Persona, TurnResult
from beval.types import EvalContext

logger = logging.getLogger(__name__)


# ── Prompt templates (§15.6.3.1) ──────────────────────────────────────────

_SIM_SYSTEM_TEMPLATE = """\
You are a simulated user in a conversation evaluation scenario.

Persona:
{persona_description}

Traits:
{traits}

Your goal:
{objective}
{completion_criteria}
Instructions:
- Stay in character as described by the persona
- Generate your next message to the agent, pursuing your goal naturally
- Also generate 1–3 evaluation criteria specific to your message — what a
  good response to your exact question should contain or address
- Estimate how much of the goal has been achieved so far (0.0 = nothing, 1.0 = fully done)
- If progress is 1.0, query is ignored — the conversation will end
- Do NOT break character or reveal that you are a simulator

You MUST respond with a JSON object containing exactly:
- "progress": number 0.0–1.0 — fraction of the goal achieved based on the conversation so far
- "query": string — the user message to send (stay in character); ignored when progress == 1.0
- "then": array of strings — criterion strings to evaluate the agent's response \
to this specific message. Use the same style as static then clauses (e.g., \
"the agent addressed the international shipping aspect of the question"). \
These are dispatched through the §4 grader registry. May be empty when progress == 1.0.\
"""

_SIM_USER_HISTORY_TEMPLATE = """\
Conversation so far:

{history}
Generate your next turn. Respond with JSON only.\
"""

_SIM_USER_FIRST_TEMPLATE = """\
This is the start of the conversation. Open the conversation with your first \
message to pursue your goal. Respond with JSON only.\
"""


def _format_traits(persona: Persona) -> str:
    if not persona.traits:
        return "(none specified)"
    traits = persona.traits
    lines = []
    for attr in ("tone", "expertise", "patience", "verbosity", "language", "style_notes"):  # noqa: E501
        val = getattr(traits, attr, None)
        if val:
            lines.append(f"{attr}: {val}")
    return "\n".join(lines) if lines else "(none specified)"


def _format_history(history: list[TurnResult]) -> str:
    parts = []
    for t in history:
        parts.append(f"User: {t.user_message}")
        parts.append(f"<agent_response>\n{t.agent_response}\n</agent_response>")
        parts.append("")
    return "\n".join(parts)


def _build_system_message(persona: Persona, goal: Goal) -> str:
    on_finish = goal.on_finish_then()
    if on_finish:
        numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(on_finish))
        completion_criteria = f"\nCompletion criteria (for reference):\n{numbered}\n"
    else:
        completion_criteria = ""
    return _SIM_SYSTEM_TEMPLATE.format(
        persona_description=persona.description,
        traits=_format_traits(persona),
        objective=goal.given.objective or "(no objective specified)",
        completion_criteria=completion_criteria,
    )


def _build_user_message(history: list[TurnResult]) -> str:
    if not history:
        return _SIM_USER_FIRST_TEMPLATE
    return _SIM_USER_HISTORY_TEMPLATE.format(history=_format_history(history))


def _parse_dynamic_case(raw: str) -> DynamicCase:
    """Parse simulator response into DynamicCase. Raises ValueError on fatal errors."""
    text = raw.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Extract the first JSON object
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    text = text[start : i + 1]
                    break

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from simulator: {raw[:200]}") from exc

    progress = float(data.get("progress", 0.0))
    progress = max(0.0, min(1.0, progress))

    if progress == 1.0:
        return DynamicCase(query="", then=(), progress=1.0)

    query = data.get("query", "")
    if not query or not isinstance(query, str):
        raise ValueError(f"Simulator returned empty or missing 'query': {raw[:200]}")

    then_raw = data.get("then", [])
    if not isinstance(then_raw, list):
        logger.warning("Simulator 'then' is not a list, using []: %s", raw[:200])
        then_raw = []
    then = tuple(str(c) for c in then_raw if c)

    return DynamicCase(query=query, then=then, progress=progress)


# ── Simulator ABC ──────────────────────────────────────────────────────────

class UserSimulatorInterface(ABC):
    """User simulator contract (§15.6.1)."""

    @abstractmethod
    async def generate_case(
        self,
        persona: Persona,
        goal: Goal,
        history: list[TurnResult],
        context: EvalContext,
    ) -> DynamicCase:
        """Generate the next DynamicCase for this turn."""
        ...

    async def close(self) -> None:  # noqa: B027
        """Release resources. No-op by default."""


# ── OpenAI simulator (§15.6.3) ────────────────────────────────────────────

class OpenAISimulator(UserSimulatorInterface):
    """Built-in simulator using an OpenAI-compatible chat completions API (§15.6.3)."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        auth: str | None = None,
        max_answer_chars: int | None = None,
        timeout: float = 30,
    ) -> None:
        try:
            from openai import AzureOpenAI, OpenAI  # noqa: F401
        except ImportError as exc:
            msg = (
                "OpenAI simulator requires the 'openai' package. "
                "Install it with: pip install beval[judge]"
            )
            raise ImportError(msg) from exc

        self._model = model
        self._max_answer_chars = max_answer_chars
        self._timeout = timeout

        # Reuse the same client-creation logic as LLMJudge
        from openai import AzureOpenAI, OpenAI

        from beval.judge import LLMJudge

        if api_key is not None or base_url is not None or auth is not None:
            self._client = LLMJudge._create_client_explicit(
                OpenAI, AzureOpenAI, api_key=api_key, base_url=base_url, auth=auth
            )
        else:
            self._client = LLMJudge._create_client(OpenAI, AzureOpenAI)

    async def generate_case(
        self,
        persona: Persona,
        goal: Goal,
        history: list[TurnResult],
        context: EvalContext,
    ) -> DynamicCase:
        system_msg = _build_system_message(persona, goal)

        # Optionally truncate agent responses to keep prompt size bounded
        if self._max_answer_chars is not None and history:
            truncated = [
                TurnResult(
                    turn_number=t.turn_number,
                    user_message=t.user_message,
                    agent_response=t.agent_response[: self._max_answer_chars],
                    completion_time_seconds=t.completion_time_seconds,
                    goal_progress=t.goal_progress,
                    grades=t.grades,
                    metric_scores=t.metric_scores,
                    overall_score=t.overall_score,
                    error=t.error,
                )
                for t in history
            ]
        else:
            truncated = history

        user_msg = _build_user_message(truncated)
        raw = await asyncio.to_thread(self._call_llm, system_msg, user_msg)
        return _parse_dynamic_case(raw)

    def _call_llm(self, system_msg: str, user_msg: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_completion_tokens=1024,
        )
        return response.choices[0].message.content or ""


# ── ACP simulator (§15.6.4) ───────────────────────────────────────────────

class ACPSimulator(UserSimulatorInterface):
    """Built-in simulator using an ACP-compatible agent (§15.6.4).

    One session per actor, reused across all turns (§15.6.4.2).
    """

    def __init__(
        self,
        connection: dict[str, Any],
        *,
        timeout: float = 30,
    ) -> None:
        self._connection = connection
        self._timeout = timeout
        self._transport = connection.get("transport", "stdio")
        self._conn: Any = None
        self._process: Any = None
        self._ctx_manager: Any = None
        self._session_id: str | None = None
        self._client: Any = None

    async def _ensure_connected(self) -> None:
        """Lazily establish ACP connection and session."""
        try:
            from acp import (  # type: ignore[import-untyped]
                PROTOCOL_VERSION,
                connect_to_agent,
                spawn_agent_process,
            )
        except ImportError as exc:
            msg = (
                "ACP simulator requires the 'agent-client-protocol' package. "
                "Install it with: pip install beval[acp]"
            )
            raise ImportError(msg) from exc

        import os

        from beval.adapters.acp import _EvalClient

        if self._client is None:
            self._client = _EvalClient()

        if self._conn is None:
            if self._transport == "stdio":
                command = self._connection.get("command", [])
                if not command:
                    raise ValueError("ACP simulator stdio transport requires 'command'")
                subprocess_env = dict(os.environ)
                subprocess_env.update(self._connection.get("env", {}))
                cwd = self._connection.get("cwd")
                self._ctx_manager = spawn_agent_process(
                    self._client,
                    command[0],
                    *command[1:],
                    env=subprocess_env,
                    cwd=cwd,
                    transport_kwargs={"limit": 10 * 1024 * 1024},
                )
                self._conn, self._process = await self._ctx_manager.__aenter__()
            elif self._transport == "tcp":
                host = self._connection.get("host", "127.0.0.1")
                port = int(self._connection.get("port", 3000))
                reader, writer = await asyncio.open_connection(host, port)
                self._conn = connect_to_agent(self._client, writer, reader)
            else:
                raise ValueError(f"Unknown ACP transport: {self._transport}")

            await asyncio.wait_for(
                self._conn.initialize(protocol_version=PROTOCOL_VERSION),
                timeout=self._timeout,
            )

        if self._session_id is None:
            import os

            cwd = self._connection.get("cwd") or os.getcwd()
            resp = await asyncio.wait_for(
                self._conn.new_session(cwd=cwd, mcp_servers=[]),
                timeout=self._timeout,
            )
            self._session_id = resp.session_id

    async def generate_case(
        self,
        persona: Persona,
        goal: Goal,
        history: list[TurnResult],
        context: EvalContext,
    ) -> DynamicCase:
        try:
            from acp import text_block  # type: ignore[import-untyped]
        except ImportError as exc:
            msg = (
                "ACP simulator requires the 'agent-client-protocol' package. "
                "Install it with: pip install beval[acp]"
            )
            raise ImportError(msg) from exc

        await self._ensure_connected()

        # Combined prompt: system message + separator + user message (§15.6.4.1)
        system_msg = _build_system_message(persona, goal)
        user_msg = _build_user_message(history)
        combined = f"{system_msg}\n\n---\n\n{user_msg}"

        self._client.clear()
        await asyncio.wait_for(
            self._conn.prompt(
                prompt=[text_block(combined)],
                session_id=self._session_id,
            ),
            timeout=self._timeout,
        )
        raw = "".join(self._client.chunks)
        return _parse_dynamic_case(raw)

    async def close(self) -> None:
        try:
            if self._ctx_manager is not None:
                await self._ctx_manager.__aexit__(None, None, None)
            elif self._conn is not None:
                await self._conn.close()
        except Exception:  # noqa: BLE001, S110
            pass
        self._conn = None
        self._process = None
        self._session_id = None
        self._ctx_manager = None


# ── Factory ────────────────────────────────────────────────────────────────

def load_simulator_from_config(simulator_config: dict[str, Any]) -> UserSimulatorInterface:  # noqa: E501
    """Create a UserSimulator from a config block (§15.6.6)."""
    from beval.judge import _resolve_config_vars

    resolved = _resolve_config_vars(simulator_config)
    protocol = resolved.get("protocol")

    if protocol == "openai":
        model = resolved.get("model")
        if not model:
            raise ValueError(
                "conversation.simulator.model is required for protocol: openai"
            )
        return OpenAISimulator(
            model,
            api_key=resolved.get("api_key"),
            base_url=resolved.get("base_url"),
            auth=resolved.get("auth"),
            max_answer_chars=resolved.get("max_answer_chars"),
            timeout=float(resolved.get("timeout", 30)),
        )

    if protocol == "acp":
        connection = resolved.get("connection")
        if not connection:
            raise ValueError(
                "conversation.simulator.connection is required for protocol: acp"
            )
        return ACPSimulator(
            connection,
            timeout=float(resolved.get("timeout", 30)),
        )

    raise ValueError(
        f"Unknown simulator protocol: {protocol!r}. Expected 'openai' or 'acp'."
    )
