"""Agent adapter interface and loader for the beval framework.

See SPEC.md §13 (Agent Adapters).
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from beval.types import EvalContext, Subject


@dataclass
class AdapterInput:
    """Input passed to an adapter's invoke method. See SPEC §13.3."""

    query: str | list[dict[str, Any]]
    givens: dict[str, Any]
    context: EvalContext
    stage: int | None = None
    stage_name: str | None = None
    prior_subject: Subject | None = None


class AdapterInterface(ABC):
    """Contract all agent adapters must implement. See SPEC §13.3."""

    @abstractmethod
    def invoke(self, adapter_input: AdapterInput) -> Subject:
        """Invoke the agent and return a Subject."""

    @abstractmethod
    def close(self) -> None:
        """Release resources held by this adapter."""


# Pattern for ${VAR} references in agent YAML.
_ENV_REF_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${VAR} references from the process environment.

    Raises ``SystemExit(2)`` if a referenced variable is not set (§13.2).
    """
    if isinstance(value, str):

        def _replace(m: re.Match[str]) -> str:
            var_name = m.group(1)
            val = os.environ.get(var_name)
            if val is None:
                raise SystemExit(2)
            return val

        return _ENV_REF_RE.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


_REQUIRED_FIELDS = {"name", "protocol", "connection"}
_KNOWN_PROTOCOLS = {"acp", "a2a", "custom"}


def load_agent(
    path_or_name: str,
    config_agents: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load an agent definition from a YAML file or config lookup.

    See SPEC §13.5 for resolution rules.

    Returns
    -------
    dict
        The fully-resolved agent definition dictionary.

    Raises
    ------
    SystemExit
        Exit code 2 for invalid definitions, missing files, or missing env vars.
    """
    # Determine if path_or_name is a file path or a bare name (§13.5)
    is_file = "/" in path_or_name or path_or_name.endswith(
        (".yaml", ".yml")
    )

    if is_file:
        agent_path = Path(path_or_name)
        if not agent_path.is_file():
            raise SystemExit(2)
        with open(agent_path, encoding="utf-8") as f:
            agent_def = yaml.safe_load(f)
        if not isinstance(agent_def, dict):
            raise SystemExit(2)
    else:
        # Bare name: look up in config agents definitions
        if not config_agents:
            raise SystemExit(2)
        definitions = config_agents.get("definitions", [])
        agent_def = None
        for defn in definitions:
            if defn.get("name") == path_or_name:
                agent_def = dict(defn)
                break
        if agent_def is None:
            raise SystemExit(2)

    # Validate required fields (§13.2)
    missing = _REQUIRED_FIELDS - set(agent_def.keys())
    if missing:
        raise SystemExit(2)

    protocol = agent_def.get("protocol")
    if protocol not in _KNOWN_PROTOCOLS:
        raise SystemExit(2)

    # Resolve ${VAR} references (§13.2)
    resolved: dict[str, Any] = _resolve_env_vars(agent_def)

    return resolved


def create_adapter(agent_def: dict[str, Any]) -> AdapterInterface:
    """Instantiate the appropriate adapter for an agent definition.

    See SPEC §13.4 for protocol-specific adapters.

    Raises
    ------
    SystemExit
        Exit code 2 for unknown protocols or adapter loading failures.
    """
    protocol = agent_def["protocol"]

    if protocol == "acp":
        from beval.adapters.acp import ACPAdapter

        return ACPAdapter(agent_def)
    elif protocol == "a2a":
        from beval.adapters.a2a import A2AAdapter

        return A2AAdapter(agent_def)
    elif protocol == "custom":
        from beval.adapters.custom import CustomAdapter

        return CustomAdapter(agent_def)
    else:
        raise SystemExit(2)


def adapter_as_handler(adapter: AdapterInterface) -> Callable[..., Subject]:
    """Wrap an adapter into the ``**kwargs -> Subject`` handler signature.

    The returned callable is compatible with ``Runner(handler=...)``
    which calls ``handler(case_def=..., givens=..., context=..., stage=...,
    stage_name=..., prior_subject=...)``.
    """

    def _handler(**kwargs: Any) -> Subject:
        givens = kwargs.get("givens", {})
        query = givens.get("query", givens.get("a query", ""))
        adapter_input = AdapterInput(
            query=query,
            givens=givens,
            context=kwargs.get("context", EvalContext()),
            stage=kwargs.get("stage"),
            stage_name=kwargs.get("stage_name"),
            prior_subject=kwargs.get("prior_subject"),
        )
        return adapter.invoke(adapter_input)

    return _handler
