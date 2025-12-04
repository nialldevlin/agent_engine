"""JSON enforcement engine.

This package provides structured JSON handling for King Arthur's Table:
- Schema-based validation (JsonContract, ContractRegistry)
- Constrained JSON generation (ConstrainedJSONGateway)
- Robust parsing with fallback strategies (JSONParser, parse_json_safely)
- Automated repair for malformed JSON (JSONMedic)

The JSON engine ensures all agent outputs conform to expected schemas,
reducing errors and enabling reliable structured data flow.
"""

# Contracts and validation
from king_arthur_orchestrator.json_engine.contracts import (
    JsonContract,
    ValidationResult,
    ContractRegistry,
    get_registry,
    CONTRACTS_DIR,
)

# Parsing utilities
from king_arthur_orchestrator.json_engine.utils import (
    JSONParser,
    ParseResult,
    ParseDiagnostics,
    ErrorClass,
    parse_json_safely,
    classify_json_error,
)

# JSON repair
from king_arthur_orchestrator.json_engine.medic import (
    JSONMedic,
    JSONRepairResult,
)

# Constrained generation gateway
from king_arthur_orchestrator.json_engine.gateway import (
    ConstrainedJSONGateway,
    ConstrainedGenerationResult,
    GenerationMetrics,
    ConstraintBackend,
)

__all__ = [
    # Contracts
    "JsonContract",
    "ValidationResult",
    "ContractRegistry",
    "get_registry",
    "CONTRACTS_DIR",
    # Parsing
    "JSONParser",
    "ParseResult",
    "ParseDiagnostics",
    "ErrorClass",
    "parse_json_safely",
    "classify_json_error",
    # Repair
    "JSONMedic",
    "JSONRepairResult",
    # Gateway
    "ConstrainedJSONGateway",
    "ConstrainedGenerationResult",
    "GenerationMetrics",
    "ConstraintBackend",
]
