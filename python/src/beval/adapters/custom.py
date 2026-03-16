"""Custom adapter via dynamic class loading. See SPEC §13.4.3."""

from __future__ import annotations

import importlib
from typing import Any

from beval.adapters import AdapterInput, AdapterInterface
from beval.types import Subject


class CustomAdapter(AdapterInterface):
    """Wrapper that loads a user-provided adapter class via importlib.

    See SPEC §13.4.3 for connection parameters and behavior.
    """

    def __init__(self, agent_def: dict[str, Any]) -> None:
        connection = agent_def.get("connection", {})
        module_path = connection.get("module")
        class_name = connection.get("class")

        if not module_path or not class_name:
            raise SystemExit(2)

        try:
            mod = importlib.import_module(module_path)
        except ImportError as exc:
            raise SystemExit(2) from exc

        cls = getattr(mod, class_name, None)
        if cls is None:
            raise SystemExit(2)

        config = connection.get("config", {})
        try:
            self._inner: Any = cls(config) if config else cls()
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(2) from exc

        # Validate interface
        if not callable(getattr(self._inner, "invoke", None)):
            raise SystemExit(2)
        if not callable(getattr(self._inner, "close", None)):
            raise SystemExit(2)

    def invoke(self, adapter_input: AdapterInput) -> Subject:
        """Delegate to the loaded custom adapter."""
        result: Subject = self._inner.invoke(adapter_input)
        return result

    def close(self) -> None:
        """Delegate close to the loaded custom adapter."""
        self._inner.close()
