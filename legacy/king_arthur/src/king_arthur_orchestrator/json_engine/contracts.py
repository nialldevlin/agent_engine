"""
JSON Contract management for King Arthur's agent system.

Provides centralized schema registry, validation, and contract management
for all JSON exchanges between agents and the orchestrator.

Aligned with the consolidated JSON research + fix plan (`docs/RESEARCH.md`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Dict, List, Tuple

try:
    import jsonschema
    from jsonschema import Draft7Validator, validators
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# Path to the JSON contracts registry
CONTRACTS_DIR = Path(__file__).parent / "schemas"


@dataclass
class ValidationResult:
    """Result of schema validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """Allow ValidationResult to be used in boolean contexts."""
        return self.is_valid


class JsonContract:
    """
    Represents a JSON contract with schema and validation capabilities.

    Provides:
    - Schema loading from the centralized registry
    - JSON validation against schemas
    - Schema introspection for constrained decoding
    - Version tracking and compatibility checks
    """

    def __init__(
        self,
        schema_id: str,
        schema: Dict[str, Any],
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a JSON contract.

        Args:
            schema_id: Unique identifier for this schema
            schema: JSON Schema dictionary (Draft 7)
            version: Semantic version of this schema
            metadata: Additional metadata about the contract
        """
        self.schema_id = schema_id
        self.schema = schema
        self.version = version
        self.metadata = metadata or {}

        # Create validator if jsonschema is available
        self.validator = None
        if HAS_JSONSCHEMA:
            try:
                self.validator = Draft7Validator(schema)
            except Exception as e:
                # If schema is invalid, store error but don't fail construction
                self.metadata["schema_error"] = str(e)

    @classmethod
    def load(cls, schema_id: str, version: str = "latest") -> JsonContract:
        """
        Load a contract from the registry.

        Args:
            schema_id: ID of the schema to load (without .schema.json)
            version: Version to load (default: "latest")

        Returns:
            JsonContract instance

        Raises:
            FileNotFoundError: If schema file doesn't exist
            ValueError: If schema is invalid JSON
        """
        schema_path = CONTRACTS_DIR / f"{schema_id}.schema.json"

        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema '{schema_id}' not found at {schema_path}. "
                f"Available schemas: {cls.list_available()}"
            )

        try:
            with schema_path.open("r", encoding="utf-8") as f:
                schema = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in schema '{schema_id}': {e}")

        # Extract version from schema if present, otherwise use parameter
        schema_version = schema.get("version", version)

        # Extract metadata
        metadata = {
            "schema_file": str(schema_path),
            "title": schema.get("title", schema_id),
            "description": schema.get("description", ""),
        }

        return cls(
            schema_id=schema_id,
            schema=schema,
            version=schema_version,
            metadata=metadata
        )

    @classmethod
    def list_available(cls) -> List[str]:
        """
        List all available schema IDs in the registry.

        Returns:
            List of schema IDs (without .schema.json extension)
        """
        if not CONTRACTS_DIR.exists():
            return []

        schemas = []
        for file in CONTRACTS_DIR.glob("*.schema.json"):
            schema_id = file.stem.replace(".schema", "")
            schemas.append(schema_id)

        return sorted(schemas)

    def validate(self, data: Any) -> ValidationResult:
        """
        Validate data against this contract's schema.

        Args:
            data: Data to validate (typically a dict)

        Returns:
            ValidationResult with is_valid flag and error/warning lists
        """
        if not HAS_JSONSCHEMA:
            return ValidationResult(
                is_valid=False,
                errors=["jsonschema library not installed - cannot validate"],
                warnings=["Install jsonschema: pip install jsonschema"]
            )

        if self.validator is None:
            return ValidationResult(
                is_valid=False,
                errors=[f"Schema validation failed: {self.metadata.get('schema_error', 'unknown error')}"]
            )

        errors = []
        warnings = []

        # Collect all validation errors
        for error in self.validator.iter_errors(data):
            # Build readable error message
            path = ".".join(str(p) for p in error.path) if error.path else "root"
            errors.append(f"{path}: {error.message}")

        # Check for additional properties if schema disallows them
        if isinstance(data, dict) and self.schema.get("additionalProperties") is False:
            allowed_props = set(self.schema.get("properties", {}).keys())
            actual_props = set(data.keys())
            extra_props = actual_props - allowed_props
            if extra_props:
                warnings.append(f"Extra properties not in schema: {', '.join(extra_props)}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the raw schema dictionary.

        Useful for passing to constrained decoding backends.

        Returns:
            JSON Schema dictionary
        """
        return self.schema.copy()

    def get_required_fields(self) -> List[str]:
        """
        Get list of required fields from the schema.

        Returns:
            List of required field names
        """
        return self.schema.get("required", [])

    def get_field_description(self, field_name: str) -> Optional[str]:
        """
        Get description for a specific field.

        Args:
            field_name: Name of the field

        Returns:
            Field description or None if not found
        """
        properties = self.schema.get("properties", {})
        field_spec = properties.get(field_name, {})
        return field_spec.get("description")

    def to_prompt_hint(self) -> str:
        """
        Generate a prompt hint describing the expected JSON structure.

        Useful for including in LLM prompts to improve JSON adherence.

        Returns:
            Human-readable description of the expected JSON format
        """
        lines = []

        # Title and description
        title = self.schema.get("title", self.schema_id)
        description = self.schema.get("description", "")

        lines.append(f"Expected JSON format: {title}")
        if description:
            lines.append(f"{description}")

        # Required fields
        required = self.get_required_fields()
        if required:
            lines.append(f"\nRequired fields: {', '.join(required)}")

        # Field descriptions
        properties = self.schema.get("properties", {})
        if properties:
            lines.append("\nField specifications:")
            for field_name, field_spec in properties.items():
                field_type = field_spec.get("type", "any")
                field_desc = field_spec.get("description", "")
                req_marker = "* " if field_name in required else "  "
                lines.append(f"{req_marker}{field_name} ({field_type}): {field_desc}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"JsonContract(schema_id='{self.schema_id}', version='{self.version}')"


# ============================================================================
# Contract Registry Management
# ============================================================================


class ContractRegistry:
    """
    Central registry for managing all JSON contracts.

    Provides caching, bulk loading, and contract lookup by ID or knight name.
    """

    def __init__(self, contracts_dir: Optional[Path] = None):
        """
        Initialize the contract registry.

        Args:
            contracts_dir: Directory containing schema files (default: CONTRACTS_DIR)
        """
        self.contracts_dir = contracts_dir or CONTRACTS_DIR
        self._cache: Dict[str, JsonContract] = {}

    def load(self, schema_id: str, use_cache: bool = True) -> JsonContract:
        """
        Load a contract by ID.

        Args:
            schema_id: Schema ID to load
            use_cache: Whether to use cached contract if available

        Returns:
            JsonContract instance
        """
        if use_cache and schema_id in self._cache:
            return self._cache[schema_id]

        contract = JsonContract.load(schema_id)
        self._cache[schema_id] = contract
        return contract

    def load_all(self) -> Dict[str, JsonContract]:
        """
        Load all contracts from the registry.

        Returns:
            Dictionary mapping schema_id -> JsonContract
        """
        contracts = {}
        errors = []

        for schema_id in JsonContract.list_available():
            try:
                contracts[schema_id] = self.load(schema_id)
            except Exception as e:
                errors.append(f"Failed to load {schema_id}: {e}")

        if errors:
            print(f"Contract registry warnings: {len(errors)} schemas failed to load")
            for error in errors:
                print(f"  - {error}")

        return contracts

    def validate(self, schema_id: str, data: Any) -> ValidationResult:
        """
        Validate data against a schema by ID.

        Args:
            schema_id: Schema ID to validate against
            data: Data to validate

        Returns:
            ValidationResult
        """
        contract = self.load(schema_id)
        return contract.validate(data)

    def clear_cache(self):
        """Clear the contract cache."""
        self._cache.clear()


# Global registry instance
_global_registry: Optional[ContractRegistry] = None


def get_registry(contracts_dir: Optional[Path] = None) -> ContractRegistry:
    """
    Get or create the global contract registry.

    Args:
        contracts_dir: Optional custom contracts directory

    Returns:
        ContractRegistry instance
    """
    global _global_registry
    if _global_registry is None or contracts_dir is not None:
        _global_registry = ContractRegistry(contracts_dir)
    return _global_registry


def reset_registry():
    """Reset the global registry (useful for tests)."""
    global _global_registry
    _global_registry = None
