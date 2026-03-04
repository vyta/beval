"""JSON Schema validation using shared schemas from spec/.

Validates case files, results, and configuration against the canonical
JSON Schema definitions. See SPEC.md §12, §13.
"""

from __future__ import annotations

import importlib.resources as pkg_resources
import importlib.util
from pathlib import Path
from typing import Any

_HAS_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None


def _find_schema_dir() -> Path:
    """Locate schema directory, preferring bundled package data."""
    # Try package data first (pip-installed)
    try:
        ref = pkg_resources.files("beval") / "schemas"
        schema_path = Path(str(ref))
        if schema_path.is_dir():
            return schema_path
    except (TypeError, FileNotFoundError):
        pass
    # Fallback to monorepo layout (development)
    monorepo_dir = Path(__file__).resolve().parents[3] / "spec" / "schemas"
    if monorepo_dir.is_dir():
        return monorepo_dir
    msg = (
        "Schema directory not found. "
        "Ensure schemas are bundled or run from the monorepo."
    )
    raise FileNotFoundError(msg)


def validate(instance: Any, schema_name: str) -> list[str]:
    """Validate a data structure against a named schema.

    Args:
        instance: The data to validate.
        schema_name: Schema filename without path (e.g., ``"case.schema.json"``).

    Returns:
        List of validation error messages. Empty list means valid.

    Raises:
        ImportError: If jsonschema is not installed.
    """
    if not _HAS_JSONSCHEMA:
        msg = (
            "jsonschema is required for validation. "
            "Install with: pip install 'beval[validate]'"
        )
        raise ImportError(msg)

    import jsonschema

    schema_dir = _find_schema_dir()
    schema_path = schema_dir / schema_name
    if not schema_path.is_file():
        return [f"Schema file not found: {schema_name}"]

    import json

    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    errors: list[str] = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in validator.iter_errors(instance):
        errors.append(error.message)

    return errors
