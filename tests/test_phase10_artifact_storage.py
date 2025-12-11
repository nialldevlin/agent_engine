"""Comprehensive test suite for Phase 10 Artifact Storage Subsystem."""

import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import Mock, MagicMock, patch

from agent_engine.schemas import (
    ArtifactType,
    ArtifactMetadata,
    ArtifactRecord,
    Task,
    TaskSpec,
    Node,
    NodeRole,
    NodeKind,
    UniversalStatus,
    ToolKind,
)
from agent_engine.runtime.artifact_store import ArtifactStore
from agent_engine.runtime.node_executor import NodeExecutor
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.engine import Engine


# ===== Schema Tests (5 tests) =====

class TestArtifactSchema:
    """Test artifact schema definitions."""

    def test_artifact_metadata_creation(self):
        """Test ArtifactMetadata can be created with required fields."""
        metadata = ArtifactMetadata(
            artifact_id="test-artifact-1",
            task_id="task-1"
        )
        assert metadata.artifact_id == "test-artifact-1"
        assert metadata.task_id == "task-1"
        assert metadata.node_id is None
        assert metadata.artifact_type == ArtifactType.NODE_OUTPUT

    def test_artifact_record_creation(self):
        """Test ArtifactRecord can be created with metadata and payload."""
        metadata = ArtifactMetadata(
            artifact_id="test-artifact-1",
            task_id="task-1"
        )
        record = ArtifactRecord(metadata=metadata, payload={"key": "value"})
        assert record.metadata == metadata
        assert record.payload == {"key": "value"}

    def test_artifact_type_enum_values(self):
        """Test ArtifactType enum has expected values."""
        assert ArtifactType.NODE_OUTPUT.value == "node_output"
        assert ArtifactType.TOOL_RESULT.value == "tool_result"
        assert ArtifactType.TELEMETRY_SNAPSHOT.value == "telemetry_snapshot"

    def test_metadata_with_optional_fields(self):
        """Test ArtifactMetadata with all optional fields."""
        metadata = ArtifactMetadata(
            artifact_id="test-artifact-1",
            task_id="task-1",
            node_id="node-1",
            artifact_type=ArtifactType.TOOL_RESULT,
            timestamp="2025-01-01T00:00:00+00:00",
            schema_ref="some-schema",
            additional_metadata={"custom": "data"}
        )
        assert metadata.node_id == "node-1"
        assert metadata.artifact_type == ArtifactType.TOOL_RESULT
        assert metadata.timestamp == "2025-01-01T00:00:00+00:00"
        assert metadata.schema_ref == "some-schema"
        assert metadata.additional_metadata == {"custom": "data"}

    def test_artifact_record_with_complex_payload(self):
        """Test ArtifactRecord can store complex nested payload."""
        metadata = ArtifactMetadata(
            artifact_id="test-artifact-1",
            task_id="task-1"
        )
        complex_payload = {
            "nested": {
                "data": [1, 2, 3],
                "values": {"a": 1, "b": 2}
            }
        }
        record = ArtifactRecord(metadata=metadata, payload=complex_payload)
        assert record.payload == complex_payload


# ===== Store Tests (10 tests) =====

class TestArtifactStore:
    """Test ArtifactStore functionality."""

    @pytest.fixture
    def store(self):
        """Create a fresh artifact store for each test."""
        return ArtifactStore()

    def test_store_artifact_returns_id(self, store):
        """Test that store_artifact returns a unique artifact ID."""
        artifact_id = store.store_artifact(
            task_id="task-1",
            artifact_type=ArtifactType.NODE_OUTPUT,
            payload={"data": "test"}
        )
        assert artifact_id is not None
        assert isinstance(artifact_id, str)
        assert len(artifact_id) > 0

    def test_get_artifact_retrieves_by_id(self, store):
        """Test retrieving artifact by ID."""
        artifact_id = store.store_artifact(
            task_id="task-1",
            artifact_type=ArtifactType.NODE_OUTPUT,
            payload={"data": "test"}
        )
        record = store.get_artifact(artifact_id)
        assert record is not None
        assert record.payload == {"data": "test"}
        assert record.metadata.artifact_id == artifact_id

    def test_get_artifacts_by_task(self, store):
        """Test retrieving all artifacts for a specific task."""
        id1 = store.store_artifact("task-1", ArtifactType.NODE_OUTPUT, {"output": 1})
        id2 = store.store_artifact("task-1", ArtifactType.TOOL_RESULT, {"result": 2})
        id3 = store.store_artifact("task-2", ArtifactType.NODE_OUTPUT, {"output": 3})

        task1_artifacts = store.get_artifacts_by_task("task-1")
        assert len(task1_artifacts) == 2
        assert any(a.metadata.artifact_id == id1 for a in task1_artifacts)
        assert any(a.metadata.artifact_id == id2 for a in task1_artifacts)

    def test_get_artifacts_by_node(self, store):
        """Test retrieving all artifacts for a specific node."""
        id1 = store.store_artifact("task-1", ArtifactType.NODE_OUTPUT, {"output": 1}, node_id="node-1")
        id2 = store.store_artifact("task-1", ArtifactType.TOOL_RESULT, {"result": 2}, node_id="node-1")
        id3 = store.store_artifact("task-1", ArtifactType.NODE_OUTPUT, {"output": 3}, node_id="node-2")

        node1_artifacts = store.get_artifacts_by_node("node-1")
        assert len(node1_artifacts) == 2
        assert any(a.metadata.artifact_id == id1 for a in node1_artifacts)
        assert any(a.metadata.artifact_id == id2 for a in node1_artifacts)

    def test_get_artifacts_by_type(self, store):
        """Test retrieving artifacts by type."""
        id1 = store.store_artifact("task-1", ArtifactType.NODE_OUTPUT, {"output": 1})
        id2 = store.store_artifact("task-1", ArtifactType.NODE_OUTPUT, {"output": 2})
        id3 = store.store_artifact("task-1", ArtifactType.TOOL_RESULT, {"result": 3})

        outputs = store.get_artifacts_by_type(ArtifactType.NODE_OUTPUT)
        assert len(outputs) == 2
        assert all(a.metadata.artifact_type == ArtifactType.NODE_OUTPUT for a in outputs)

    def test_get_artifacts_by_type_filtered_by_task(self, store):
        """Test getting artifacts by type and task."""
        id1 = store.store_artifact("task-1", ArtifactType.NODE_OUTPUT, {"output": 1})
        id2 = store.store_artifact("task-2", ArtifactType.NODE_OUTPUT, {"output": 2})
        id3 = store.store_artifact("task-1", ArtifactType.TOOL_RESULT, {"result": 3})

        task1_outputs = store.get_artifacts_by_type(ArtifactType.NODE_OUTPUT, task_id="task-1")
        assert len(task1_outputs) == 1
        assert task1_outputs[0].metadata.artifact_id == id1

    def test_clear_empties_store(self, store):
        """Test that clear() empties all storage."""
        store.store_artifact("task-1", ArtifactType.NODE_OUTPUT, {"output": 1})
        store.store_artifact("task-1", ArtifactType.TOOL_RESULT, {"result": 2})

        assert len(store.get_artifacts_by_task("task-1")) == 2

        store.clear()

        assert len(store.get_artifacts_by_task("task-1")) == 0
        assert store.get_artifact("nonexistent") is None

    def test_multiple_artifacts_for_same_task(self, store):
        """Test storing multiple artifacts for the same task."""
        ids = []
        for i in range(5):
            artifact_id = store.store_artifact(
                task_id="task-1",
                artifact_type=ArtifactType.NODE_OUTPUT,
                payload={"index": i}
            )
            ids.append(artifact_id)

        artifacts = store.get_artifacts_by_task("task-1")
        assert len(artifacts) == 5
        for i, artifact in enumerate(artifacts):
            assert artifact.payload["index"] == i

    def test_artifacts_without_node_id(self, store):
        """Test storing artifacts without node_id (telemetry snapshots)."""
        artifact_id = store.store_artifact(
            task_id="task-1",
            artifact_type=ArtifactType.TELEMETRY_SNAPSHOT,
            payload={"telemetry": "data"}
        )
        record = store.get_artifact(artifact_id)
        assert record.metadata.node_id is None
        assert record.metadata.artifact_type == ArtifactType.TELEMETRY_SNAPSHOT

    def test_additional_metadata_preservation(self, store):
        """Test that additional metadata is preserved."""
        additional = {"custom_key": "custom_value", "nested": {"data": "value"}}
        artifact_id = store.store_artifact(
            task_id="task-1",
            artifact_type=ArtifactType.NODE_OUTPUT,
            payload={"output": "test"},
            additional_metadata=additional
        )
        record = store.get_artifact(artifact_id)
        assert record.metadata.additional_metadata == additional


# ===== Integration Tests (10 tests) =====

class TestArtifactStorageIntegration:
    """Test artifact storage integration with runtime components."""

    def test_node_executor_stores_artifact_on_success(self):
        """Test that NodeExecutor stores output as artifact on successful execution."""
        # Setup
        store = ArtifactStore()
        executor = NodeExecutor(
            agent_runtime=Mock(),
            tool_runtime=Mock(),
            context_assembler=None,
            json_engine=None,
            deterministic_registry=Mock(),
            telemetry=None,
            artifact_store=store
        )

        # Create mock task and node
        task = Mock(spec=Task)
        task.task_id = "test-task-1"
        task.current_output = {"input": "data"}

        node = Mock(spec=Node)
        node.stage_id = "node-1"
        node.role = NodeRole.LINEAR
        node.kind = NodeKind.DETERMINISTIC
        node.inputs_schema_id = None
        node.outputs_schema_id = None
        node.context = None
        node.tools = None

        # Mock deterministic registry to return test operation
        executor.deterministic_registry.get.return_value = lambda t, n, c: ({"output": "result"}, None)
        executor.deterministic_registry.get_default_for_role.return_value = None

        # Execute
        record, output = executor.execute_node(task, node)

        # Verify artifact was stored
        artifacts = store.get_artifacts_by_task("test-task-1")
        assert len(artifacts) > 0
        assert artifacts[0].metadata.artifact_type == ArtifactType.NODE_OUTPUT
        assert artifacts[0].payload == {"output": "result"}

    def test_tool_runtime_stores_artifact_for_tool_result(self):
        """Test that ToolRuntime stores tool results as artifacts."""
        # Setup with real artifact store to verify it gets called
        store = ArtifactStore()
        runtime = ToolRuntime(
            tools={},
            tool_handlers={},
            llm_client=None,
            telemetry=None,
            artifact_store=store
        )

        # Create mock task and node
        task = Mock(spec=Task)
        task.task_id = "test-task-2"

        node = Mock(spec=Node)
        node.stage_id = "node-2"
        node.tools = []

        # Create tool plan with a step
        tool_plan = {
            "steps": [
                {
                    "tool_id": "test-tool",
                    "inputs": {"arg": "value"},
                    "reason": "test reason",
                    "kind": "analyze"
                }
            ]
        }

        # Create a real tool definition object instead of Mock
        from agent_engine.schemas import ToolDefinition
        tool_def = ToolDefinition(
            tool_id="test-tool",
            name="Test Tool",
            description="Test",
            kind=ToolKind.DETERMINISTIC,
            inputs_schema_id="input-schema",
            outputs_schema_id="output-schema",
            capabilities=[],
            risk_level="low"
        )
        runtime.tools["test-tool"] = tool_def

        # Mock tool handler
        runtime.tool_handlers["test-tool"] = lambda inputs: {"result": "success"}

        # Execute
        with patch("agent_engine.security.check_tool_call") as mock_check:
            mock_check.return_value = Mock(allowed=True, reason=None)
            tool_calls, error = runtime.execute_tool_plan(tool_plan, task, node, None)

        # Verify tool was executed
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_id == "test-tool"

        # Verify artifact was stored
        artifacts = store.get_artifacts_by_task("test-task-2")
        assert len(artifacts) > 0
        assert artifacts[0].metadata.artifact_type == ArtifactType.TOOL_RESULT
        assert "tool_name" in artifacts[0].payload

    def test_artifact_created_during_workflow_execution(self):
        """Test that artifacts are created during workflow execution."""
        store = ArtifactStore()

        # Verify artifacts can be stored throughout execution
        artifact_id_1 = store.store_artifact(
            task_id="workflow-task",
            artifact_type=ArtifactType.NODE_OUTPUT,
            payload={"stage": "first_node"},
            node_id="entry"
        )

        artifact_id_2 = store.store_artifact(
            task_id="workflow-task",
            artifact_type=ArtifactType.TOOL_RESULT,
            payload={"tool": "analyzer", "result": "ok"},
            node_id="processing"
        )

        artifact_id_3 = store.store_artifact(
            task_id="workflow-task",
            artifact_type=ArtifactType.NODE_OUTPUT,
            payload={"final": "output"},
            node_id="exit"
        )

        # Verify all artifacts stored
        all_artifacts = store.get_artifacts_by_task("workflow-task")
        assert len(all_artifacts) == 3

    def test_artifacts_indexed_by_task(self):
        """Test that artifacts are properly indexed by task."""
        store = ArtifactStore()

        for task_num in range(3):
            task_id = f"task-{task_num}"
            for artifact_num in range(2):
                store.store_artifact(
                    task_id=task_id,
                    artifact_type=ArtifactType.NODE_OUTPUT,
                    payload={"task": task_num, "artifact": artifact_num}
                )

        # Verify each task has 2 artifacts
        for task_num in range(3):
            artifacts = store.get_artifacts_by_task(f"task-{task_num}")
            assert len(artifacts) == 2

    def test_artifacts_indexed_by_node(self):
        """Test that artifacts are properly indexed by node."""
        store = ArtifactStore()

        node_ids = ["node-a", "node-b", "node-c"]
        for node_id in node_ids:
            for i in range(3):
                store.store_artifact(
                    task_id="task-1",
                    artifact_type=ArtifactType.NODE_OUTPUT,
                    payload={"node": node_id, "count": i},
                    node_id=node_id
                )

        # Verify each node has 3 artifacts
        for node_id in node_ids:
            artifacts = store.get_artifacts_by_node(node_id)
            assert len(artifacts) == 3

    def test_artifact_metadata_correctness(self):
        """Test that artifact metadata is correctly populated."""
        store = ArtifactStore()

        artifact_id = store.store_artifact(
            task_id="task-1",
            artifact_type=ArtifactType.NODE_OUTPUT,
            payload={"test": "data"},
            node_id="node-1",
            schema_ref="output-schema",
            additional_metadata={"extra": "info"}
        )

        record = store.get_artifact(artifact_id)
        metadata = record.metadata

        assert metadata.artifact_id == artifact_id
        assert metadata.task_id == "task-1"
        assert metadata.node_id == "node-1"
        assert metadata.artifact_type == ArtifactType.NODE_OUTPUT
        assert metadata.schema_ref == "output-schema"
        assert metadata.additional_metadata == {"extra": "info"}
        assert metadata.timestamp  # Should be ISO-8601 timestamp

    def test_artifact_payload_correctness(self):
        """Test that artifact payload is correctly stored and retrieved."""
        store = ArtifactStore()

        payloads = [
            {"string": "value"},
            [1, 2, 3],
            {"nested": {"deep": {"data": "value"}}},
            42,
            None,
            True,
        ]

        artifact_ids = []
        for payload in payloads:
            artifact_id = store.store_artifact(
                task_id="task-1",
                artifact_type=ArtifactType.NODE_OUTPUT,
                payload=payload
            )
            artifact_ids.append(artifact_id)

        for i, artifact_id in enumerate(artifact_ids):
            record = store.get_artifact(artifact_id)
            assert record.payload == payloads[i]

    def test_multiple_artifacts_per_task(self):
        """Test handling multiple artifacts per task."""
        store = ArtifactStore()

        task_id = "multi-artifact-task"
        artifact_ids = []

        # Create artifacts of different types
        artifact_ids.append(
            store.store_artifact(
                task_id=task_id,
                artifact_type=ArtifactType.NODE_OUTPUT,
                payload={"stage": 1},
                node_id="node-1"
            )
        )

        artifact_ids.append(
            store.store_artifact(
                task_id=task_id,
                artifact_type=ArtifactType.TOOL_RESULT,
                payload={"tool": "first"},
                node_id="node-2"
            )
        )

        artifact_ids.append(
            store.store_artifact(
                task_id=task_id,
                artifact_type=ArtifactType.NODE_OUTPUT,
                payload={"stage": 2},
                node_id="node-3"
            )
        )

        # Verify all stored and retrievable
        all_artifacts = store.get_artifacts_by_task(task_id)
        assert len(all_artifacts) == 3
        for i, artifact_id in enumerate(artifact_ids):
            record = store.get_artifact(artifact_id)
            assert record is not None

    def test_artifact_retrieval_apis(self):
        """Test all artifact retrieval APIs work correctly."""
        store = ArtifactStore()

        # Store test artifacts
        id1 = store.store_artifact(
            task_id="task-1",
            artifact_type=ArtifactType.NODE_OUTPUT,
            payload={"data": 1},
            node_id="node-1"
        )
        id2 = store.store_artifact(
            task_id="task-2",
            artifact_type=ArtifactType.TOOL_RESULT,
            payload={"data": 2},
            node_id="node-1"
        )

        # Test get_artifact
        assert store.get_artifact(id1) is not None
        assert store.get_artifact(id2) is not None
        assert store.get_artifact("nonexistent") is None

        # Test get_artifacts_by_task
        assert len(store.get_artifacts_by_task("task-1")) == 1
        assert len(store.get_artifacts_by_task("task-2")) == 1

        # Test get_artifacts_by_node
        assert len(store.get_artifacts_by_node("node-1")) == 2

        # Test get_artifacts_by_type
        outputs = store.get_artifacts_by_type(ArtifactType.NODE_OUTPUT)
        assert len(outputs) == 1
        tools = store.get_artifacts_by_type(ArtifactType.TOOL_RESULT)
        assert len(tools) == 1

    def test_no_artifacts_when_store_disabled(self):
        """Test that no artifacts are stored when artifact_store is None."""
        executor = NodeExecutor(
            agent_runtime=Mock(),
            tool_runtime=Mock(),
            context_assembler=None,
            json_engine=None,
            deterministic_registry=Mock(),
            telemetry=None,
            artifact_store=None  # Disabled
        )

        task = Mock(spec=Task)
        task.task_id = "test-task"
        task.current_output = {"input": "data"}

        node = Mock(spec=Node)
        node.stage_id = "node-1"
        node.role = NodeRole.LINEAR
        node.kind = NodeKind.DETERMINISTIC
        node.inputs_schema_id = None
        node.outputs_schema_id = None
        node.context = None
        node.tools = None

        executor.deterministic_registry.get.return_value = lambda t, n, c: ({"output": "result"}, None)
        executor.deterministic_registry.get_default_for_role.return_value = None

        # Execute - should not raise error even without artifact store
        record, output = executor.execute_node(task, node)

        # Verify execution succeeded
        assert record is not None
        assert output == {"output": "result"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
