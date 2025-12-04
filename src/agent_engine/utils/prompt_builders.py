"""Prompt construction utilities for Agent Engine.

Provides standardized prompt construction with schema hints, constraint
enforcement, and best practices for JSON generation.
"""

import json
from typing import Optional, Any, Dict
from agent_engine.schemas.registry import SCHEMA_REGISTRY, get_schema_json


def _resolve_ref(ref_path: str, full_schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve a JSON Schema $ref reference to its definition.

    Args:
        ref_path: Reference path (e.g., "#/definitions/ExecutionStep")
        full_schema: Full schema containing definitions

    Returns:
        Referenced schema definition, or empty dict if not found
    """
    if not ref_path.startswith("#/"):
        return {}

    parts = ref_path[2:].split("/")  # Remove "#/" and split by /
    current = full_schema

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, {})
        else:
            return {}

    return current if isinstance(current, dict) else {}


def _generate_json_skeleton(
    schema: Dict[str, Any],
    include_descriptions: bool = True,
    full_schema: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate a JSON skeleton with example blank values from a schema.

    This creates a concrete example structure following StructuredRAG guidance:
    showing the exact keys and structure with placeholder values.

    Supports resolving $ref references to nested definitions.

    Args:
        schema: JSON Schema to generate skeleton from
        include_descriptions: Whether to include field descriptions as values
        full_schema: Full schema (needed for $ref resolution). Defaults to schema itself.

    Returns:
        Dict representing the skeleton structure
    """
    # Use the schema as full_schema if not provided (for initial call)
    if full_schema is None:
        full_schema = schema

    # Handle case where schema itself is a reference
    if '$ref' in schema and not schema.get('properties'):
        resolved = _resolve_ref(schema['$ref'], full_schema)
        if resolved:
            return _generate_json_skeleton(resolved, include_descriptions, full_schema)
        return {}

    skeleton = {}
    properties = schema.get('properties', {})

    for field_name, field_spec in properties.items():
        # Handle $ref at field level
        if '$ref' in field_spec:
            resolved = _resolve_ref(field_spec['$ref'], full_schema)
            if resolved:
                skeleton[field_name] = _generate_json_skeleton(resolved, include_descriptions=False, full_schema=full_schema)
            else:
                skeleton[field_name] = {}
            continue

        field_type = field_spec.get('type', 'any')
        description = field_spec.get('description', '')

        if field_type == 'string':
            if 'enum' in field_spec:
                # Show first enum option as example
                skeleton[field_name] = field_spec['enum'][0] if field_spec['enum'] else "<string>"
            else:
                # Use description as hint or generic placeholder
                if include_descriptions and description:
                    skeleton[field_name] = f"<{description[:50]}>"
                else:
                    skeleton[field_name] = "<string>"

        elif field_type == 'integer' or field_type == 'number':
            skeleton[field_name] = 0

        elif field_type == 'boolean':
            skeleton[field_name] = False

        elif field_type == 'array':
            items_schema = field_spec.get('items', {})

            # Handle $ref in array items
            if '$ref' in items_schema:
                resolved = _resolve_ref(items_schema['$ref'], full_schema)
                if resolved:
                    item_skeleton = _generate_json_skeleton(resolved, include_descriptions=False, full_schema=full_schema)
                    skeleton[field_name] = [item_skeleton]
                else:
                    skeleton[field_name] = [{}]
            else:
                items_type = items_schema.get('type', 'object')

                if items_type == 'object':
                    # Recursively generate skeleton for array items
                    item_skeleton = _generate_json_skeleton(items_schema, include_descriptions=False, full_schema=full_schema)
                    skeleton[field_name] = [item_skeleton]
                elif items_type == 'string':
                    skeleton[field_name] = ["<string>"]
                else:
                    skeleton[field_name] = []

        elif field_type == 'object':
            # Recursively generate skeleton for nested objects
            skeleton[field_name] = _generate_json_skeleton(field_spec, include_descriptions=False, full_schema=full_schema)

        else:
            # Unknown type, use null or description
            if include_descriptions and description:
                skeleton[field_name] = f"<{description[:50]}>"
            else:
                skeleton[field_name] = None

    return skeleton


def json_context(schema_id: str, include_full_schema: bool = False, include_skeleton: bool = True) -> str:
    """
    Generate standardized JSON context/instructions for a schema.

    This helper creates consistent prompt additions that:
    - Describe the expected JSON structure
    - List required fields
    - Provide field-level documentation
    - Include a concrete JSON skeleton showing structure (per StructuredRAG guidance)
    - Include formatting instructions

    Args:
        schema_id: ID of the schema to generate context for
        include_full_schema: Whether to include the full JSON Schema (for debugging)
        include_skeleton: Whether to include concrete JSON skeleton example

    Returns:
        Formatted prompt text to append to prompts

    Example:
        system_prompt = "You are helpful." + json_context("task_spec")
    """
    try:
        schema = get_schema_json(schema_id)
    except KeyError:
        return f"\n\nResponse must be valid JSON matching schema: {schema_id}"

    lines = [
        "",
        "=" * 70,
        "JSON OUTPUT REQUIREMENTS",
        "=" * 70,
        "",
        "You MUST respond with ONLY a valid JSON object.",
        "Do NOT include:",
        "  - Explanatory text before or after the JSON",
        "  - Code fences (```json or ```)",
        "  - Comments inside the JSON",
        "  - Markdown formatting",
        "",
    ]

    # Add schema information
    title = schema.get('title', schema_id)
    lines.append(f"Expected Schema: {title}")

    description = schema.get('description')
    if description:
        lines.append(f"Purpose: {description}")

    lines.append("")

    # Required fields
    required = schema.get('required', [])
    if required:
        lines.append("Required Fields:")
        for field in required:
            properties = schema.get('properties', {})
            field_spec = properties.get(field, {})
            field_type = field_spec.get('type', 'any')
            desc = field_spec.get('description', '')

            if desc:
                lines.append(f"  * {field} ({field_type}): {desc}")
            else:
                lines.append(f"  * {field} ({field_type})")
        lines.append("")

    # Optional fields
    all_fields = set(schema.get('properties', {}).keys())
    optional_fields = all_fields - set(required)
    if optional_fields:
        lines.append("Optional Fields:")
        for field in sorted(optional_fields):
            properties = schema.get('properties', {})
            field_spec = properties.get(field, {})
            field_type = field_spec.get('type', 'any')
            desc = field_spec.get('description', '')

            if desc:
                lines.append(f"  - {field} ({field_type}): {desc}")
            else:
                lines.append(f"  - {field} ({field_type})")
        lines.append("")

    # Enum constraints
    for field_name, field_spec in schema.get('properties', {}).items():
        if 'enum' in field_spec:
            lines.append(f"Note: '{field_name}' must be one of: {', '.join(repr(v) for v in field_spec['enum'])}")

    lines.append("")

    # Add concrete JSON skeleton example (per StructuredRAG guidance)
    if include_skeleton:
        lines.append("Example Structure (replace placeholders with actual values):")
        lines.append("```json")
        skeleton = _generate_json_skeleton(schema, include_descriptions=True)
        lines.append(json.dumps(skeleton, indent=2))
        lines.append("```")
        lines.append("")

    lines.append("=" * 70)
    lines.append("")

    # Optionally include full schema for debugging
    if include_full_schema:
        lines.append("Full JSON Schema:")
        lines.append("```json")
        lines.append(json.dumps(schema, indent=2))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


def json_only_instruction() -> str:
    """
    Get the standard "JSON-only" instruction for prompts.

    Returns:
        Standard instruction text
    """
    return (
        "\n\nIMPORTANT: Respond with ONLY valid JSON. "
        "Do not include explanations, code fences, or any text outside the JSON object."
    )


def wrap_with_json_requirement(base_prompt: str, schema_id: str, mode: str = "full") -> str:
    """
    Wrap an existing prompt with JSON requirements.

    Args:
        base_prompt: The base system or user prompt
        schema_id: Schema ID for the expected response
        mode: How much detail to add:
            - "minimal": Just the JSON-only instruction
            - "standard": JSON-only + schema name
            - "full": Complete schema context (default)

    Returns:
        Enhanced prompt with JSON requirements
    """
    if mode == "minimal":
        return base_prompt + json_only_instruction()

    elif mode == "standard":
        return (
            f"{base_prompt}\n\n"
            f"Respond with ONLY valid JSON matching the '{schema_id}' schema. "
            f"No explanations, no code fences, just the JSON object."
        )

    else:  # "full"
        return base_prompt + json_context(schema_id)


def validate_prompt_has_json_instruction(prompt: str) -> bool:
    """
    Check if a prompt already includes JSON-only instructions.

    Args:
        prompt: Prompt text to check

    Returns:
        True if prompt appears to include JSON requirements
    """
    indicators = [
        "only json",
        "only a json",
        "only valid json",
        "respond with json",
        "return json",
        "output json",
        "no prose",
        "no explanations",
        "do not include",
        "code fence",
    ]

    prompt_lower = prompt.lower()
    return any(indicator in prompt_lower for indicator in indicators)


__all__ = [
    "json_context",
    "json_only_instruction",
    "wrap_with_json_requirement",
    "validate_prompt_has_json_instruction",
    "_resolve_ref",
    "_generate_json_skeleton",
]
