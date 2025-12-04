"""
Toolkit validation helpers for configuration, overrides, and schema enforcement.

Encapsulates the type/range/choice guards that previously lived inside the
unified config manager so every consumer can rely on a consistent contract.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


TYPE_CHECKERS = {
    "boolean": lambda value: isinstance(value, bool),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "string": lambda value: isinstance(value, str),
    "path": lambda value: isinstance(value, str),
}


def validate_type(value: Any, type_name: str) -> bool:
    """Validate value against named type, raising ValueError for unknown type."""
    checker = TYPE_CHECKERS.get(type_name)
    if not checker:
        raise ValueError(f"Unsupported type '{type_name}'")
    return checker(value)


def validate_range(
    value: Any,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """Restrict numeric values to a min/max range."""
    if not isinstance(value, (int, float)):
        return False, "Value must be numeric to validate range"

    if min_val is not None and value < min_val:
        return False, f"must be >= {min_val}"
    if max_val is not None and value > max_val:
        return False, f"must be <= {max_val}"
    return True, None


def validate_choices(value: Any, choices: Iterable[Any]) -> Tuple[bool, Optional[str]]:
    """Ensure a value belongs to a provided choice list."""
    choice_list = list(choices)
    if value not in choice_list:
        return False, f"must be one of {choice_list}"
    return True, None


def validate_config_section(parameters: Dict[str, Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate a config section where each parameter contains metadata similar to
    `arthur_system_config.json`. Returns (is_valid, errors).
    """
    errors: List[str] = []
    for name, meta in parameters.items():
        param_type = meta.get("type")
        if not param_type:
            errors.append(f"{name}: missing type declaration")
            continue

        value = meta.get("value")
        if param_type == "enum":
            choices = meta.get("choices")
            if not choices:
                errors.append(f"{name}: enum type requires 'choices'")
                continue
            valid, msg = validate_choices(value, choices)
            if not valid:
                errors.append(f"{name}: {msg}")
            continue

        try:
            if not validate_type(value, param_type):
                errors.append(f"{name}: expected type '{param_type}', got {value!r}")
                continue
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            continue

        range_def = meta.get("range", {}) or {}
        if isinstance(range_def, dict):
            min_val = range_def.get("min")
            max_val = range_def.get("max")
            if min_val is not None or max_val is not None:
                valid, msg = validate_range(value, min_val, max_val)
                if not valid:
                    errors.append(f"{name}: {msg}")

    return not errors, errors


__all__ = [
    "validate_type",
    "validate_range",
    "validate_choices",
    "validate_config_section",
    "TYPE_CHECKERS",
]
