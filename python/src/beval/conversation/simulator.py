"""UserSimulator interface and built-in implementations (§15.6).

See spec/conversation-sim.spec.md §15.6 for the normative specification.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from beval.conversation.types import (
    DynamicCase,
    Goal,
    Persona,
    ThenClause,
    TurnResult,
    UserFeedback,
)
from beval.types import EvalContext

logger = logging.getLogger(__name__)


# ── Prompt templates (§15.6.3.1) ──────────────────────────────────────────

_SIM_SYSTEM_TEMPLATE = """\
You are a creative writing assistant helping script a conversation for a chatbot test.

Write the next message for this person:

Profile: {persona_description}

Personality: {traits}

Goal for this conversation: {objective}
{completion_criteria}
Estimate how close the person is to achieving \
their goal (0.0 = just started, 1.0 = fully achieved — set to 1.0 only when done).
Progress should only increase or stay the same across turns, never go down.

Reply with a JSON object containing:
- "progress": number between 0.0 and 1.0
- "query": the person's next message (written in their voice)\
"""

_SIM_DYNAMIC_CRITERIA_ADDENDUM = """
Also provide up to {max_criteria} brief notes on what a helpful AI response to \
this message should address.

Include in the JSON object:
- "then": array of evaluation notes, each beginning with "the answer should be: " \
(e.g., "the answer should be: the response gives specific examples"). \
Empty array is fine when progress is 1.0.\
"""

_SIM_USER_HISTORY_TEMPLATE = """\
Conversation so far:

{history}
What is your next message?\
"""

_SIM_USER_FIRST_TEMPLATE = """\
Start the conversation with your opening message.\
"""

# ── Feedback prompt templates ────────────────────────────────────────────

_FEEDBACK_SYSTEM_TEMPLATE = """\
You just finished a conversation with an AI assistant. Stay in character as \
this person and rate the experience.

Profile: {persona_description}

Personality: {traits}

Your goal was: {objective}

Reply with a JSON object containing:
- "satisfaction": number between 0.0 (terrible) and 1.0 (excellent)\
"""

_FEEDBACK_TEXT_ADDENDUM = """
- "text": a brief sentence explaining your rating, in your own voice\
"""

_FEEDBACK_USER_TEMPLATE = """\
Here is the full conversation:

{history}

The conversation ended because: {termination_reason}

Rate your experience.\
"""


def _format_traits(persona: Persona) -> str:
    if not persona.traits:
        return "(none specified)"
    traits = persona.traits
    lines = []
    for attr in (
        "tone",
        "expertise",
        "patience",
        "verbosity",
        "language",
        "style_notes",
    ):  # noqa: E501
        val = getattr(traits, attr, None)
        if val:
            lines.append(f"{attr}: {val}")
    return "\n".join(lines) if lines else "(none specified)"


def _format_history(history: list[TurnResult]) -> str:
    parts = []
    for t in history:
        parts.append(f"User: {t.user_message}")
        parts.append(f"Assistant: {t.agent_response}")
        parts.append("")
    return "\n".join(parts)


def _build_system_message(persona: Persona, goal: Goal, max_criteria: int = 3) -> str:
    on_finish_criteria: list[ThenClause] = []
    for ev in goal.conversation_evals:
        on_finish_criteria.extend(ev.then)
    if on_finish_criteria:
        numbered = "\n".join(
            f"{i + 1}. {c[0]}" for i, c in enumerate(on_finish_criteria)
        )
        completion_criteria = f"\nCompletion criteria (for reference):\n{numbered}\n"
    else:
        completion_criteria = ""
    prompt = _SIM_SYSTEM_TEMPLATE.format(
        persona_description=persona.description,
        traits=_format_traits(persona),
        objective=goal.objective or "(no objective specified)",
        completion_criteria=completion_criteria,
    )
    if max_criteria > 0:
        prompt += _SIM_DYNAMIC_CRITERIA_ADDENDUM.format(max_criteria=max_criteria)
    return prompt


def _build_user_message(history: list[TurnResult]) -> str:
    if not history:
        return _SIM_USER_FIRST_TEMPLATE
    return _SIM_USER_HISTORY_TEMPLATE.format(history=_format_history(history))


def _extract_json_object(raw: str, label: str) -> dict[str, Any]:
    """Strip markdown fences, extract the first JSON object, and parse it."""
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
        data: dict[str, Any] = json.loads(text)
        return data
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from {label}: {raw[:200]}") from exc


def _parse_dynamic_case(raw: str) -> DynamicCase:
    """Parse simulator response into DynamicCase. Raises ValueError on fatal errors."""
    data = _extract_json_object(raw, "simulator")

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


def _parse_feedback(raw: str) -> UserFeedback:
    """Parse feedback response into UserFeedback. Raises ValueError on fatal errors."""
    data = _extract_json_object(raw, "feedback")

    satisfaction = float(data.get("satisfaction", 0.0))
    satisfaction = max(0.0, min(1.0, satisfaction))
    feedback_text = data.get("text")
    if feedback_text is not None:
        feedback_text = str(feedback_text).strip() or None

    return UserFeedback(satisfaction=satisfaction, text=feedback_text)


def _enforce_max_criteria(result: DynamicCase, max_criteria: int) -> DynamicCase:
    """Truncate or clear dynamic criteria to respect the per-turn limit."""
    if max_criteria == 0:
        return DynamicCase(query=result.query, then=(), progress=result.progress)
    if len(result.then) > max_criteria:
        return DynamicCase(
            query=result.query,
            then=result.then[:max_criteria],
            progress=result.progress,
        )
    return result


def _build_feedback_messages(
    persona: Persona,
    goal: Goal,
    history: list[TurnResult],
    termination_reason: str,
    include_text: bool,
) -> tuple[str, str]:
    """Build system + user messages for the feedback prompt."""
    system_msg = _FEEDBACK_SYSTEM_TEMPLATE.format(
        persona_description=persona.description,
        traits=_format_traits(persona),
        objective=goal.objective or "(no objective specified)",
    )
    if include_text:
        system_msg += _FEEDBACK_TEXT_ADDENDUM

    user_msg = _FEEDBACK_USER_TEMPLATE.format(
        history=_format_history(history),
        termination_reason=termination_reason,
    )
    return system_msg, user_msg


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

    async def generate_feedback(  # noqa: B027
        self,
        persona: Persona,
        goal: Goal,
        history: list[TurnResult],
        termination_reason: str,
        *,
        include_text: bool = False,
    ) -> UserFeedback | None:
        """Generate post-conversation feedback. Returns None by default."""
        return None


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
        max_dynamic_criteria_per_turn: int = 3,
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
        self._max_dynamic_criteria_per_turn = max_dynamic_criteria_per_turn

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
        system_msg = _build_system_message(
            persona, goal, self._max_dynamic_criteria_per_turn
        )

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
                    passed=t.passed,
                    error=t.error,
                )
                for t in history
            ]
        else:
            truncated = history

        user_msg = _build_user_message(truncated)
        raw = await asyncio.to_thread(self._call_llm, system_msg, user_msg)
        result = _parse_dynamic_case(raw)
        return _enforce_max_criteria(result, self._max_dynamic_criteria_per_turn)

    def _call_llm(self, system_msg: str, user_msg: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "max_completion_tokens": 8192,  # reasoning models use tokens for thinking before output
        }
        try:
            kwargs["response_format"] = {"type": "json_object"}
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            # response_format not supported — log and retry without it
            logger.debug("response_format not supported (%s), retrying without", exc)
            del kwargs["response_format"]
            response = self._client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        content = choice.message.content or ""
        if not content:
            raise ValueError(
                f"Simulator returned empty content "
                f"(model={self._model}, finish_reason={finish_reason!r}, "
                f"usage={getattr(response, 'usage', None)})"
            )
        return content

    async def generate_feedback(
        self,
        persona: Persona,
        goal: Goal,
        history: list[TurnResult],
        termination_reason: str,
        *,
        include_text: bool = False,
    ) -> UserFeedback | None:
        system_msg, user_msg = _build_feedback_messages(
            persona,
            goal,
            history,
            termination_reason,
            include_text,
        )
        try:
            raw = await asyncio.to_thread(self._call_llm, system_msg, user_msg)
            return _parse_feedback(raw)
        except Exception:  # noqa: BLE001
            logger.warning("Feedback generation failed for %s", persona.id)
            return None


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
        max_dynamic_criteria_per_turn: int = 3,
    ) -> None:
        self._connection = connection
        self._timeout = timeout
        self._max_dynamic_criteria_per_turn = max_dynamic_criteria_per_turn
        self._transport = connection.get("transport", "stdio")
        self._conn: Any = None
        self._process: Any = None
        self._ctx_manager: Any = None
        self._session_id: str | None = None
        self._client: Any = None

    async def _ensure_connected(self) -> None:
        """Lazily establish ACP connection and session."""
        try:
            from acp import (
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

            model = self._connection.get("model")
            if model:
                await asyncio.wait_for(
                    self._conn.set_session_model(
                        model_id=model, session_id=self._session_id
                    ),
                    timeout=self._timeout,
                )

    async def generate_case(
        self,
        persona: Persona,
        goal: Goal,
        history: list[TurnResult],
        context: EvalContext,
    ) -> DynamicCase:
        try:
            from acp import text_block
        except ImportError as exc:
            msg = (
                "ACP simulator requires the 'agent-client-protocol' package. "
                "Install it with: pip install beval[acp]"
            )
            raise ImportError(msg) from exc

        await self._ensure_connected()

        # Combined prompt: system message + separator + user message (§15.6.4.1)
        system_msg = _build_system_message(
            persona, goal, self._max_dynamic_criteria_per_turn
        )
        user_msg = _build_user_message(history)
        combined = f"{system_msg}\n\n---\n\n{user_msg}"

        max_retries = 3
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            if attempt > 0:
                wait = 2.0 * attempt
                logger.warning(
                    "Simulator retry %d/%d after %.1fs (last error: %s)",
                    attempt,
                    max_retries - 1,
                    wait,
                    last_exc,
                )
                await asyncio.sleep(wait)

            self._client.clear()
            await asyncio.wait_for(
                self._conn.prompt(
                    prompt=[text_block(combined)],
                    session_id=self._session_id,
                ),
                timeout=self._timeout,
            )
            raw = "".join(self._client.chunks)
            try:
                result = _parse_dynamic_case(raw)
                return _enforce_max_criteria(
                    result, self._max_dynamic_criteria_per_turn
                )
            except ValueError as exc:
                logger.warning(
                    "Simulator parse error (attempt %d/%d): %s | raw=%r",
                    attempt + 1,
                    max_retries,
                    exc,
                    raw[:500],
                )
                last_exc = exc

        raise ValueError(f"Simulator failed after {max_retries} attempts: {last_exc}")

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

    async def generate_feedback(
        self,
        persona: Persona,
        goal: Goal,
        history: list[TurnResult],
        termination_reason: str,
        *,
        include_text: bool = False,
    ) -> UserFeedback | None:
        try:
            from acp import text_block
        except ImportError:
            return None

        await self._ensure_connected()
        system_msg, user_msg = _build_feedback_messages(
            persona,
            goal,
            history,
            termination_reason,
            include_text,
        )
        combined = f"{system_msg}\n\n---\n\n{user_msg}"
        try:
            self._client.clear()
            await asyncio.wait_for(
                self._conn.prompt(
                    prompt=[text_block(combined)],
                    session_id=self._session_id,
                ),
                timeout=self._timeout,
            )
            raw = "".join(self._client.chunks)
            return _parse_feedback(raw)
        except Exception:  # noqa: BLE001
            logger.warning("Feedback generation failed for %s", persona.id)
            return None


# ── Factory ────────────────────────────────────────────────────────────────


def load_simulator_from_config(
    simulator_config: dict[str, Any],
) -> UserSimulatorInterface:  # noqa: E501
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
            max_dynamic_criteria_per_turn=int(
                resolved.get(
                    "max_dynamic_criteria_per_turn",
                    resolved.get("max_criteria_per_turn", 3),
                )
            ),
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
            max_dynamic_criteria_per_turn=int(
                resolved.get(
                    "max_dynamic_criteria_per_turn",
                    resolved.get("max_criteria_per_turn", 3),
                )
            ),
        )

    raise ValueError(
        f"Unknown simulator protocol: {protocol!r}. Expected 'openai' or 'acp'."
    )
