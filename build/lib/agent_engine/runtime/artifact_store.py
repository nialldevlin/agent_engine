"""Artifact store for Phase 10 Artifact Storage Subsystem with Phase 19 persistence."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid

from agent_engine.schemas import ArtifactMetadata, ArtifactRecord, ArtifactType


class ArtifactStore:
    """Central storage for validated outputs, tool results, and telemetry snapshots.

    Phase 10: In-memory storage.
    Phase 19: Supports optional SQLite backend with automatic persistence.
    """

    def __init__(self, backend_type: str = "in_memory", db_path: Optional[str] = None, max_items: Optional[int] = None):
        """Initialize artifact store with optional persistence backend.

        Args:
            backend_type: Storage backend - 'in_memory' or 'sqlite'
            db_path: Path to SQLite database (required for sqlite backend)
            max_items: Retention policy - max artifacts to keep
        """
        # artifact_id -> ArtifactRecord
        self._artifacts: Dict[str, ArtifactRecord] = {}
        # task_id -> List[artifact_id]
        self._task_index: Dict[str, List[str]] = {}
        # node_id -> List[artifact_id]
        self._node_index: Dict[str, List[str]] = {}

        self.backend_type = backend_type
        self.db_path = db_path
        self.max_items = max_items
        self._persistent_backend = None

        # Initialize persistent backend if requested
        if backend_type == "sqlite":
            if not db_path:
                raise ValueError("db_path required for sqlite backend")
            from agent_engine.runtime.persistent_memory import SQLiteBackend
            self._persistent_backend = SQLiteBackend(db_path)

    def store_artifact(
        self,
        task_id: str,
        artifact_type: ArtifactType,
        payload: Any,
        node_id: Optional[str] = None,
        schema_ref: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store an artifact and return its ID.

        Args:
            task_id: Task that produced this artifact
            artifact_type: Type of artifact
            payload: The artifact data
            node_id: Node that produced this (None for telemetry)
            schema_ref: Schema used for validation
            additional_metadata: Extra metadata

        Returns:
            artifact_id: Unique identifier for retrieval
        """
        artifact_id = str(uuid.uuid4())
        timestamp = datetime.now(ZoneInfo("UTC")).isoformat()

        metadata = ArtifactMetadata(
            artifact_id=artifact_id,
            task_id=task_id,
            node_id=node_id,
            artifact_type=artifact_type,
            timestamp=timestamp,
            schema_ref=schema_ref,
            additional_metadata=additional_metadata or {}
        )

        record = ArtifactRecord(metadata=metadata, payload=payload)

        # Store in main index
        self._artifacts[artifact_id] = record

        # Index by task
        if task_id not in self._task_index:
            self._task_index[task_id] = []
        self._task_index[task_id].append(artifact_id)

        # Index by node (if applicable)
        if node_id:
            if node_id not in self._node_index:
                self._node_index[node_id] = []
            self._node_index[node_id].append(artifact_id)

        # Persist to backend if configured
        if self._persistent_backend:
            self._persistent_backend.add_artifact(
                artifact_id=artifact_id,
                task_id=task_id,
                node_id=node_id,
                artifact_type=artifact_type.value,
                timestamp=timestamp,
                schema_ref=schema_ref,
                payload=payload,
                additional_metadata=additional_metadata
            )
            self._persistent_backend.enforce_artifact_retention(self.max_items)

        return artifact_id

    def get_artifact(self, artifact_id: str) -> Optional[ArtifactRecord]:
        """Retrieve artifact by ID."""
        return self._artifacts.get(artifact_id)

    def get_artifacts_by_task(self, task_id: str) -> List[ArtifactRecord]:
        """Get all artifacts for a task."""
        artifact_ids = self._task_index.get(task_id, [])
        return [self._artifacts[aid] for aid in artifact_ids]

    def get_artifacts_by_node(self, node_id: str) -> List[ArtifactRecord]:
        """Get all artifacts for a node."""
        artifact_ids = self._node_index.get(node_id, [])
        return [self._artifacts[aid] for aid in artifact_ids]

    def get_artifacts_by_type(
        self,
        artifact_type: ArtifactType,
        task_id: Optional[str] = None
    ) -> List[ArtifactRecord]:
        """Get artifacts by type, optionally filtered by task."""
        results = []
        for record in self._artifacts.values():
            if record.metadata.artifact_type == artifact_type:
                if task_id is None or record.metadata.task_id == task_id:
                    results.append(record)
        return results

    def clear(self):
        """Clear all artifacts (useful for testing)."""
        self._artifacts.clear()
        self._task_index.clear()
        self._node_index.clear()
