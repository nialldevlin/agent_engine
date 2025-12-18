"""JSON Engine for validation and minimal repair."""

from __future__ import annotations

import json
from typing import Any, Tuple

from pydantic import ValidationError

from agent_engine.schemas import (
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    SCHEMA_REGISTRY,
    Severity,
)


def _make_error(code: EngineErrorCode, message: str, details: Any = None) -> EngineError:
    return EngineError(
        error_id="engine_error",
        code=code,
        message=message,
        source=EngineErrorSource.JSON_ENGINE,
        severity=Severity.ERROR,
        details=details if isinstance(details, dict) else {"details": str(details)} if details else {},
    )


def validate(schema_name: str, payload: Any) -> Tuple[Any | None, EngineError | None]:
    """Validate payload against a registered schema.

    Returns (validated_object, None) on success, (None, EngineError) on failure.
    """
    model = SCHEMA_REGISTRY.get(schema_name)
    if model is None:
        return None, _make_error(EngineErrorCode.VALIDATION, f"Unknown schema '{schema_name}'")
    try:
        validated = model.model_validate(payload)
        return validated, None
    except ValidationError as exc:
        return None, _make_error(EngineErrorCode.VALIDATION, "Validation failed", exc.errors())


def repair_and_validate(schema_name: str, payload: Any) -> Tuple[Any | None, EngineError | None]:
    """Attempt simple repairs (parse JSON string, trim) before validation."""
    obj = payload
    if isinstance(payload, str):
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            # Attempt to extract between first { and last }
            start = payload.find("{")
            end = payload.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    obj = json.loads(payload[start : end + 1])
                except json.JSONDecodeError:
                    return None, _make_error(EngineErrorCode.JSON, "Repair failed: invalid JSON")
            else:
                return None, _make_error(EngineErrorCode.JSON, "Repair failed: no JSON object found")
    return validate(schema_name, obj)
