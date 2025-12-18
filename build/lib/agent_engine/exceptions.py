"""
Custom exception classes for the Agent Engine.

This module defines structured exception types for manifest loading,
validation errors, and DAG processing.
"""


class EngineError(Exception):
    """Base exception for all Agent Engine errors."""
    pass


class ManifestLoadError(EngineError):
    """Error loading manifest file."""

    def __init__(self, file_name: str, message: str):
        self.file_name = file_name
        self.message = message
        super().__init__(f"Error loading {file_name}: {message}")


class SchemaValidationError(EngineError):
    """Schema validation error in manifest."""

    def __init__(self, file_name: str, field_path: str, message: str):
        self.file_name = file_name
        self.field_path = field_path
        self.message = message
        super().__init__(
            f"Schema validation error in {file_name} at {field_path}: {message}"
        )


class DAGValidationError(EngineError):
    """DAG validation error."""

    def __init__(self, message: str, node_id: str = None):
        self.message = message
        self.node_id = node_id
        if node_id:
            super().__init__(f"DAG validation error at node {node_id}: {message}")
        else:
            super().__init__(f"DAG validation error: {message}")
