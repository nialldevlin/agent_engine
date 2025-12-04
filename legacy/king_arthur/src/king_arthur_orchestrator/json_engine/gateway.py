"""
Constrained JSON Gateway for King Arthur's agent system.

Provides schema-constrained JSON generation with pluggable backends:
- Claude API's native JSON mode (default)
- Future: Jsonformer-claude, DOMINO, or other constrained decoders

Part of the consolidated JSON research + fix plan (`docs/RESEARCH.md`).
"""

from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from king_arthur_orchestrator.json_engine.contracts import JsonContract, ValidationResult
from king_arthur_orchestrator.json_engine.utils import JSONParser, ParseResult, ErrorClass


class ConstraintBackend(str, Enum):
    """Available constraint backend strategies."""
    CLAUDE_JSON_MODE = "claude_json_mode"  # Claude API's native JSON mode
    JSONFORMER = "jsonformer"  # Future: Jsonformer-style skeleton generation
    FALLBACK = "fallback"  # Fallback to unconstrained + validation


@dataclass
class GenerationMetrics:
    """Metrics for a constrained generation attempt."""
    backend_used: str
    latency_ms: float
    tokens_used: int
    parse_success: bool
    validation_success: bool
    attempts: int = 1
    fallback_triggered: bool = False
    error_class: Optional[str] = None


@dataclass
class ConstrainedGenerationResult:
    """Result from constrained JSON generation."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    raw_content: str = ""
    metrics: Optional[GenerationMetrics] = None
    parse_result: Optional[ParseResult] = None
    validation_result: Optional[ValidationResult] = None
    error_message: Optional[str] = None

    def __bool__(self) -> bool:
        """Allow result to be used in boolean contexts."""
        return self.success


class ConstraintBackendInterface(ABC):
    """
    Abstract interface for constrained decoding backends.

    Backends must implement generate() to produce JSON conforming to a schema.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        schema: Dict[str, Any],
        completion_fn: Callable,
        **kwargs
    ) -> ConstrainedGenerationResult:
        """
        Generate JSON conforming to the given schema.

        Args:
            prompt: The prompt for generation
            schema: JSON Schema to constrain generation
            completion_fn: Function to call for LLM completion
            **kwargs: Backend-specific parameters

        Returns:
            ConstrainedGenerationResult with generated JSON
        """
        pass

    @abstractmethod
    def supports_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Check if this backend can handle the given schema.

        Args:
            schema: JSON Schema to check

        Returns:
            True if backend can enforce this schema
        """
        pass


class ClaudeJSONModeBackend(ConstraintBackendInterface):
    """
    Backend using Claude API's native Structured Outputs.

    This uses Anthropic's structured outputs feature (beta: structured-outputs-2025-11-13)
    which guarantees JSON schema compliance at generation time - no post-validation needed!

    The API enforces the exact schema during generation, eliminating:
    - Parsing errors
    - Schema validation failures
    - Need for repair/retry logic
    """

    def __init__(self, validate_schema: bool = True):
        """
        Initialize Claude structured outputs backend.

        Args:
            validate_schema: Whether to validate against schema after generation
                           (mostly redundant since API enforces schema, but useful for debugging)
        """
        self.validate_schema = validate_schema
        self.parser = JSONParser()

    def generate(
        self,
        prompt: str,
        schema: Dict[str, Any],
        completion_fn: Callable,
        **kwargs
    ) -> ConstrainedGenerationResult:
        """
        Generate JSON using Claude's native Structured Outputs.

        Args:
            prompt: The prompt (schema is enforced by API, not just hints)
            schema: JSON Schema for generation (API enforces this exactly)
            completion_fn: Function that calls Claude API
            **kwargs: Additional parameters for completion_fn

        Returns:
            ConstrainedGenerationResult
        """
        start_time = time.time()

        # Call Claude with structured outputs (guarantees schema compliance)
        try:
            response = completion_fn(
                prompt=prompt,
                output_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response",
                        "strict": True,
                        "schema": schema
                    }
                },
                **kwargs
            )

            tokens_used = getattr(response, 'tokens_used', 0)
            raw_content = getattr(response, 'content', '')
            if not isinstance(raw_content, str):
                raw_content = str(raw_content)

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ConstrainedGenerationResult(
                success=False,
                error_message=f"Completion failed: {str(e)}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.CLAUDE_JSON_MODE,
                    latency_ms=latency,
                    tokens_used=0,
                    parse_success=False,
                    validation_success=False,
                )
            )

        # Parse the JSON (should always succeed with structured outputs, but check anyway)
        parse_result = self.parser.parse(raw_content)
        latency = (time.time() - start_time) * 1000

        if not parse_result.success:
            # This should NEVER happen with structured outputs - log as critical
            return ConstrainedGenerationResult(
                success=False,
                raw_content=raw_content,
                parse_result=parse_result,
                error_message=f"UNEXPECTED: JSON parsing failed despite structured outputs: {parse_result.error_message}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.CLAUDE_JSON_MODE,
                    latency_ms=latency,
                    tokens_used=tokens_used,
                    parse_success=False,
                    validation_success=False,
                    error_class=parse_result.error_class.value if parse_result.error_class else None
                )
            )

        # Validate against schema if requested (should always pass with structured outputs)
        validation_result = None
        validation_success = True

        if self.validate_schema:
            contract = JsonContract(
                schema_id="inline",
                schema=schema,
                version="1.0.0"
            )
            validation_result = contract.validate(parse_result.data)
            validation_success = validation_result.is_valid

            if not validation_success:
                # This should NEVER happen with structured outputs - log as critical
                pass

        return ConstrainedGenerationResult(
            success=validation_success,
            data=parse_result.data,
            raw_content=raw_content,
            parse_result=parse_result,
            validation_result=validation_result,
            error_message=None if validation_success else f"Schema validation failed: {validation_result.errors}",
            metrics=GenerationMetrics(
                backend_used=ConstraintBackend.CLAUDE_JSON_MODE,
                latency_ms=latency,
                tokens_used=tokens_used,
                parse_success=True,
                validation_success=validation_success,
            )
        )

    def supports_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Claude JSON mode supports any schema (with post-validation).

        Args:
            schema: JSON Schema to check

        Returns:
            Always True (we validate after generation)
        """
        return True


class FallbackBackend(ConstraintBackendInterface):
    """
    Fallback backend using unconstrained generation + validation + repair.

    Used when other backends can't handle a schema or fail.
    """

    def __init__(self):
        """Initialize fallback backend."""
        self.parser = JSONParser()

    def generate(
        self,
        prompt: str,
        schema: Dict[str, Any],
        completion_fn: Callable,
        **kwargs
    ) -> ConstrainedGenerationResult:
        """
        Generate JSON without constraints, then validate.

        Args:
            prompt: The prompt (should include schema hints)
            schema: JSON Schema for validation
            completion_fn: Function that calls LLM
            **kwargs: Additional parameters

        Returns:
            ConstrainedGenerationResult
        """
        start_time = time.time()

        # Call without JSON mode constraint
        try:
            response = completion_fn(prompt=prompt, **kwargs)
            tokens_used = getattr(response, 'tokens_used', 0)
            raw_content = getattr(response, 'content', '')
            if not isinstance(raw_content, str):
                raw_content = str(raw_content)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ConstrainedGenerationResult(
                success=False,
                error_message=f"Completion failed: {str(e)}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.FALLBACK,
                    latency_ms=latency,
                    tokens_used=0,
                    parse_success=False,
                    validation_success=False,
                )
            )

        # Parse
        parse_result = self.parser.parse(raw_content)
        latency = (time.time() - start_time) * 1000

        if not parse_result.success:
            return ConstrainedGenerationResult(
                success=False,
                raw_content=raw_content,
                parse_result=parse_result,
                error_message=f"Parsing failed: {parse_result.error_message}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.FALLBACK,
                    latency_ms=latency,
                    tokens_used=tokens_used,
                    parse_success=False,
                    validation_success=False,
                    error_class=parse_result.error_class.value if parse_result.error_class else None
                )
            )

        # Validate
        contract = JsonContract(schema_id="inline", schema=schema, version="1.0.0")
        validation_result = contract.validate(parse_result.data)

        return ConstrainedGenerationResult(
            success=validation_result.is_valid,
            data=parse_result.data,
            raw_content=raw_content,
            parse_result=parse_result,
            validation_result=validation_result,
            error_message=None if validation_result.is_valid else f"Validation failed: {validation_result.errors}",
            metrics=GenerationMetrics(
                backend_used=ConstraintBackend.FALLBACK,
                latency_ms=latency,
                tokens_used=tokens_used,
                parse_success=True,
                validation_success=validation_result.is_valid,
            )
        )

    def supports_schema(self, schema: Dict[str, Any]) -> bool:
        """Fallback supports any schema."""
        return True


class JsonformerBackend(ConstraintBackendInterface):
    """
    Jsonformer-style constrained backend that fixes JSON structure and lets model fill values.
    
    This backend implements the Jsonformer approach:
    1. Generate a deterministic JSON skeleton from the schema (keys, structure)
    2. Prompt the LLM to only generate the VALUES for each field
    3. Merge the LLM-generated values back into the skeleton
    
    This ensures perfect structural validity while leveraging the LLM for content.
    """
    
    def __init__(self, validate_schema: bool = True):
        """
        Initialize Jsonformer backend.
        
        Args:
            validate_schema: Whether to validate output against schema
        """
        self.validate_schema = validate_schema
        self.parser = JSONParser()
    
    def _generate_skeleton(self, schema: Dict[str, Any], path: str = "") -> tuple[Dict[str, Any], List[str]]:
        """
        Generate a JSON skeleton with placeholders for values.
        
        Returns:
            Tuple of (skeleton dict, list of field paths that need values)
        """
        import json
        
        skeleton = {}
        value_paths = []
        properties = schema.get('properties', {})
        required = set(schema.get('required', []))
        
        for field_name, field_spec in properties.items():
            field_path = f"{path}.{field_name}" if path else field_name
            field_type = field_spec.get('type', 'any')
            
            # Handle different field types
            if field_type == 'string':
                if 'enum' in field_spec:
                    # For enums, we'll still let LLM choose from valid options
                    skeleton[field_name] = f"__VALUE__{field_path}__"
                    value_paths.append(field_path)
                else:
                    skeleton[field_name] = f"__VALUE__{field_path}__"
                    value_paths.append(field_path)
                    
            elif field_type in ('integer', 'number'):
                skeleton[field_name] = f"__VALUE__{field_path}__"
                value_paths.append(field_path)
                
            elif field_type == 'boolean':
                skeleton[field_name] = f"__VALUE__{field_path}__"
                value_paths.append(field_path)
                
            elif field_type == 'array':
                # For arrays, we need special handling
                skeleton[field_name] = f"__ARRAY__{field_path}__"
                value_paths.append(field_path)
                
            elif field_type == 'object':
                # Recursively generate skeleton for nested objects
                nested_skeleton, nested_paths = self._generate_skeleton(field_spec, field_path)
                skeleton[field_name] = nested_skeleton
                value_paths.extend(nested_paths)
                
            elif field_type == 'null':
                skeleton[field_name] = None
                
            else:
                # Unknown type - let LLM generate it
                skeleton[field_name] = f"__VALUE__{field_path}__"
                value_paths.append(field_path)
        
        return skeleton, value_paths
    
    def _build_value_prompt(self, schema: Dict[str, Any], skeleton: Dict[str, Any], 
                           value_paths: List[str], base_prompt: str) -> str:
        """
        Build a prompt that asks the LLM to provide only the values for each field.
        
        Args:
            schema: The JSON schema
            skeleton: The skeleton structure with placeholders
            value_paths: List of field paths that need values
            base_prompt: The original prompt
            
        Returns:
            Enhanced prompt for value-only generation
        """
        import json
        
        lines = [base_prompt, ""]
        lines.append("=" * 70)
        lines.append("JSONFORMER MODE: Provide ONLY the values for these fields")
        lines.append("=" * 70)
        lines.append("")
        lines.append("I will construct the JSON structure. You need to provide ONLY the values.")
        lines.append("For each field below, provide the appropriate value:")
        lines.append("")
        
        # List each field that needs a value
        properties = schema.get('properties', {})
        for field_path in value_paths:
            field_name = field_path.split('.')[-1]
            field_spec = properties.get(field_name, {})
            field_type = field_spec.get('type', 'any')
            description = field_spec.get('description', '')
            
            lines.append(f"Field: {field_path}")
            lines.append(f"  Type: {field_type}")
            if description:
                lines.append(f"  Description: {description}")
            if 'enum' in field_spec:
                lines.append(f"  Allowed values: {', '.join(repr(v) for v in field_spec['enum'])}")
            lines.append("")
        
        lines.append("=" * 70)
        lines.append("RESPONSE FORMAT:")
        lines.append("=" * 70)
        lines.append("Respond with a JSON object mapping field paths to values:")
        lines.append('{"field_path": "value", "another_path": 123, ...}')
        lines.append("")
        lines.append("Example:")
        lines.append('{')
        lines.append('  "task_description": "Fix the login bug",')
        lines.append('  "confidence": 0.85,')
        lines.append('  "next_steps": ["Review code", "Add tests"]')
        lines.append('}')
        lines.append("")
        lines.append("IMPORTANT: Include ALL fields listed above. Respond with ONLY the JSON object.")
        
        return "\n".join(lines)
    
    def _merge_values(self, skeleton: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge LLM-generated values back into the skeleton.
        
        Args:
            skeleton: The skeleton with placeholders
            values: The values provided by the LLM
            
        Returns:
            Complete JSON with values filled in
        """
        import json
        import copy
        
        result = copy.deepcopy(skeleton)
        
        def replace_placeholders(obj, path=""):
            """Recursively replace placeholders with actual values."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    field_path = f"{path}.{key}" if path else key
                    if isinstance(value, str):
                        if value.startswith("__VALUE__") or value.startswith("__ARRAY__"):
                            # Replace with actual value
                            if field_path in values:
                                obj[key] = values[field_path]
                            else:
                                # Value not provided, use default
                                obj[key] = None
                        else:
                            obj[key] = value
                    elif isinstance(value, dict):
                        replace_placeholders(value, field_path)
                    elif isinstance(value, list):
                        obj[key] = [replace_placeholders(item, f"{field_path}[{i}]") 
                                   for i, item in enumerate(value)]
            return obj
        
        return replace_placeholders(result)
    
    def generate(
        self,
        prompt: str,
        schema: Dict[str, Any],
        completion_fn: Callable,
        **kwargs
    ) -> ConstrainedGenerationResult:
        """
        Generate JSON using Jsonformer approach: fixed structure, LLM fills values.
        
        Args:
            prompt: The prompt for generation
            schema: JSON Schema to constrain generation
            completion_fn: Function to call for LLM completion
            **kwargs: Backend-specific parameters
            
        Returns:
            ConstrainedGenerationResult with generated JSON
        """
        start_time = time.time()
        
        # Generate skeleton
        try:
            skeleton, value_paths = self._generate_skeleton(schema)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ConstrainedGenerationResult(
                success=False,
                error_message=f"Failed to generate skeleton: {str(e)}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.JSONFORMER,
                    latency_ms=latency,
                    tokens_used=0,
                    parse_success=False,
                    validation_success=False,
                )
            )
        
        # Build value-only prompt
        value_prompt = self._build_value_prompt(schema, skeleton, value_paths, prompt)
        
        # Call LLM to get values
        try:
            response = completion_fn(
                prompt=value_prompt,
                response_format={"type": "json_object"},
                **kwargs
            )
            tokens_used = getattr(response, 'tokens_used', 0)
            raw_content = getattr(response, 'content', '')
            if not isinstance(raw_content, str):
                raw_content = str(raw_content)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ConstrainedGenerationResult(
                success=False,
                error_message=f"LLM completion failed: {str(e)}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.JSONFORMER,
                    latency_ms=latency,
                    tokens_used=0,
                    parse_success=False,
                    validation_success=False,
                )
            )
        
        # Parse LLM response to extract values
        parse_result = self.parser.parse(raw_content)
        if not parse_result.success:
            latency = (time.time() - start_time) * 1000
            return ConstrainedGenerationResult(
                success=False,
                raw_content=raw_content,
                parse_result=parse_result,
                error_message=f"Failed to parse LLM values: {parse_result.error_message}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.JSONFORMER,
                    latency_ms=latency,
                    tokens_used=tokens_used,
                    parse_success=False,
                    validation_success=False,
                    error_class=parse_result.error_class.value if parse_result.error_class else None
                )
            )
        
        # Merge values into skeleton
        try:
            final_json = self._merge_values(skeleton, parse_result.data)
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return ConstrainedGenerationResult(
                success=False,
                raw_content=raw_content,
                error_message=f"Failed to merge values: {str(e)}",
                metrics=GenerationMetrics(
                    backend_used=ConstraintBackend.JSONFORMER,
                    latency_ms=latency,
                    tokens_used=tokens_used,
                    parse_success=True,
                    validation_success=False,
                )
            )
        
        latency = (time.time() - start_time) * 1000
        
        # Validate if requested
        validation_success = True
        validation_result = None
        
        if self.validate_schema:
            contract = JsonContract(schema_id="inline", schema=schema, version="1.0.0")
            validation_result = contract.validate(final_json)
            validation_success = validation_result.is_valid
        
        return ConstrainedGenerationResult(
            success=validation_success,
            data=final_json,
            raw_content=raw_content,
            parse_result=parse_result,
            validation_result=validation_result,
            error_message=None if validation_success else f"Validation failed: {validation_result.errors}",
            metrics=GenerationMetrics(
                backend_used=ConstraintBackend.JSONFORMER,
                latency_ms=latency,
                tokens_used=tokens_used,
                parse_success=True,
                validation_success=validation_success,
            )
        )
    
    def supports_schema(self, schema: Dict[str, Any]) -> bool:
        """
        Check if Jsonformer can handle this schema.
        
        We don't support:
        - Complex oneOf/anyOf/allOf constructs
        - Pattern/regex constraints
        - Format constraints that require specific string patterns
        
        Args:
            schema: JSON Schema to check
            
        Returns:
            True if we can handle this schema
        """
        # Check for unsupported constructs
        if 'oneOf' in schema or 'anyOf' in schema or 'allOf' in schema:
            return False
        
        # Check properties for patterns or complex formats
        properties = schema.get('properties', {})
        for field_spec in properties.values():
            if 'pattern' in field_spec:
                return False
            if field_spec.get('format') in ('regex', 'uri', 'email', 'ipv4', 'ipv6'):
                # These require specific string patterns we can't easily enforce
                return False
            # Recursively check nested objects
            if field_spec.get('type') == 'object':
                if not self.supports_schema(field_spec):
                    return False
        
        return True


class ConstrainedJSONGateway:
    """
    Gateway for constrained JSON generation with pluggable backends.

    Selects the best backend for a schema, handles retries, and collects telemetry.
    """

    def __init__(
        self,
        preferred_backend: ConstraintBackend = ConstraintBackend.JSONFORMER,
        enable_fallback: bool = True
    ):
        """
        Initialize the JSON gateway.

        Args:
            preferred_backend: Preferred backend to use (default: JSONFORMER)
            enable_fallback: Whether to fall back on failure
        """
        self.preferred_backend = preferred_backend
        self.enable_fallback = enable_fallback

        # Register backends - Jsonformer first, then Claude JSON mode, then fallback
        self.backends: Dict[ConstraintBackend, ConstraintBackendInterface] = {
            ConstraintBackend.JSONFORMER: JsonformerBackend(validate_schema=True),
            ConstraintBackend.CLAUDE_JSON_MODE: ClaudeJSONModeBackend(validate_schema=True),
            ConstraintBackend.FALLBACK: FallbackBackend(),
        }

    def generate(
        self,
        prompt: str,
        schema_id: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        completion_fn: Optional[Callable] = None,
        max_retries: int = 2,
        **kwargs
    ) -> ConstrainedGenerationResult:
        """
        Generate JSON conforming to a schema with intelligent fallback chain.

        Fallback strategy:
        1. Try preferred backend (Structured Outputs) with retries
        2. If preferred fails, try JSONFORMER
        3. If JSONFORMER fails, try FallbackBackend
        4. As last resort, attempt json_medic repair on raw response

        Args:
            prompt: Generation prompt (should include schema hints)
            schema_id: ID of schema in registry (optional if schema provided)
            schema: Raw JSON Schema (optional if schema_id provided)
            completion_fn: Function to call for LLM completion
            max_retries: Maximum retry attempts per backend
            **kwargs: Additional parameters for completion_fn

        Returns:
            ConstrainedGenerationResult
        """
        # Load schema
        if schema is None:
            if schema_id is None:
                raise ValueError("Must provide either schema_id or schema")
            contract = JsonContract.load(schema_id)
            schema = contract.get_schema()

        if completion_fn is None:
            raise ValueError("completion_fn is required")

        # Define fallback chain: Structured Outputs → JSONFORMER → Fallback
        backend_chain = [
            (ConstraintBackend.CLAUDE_JSON_MODE, "Structured Outputs"),
            (ConstraintBackend.JSONFORMER, "JSONFORMER"),
            (ConstraintBackend.FALLBACK, "Fallback"),
        ]

        last_result = None
        total_attempts = 0
        last_exception: Optional[Exception] = None

        # Try each backend in chain
        for backend_type, backend_name in backend_chain:
            backend = self.backends.get(backend_type)
            if not backend:
                continue

            # Try this backend with retries
            for attempt in range(max_retries):
                total_attempts += 1
                try:
                    def completion_with_backend(prompt, response_format=None, **call_kwargs):
                        merged = dict(kwargs)
                        merged.update(call_kwargs)
                        return completion_fn(
                            prompt=prompt,
                            response_format=response_format,
                            gateway_backend=backend_type.value,
                            **merged
                        )

                    result = backend.generate(
                        prompt=prompt,
                        schema=schema,
                        completion_fn=completion_with_backend,
                        **kwargs
                    )

                    if result.success:
                        if result.metrics:
                            result.metrics.attempts = total_attempts
                            if backend_type == ConstraintBackend.FALLBACK:
                                result.metrics.fallback_triggered = True
                        return result

                    if result.metrics and result.metrics.parse_success and not result.metrics.validation_success:
                        result.metrics.attempts = total_attempts
                        return result

                    last_result = result

                    # If fatal error on Structured Outputs, skip to next backend
                    if backend_type == ConstraintBackend.CLAUDE_JSON_MODE and \
                       result.metrics and result.metrics.error_class == ErrorClass.FATAL.value:
                        break

                except Exception as e:
                    last_exception = e
                    # If backend raises exception, try next backend
                    continue

        # All backends failed - try json_medic repair as final fallback
        if last_result is not None and last_result.raw_content and self.enable_fallback:
            try:
                import json
                from .json_medic import JSONMedic
                from .api_client import ClaudeClient

                # Try to get the completion function's client
                # Fallback: create a new one (not ideal but works)
                medic_client = kwargs.get('client')
                if not medic_client:
                    # This is a last resort - ideally client is passed in kwargs
                    medic_client = ClaudeClient(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

                medic = JSONMedic(medic_client)
                repair_result = medic.repair_with_fallback(
                    malformed_json=last_result.raw_content,
                    context=f"Schema: {schema.get('title', 'unknown')}"
                )

                if repair_result.success and repair_result.repaired_json:
                    try:
                        repaired_data = json.loads(repair_result.repaired_json)

                        # Validate against schema
                        contract = JsonContract(
                            schema_id="inline",
                            schema=schema,
                            version="1.0.0"
                        )
                        validation_result = contract.validate(repaired_data)

                        if validation_result.is_valid:
                            if last_result.metrics:
                                last_result.metrics.attempts = total_attempts + 1
                                last_result.metrics.fallback_triggered = True
                                last_result.metrics.tokens_used += repair_result.tokens_used

                            return ConstrainedGenerationResult(
                                success=True,
                                data=repaired_data,
                                raw_content=repair_result.repaired_json,
                                error_message=None,
                                metrics=last_result.metrics or GenerationMetrics(
                                    backend_used="json_medic",
                                    latency_ms=repair_result.latency_ms,
                                    tokens_used=repair_result.tokens_used,
                                    parse_success=True,
                                    validation_success=True,
                                    attempts=total_attempts + 1,
                                    fallback_triggered=True
                                )
                            )
                    except Exception as e:
                        pass
            except Exception as e:
                pass

        # All fallbacks exhausted - return last error
        if last_result is not None:
            if last_result.metrics:
                last_result.metrics.attempts = total_attempts
            return last_result

        if last_exception:
            return ConstrainedGenerationResult(
                success=False,
                error_message=f"Generation failed: {last_exception}",
                metrics=GenerationMetrics(
                    backend_used=self.preferred_backend.value,
                    latency_ms=0.0,
                    tokens_used=0,
                    parse_success=False,
                    validation_success=False,
                    attempts=total_attempts
                )
            )

        # Shouldn't reach here
        return ConstrainedGenerationResult(
            success=False,
            error_message="Generation failed without result",
            metrics=GenerationMetrics(
                backend_used=self.preferred_backend.value,
                latency_ms=0.0,
                tokens_used=0,
                parse_success=False,
                validation_success=False,
                attempts=total_attempts
            )
        )

    def _select_backend(self, schema: Dict[str, Any]) -> ConstraintBackendInterface:
        """
        Select the best backend for a given schema.

        Args:
            schema: JSON Schema

        Returns:
            ConstraintBackendInterface to use
        """
        # Try preferred backend first
        preferred = self.backends.get(self.preferred_backend)
        if preferred and preferred.supports_schema(schema):
            return preferred

        # Fall back to any supporting backend
        for backend in self.backends.values():
            if backend.supports_schema(schema):
                return backend

        # Last resort: fallback
        return self.backends[ConstraintBackend.FALLBACK]

    def register_backend(
        self,
        name: ConstraintBackend,
        backend: ConstraintBackendInterface
    ):
        """
        Register a custom backend.

        Args:
            name: Backend identifier
            backend: Backend implementation
        """
        self.backends[name] = backend


# Global gateway instance
_global_gateway: Optional[ConstrainedJSONGateway] = None


def get_gateway(
    preferred_backend: ConstraintBackend = ConstraintBackend.CLAUDE_JSON_MODE
) -> ConstrainedJSONGateway:
    """
    Get or create the global constrained JSON gateway.

    Args:
        preferred_backend: Preferred backend to use (default: CLAUDE_JSON_MODE)
                          Claude's native Structured Outputs provides guaranteed
                          first-time JSON schema compliance.

    Returns:
        ConstrainedJSONGateway instance
    """
    global _global_gateway
    if _global_gateway is None:
        _global_gateway = ConstrainedJSONGateway(preferred_backend=preferred_backend)
    return _global_gateway


def reset_gateway():
    """Reset the global gateway (useful for tests)."""
    global _global_gateway
    _global_gateway = None
