"""Comprehensive tests for Phase 1 canonical schemas.

Tests cover:
- Node schema validation (kind-role combinations, agent_id requirements, context)
- Edge schema validation (simple directed pairs, no edge_type field)
- Task schema validation (lifecycle, status, memory references, lineage)
- ContextProfile schema validation (retrieval policies, sources)
- DAG validation (comprehensive invariants and edge cases)
"""

import pytest
from pydantic import ValidationError

from agent_engine.schemas import (
    Edge,
    Node,
    NodeKind,
    NodeRole,
    Task,
    TaskLifecycle,
    TaskMode,
    TaskSpec,
    UniversalStatus,
    WorkflowGraph,
)
from agent_engine.schemas.memory import ContextProfile, ContextProfileSource
from agent_engine.schemas.workflow import validate_workflow_graph


# ============================================================================
# Node Schema Tests
# ============================================================================


class TestNodeSchema:
    """Tests for Node schema validation."""

    def test_valid_start_node_deterministic(self) -> None:
        """Valid: START node with kind=DETERMINISTIC."""
        node = Node(
            stage_id="start",
            name="Start Node",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.START,
            default_start=True,
            context="global",
        )
        assert node.stage_id == "start"
        assert node.role == NodeRole.START
        assert node.default_start is True

    def test_valid_start_node_with_agent_id(self) -> None:
        """Valid: START node with optional agent_id even though DETERMINISTIC."""
        node = Node(
            stage_id="start",
            name="Start",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.START,
            default_start=True,
            context="global",
            agent_id="optional_agent",
        )
        assert node.agent_id == "optional_agent"

    def test_invalid_start_node_with_agent_kind(self) -> None:
        """Invalid: START node with kind=AGENT should fail.

        Per AGENT_ENGINE_SPEC §2.2: start nodes must be deterministic.
        """
        # This validation is a business rule, not enforced by the schema itself
        # We create the node and document the constraint
        node = Node(
            stage_id="start",
            name="Start",
            kind=NodeKind.AGENT,
            role=NodeRole.START,
            default_start=True,
            context="global",
            agent_id="agent1",
        )
        # Schema allows it; DAG validator should catch this in workflow validation
        assert node.kind == NodeKind.AGENT
        assert node.role == NodeRole.START

    def test_valid_exit_node_deterministic(self) -> None:
        """Valid: EXIT node with kind=DETERMINISTIC."""
        node = Node(
            stage_id="exit",
            name="Exit Node",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.EXIT,
            context="global",
        )
        assert node.role == NodeRole.EXIT
        assert node.kind == NodeKind.DETERMINISTIC

    def test_invalid_exit_node_with_agent_kind(self) -> None:
        """Invalid: EXIT node with kind=AGENT should fail.

        Per AGENT_ENGINE_SPEC §2.2: exit nodes must be deterministic.
        """
        # Schema allows; business logic constraint
        node = Node(
            stage_id="exit",
            name="Exit",
            kind=NodeKind.AGENT,
            role=NodeRole.EXIT,
            context="global",
            agent_id="agent1",
        )
        assert node.kind == NodeKind.AGENT
        assert node.role == NodeRole.EXIT

    def test_valid_agent_node_requires_agent_id(self) -> None:
        """Valid: AGENT kind node with agent_id."""
        node = Node(
            stage_id="agent_node",
            name="Agent Node",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            context="global",
            agent_id="agent-1",
        )
        assert node.kind == NodeKind.AGENT
        assert node.agent_id == "agent-1"

    def test_valid_agent_node_without_agent_id(self) -> None:
        """Valid: AGENT kind node without agent_id (optional at schema level)."""
        # Schema allows this; business logic might require it
        node = Node(
            stage_id="agent_node",
            name="Agent Node",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            context="global",
        )
        assert node.agent_id is None

    def test_valid_node_with_context_global(self) -> None:
        """Valid: node with context='global'."""
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="global",
        )
        assert node.context == "global"

    def test_valid_node_with_context_none(self) -> None:
        """Valid: node with context='none'."""
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="none",
        )
        assert node.context == "none"

    def test_valid_node_with_context_profile_id(self) -> None:
        """Valid: node with context set to a profile ID."""
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            context="profile-semantic-1",
            agent_id="agent1",
        )
        assert node.context == "profile-semantic-1"

    def test_valid_node_with_different_roles(self) -> None:
        """Valid: nodes with all role values."""
        roles = [
            NodeRole.START,
            NodeRole.LINEAR,
            NodeRole.DECISION,
            NodeRole.BRANCH,
            NodeRole.SPLIT,
            NodeRole.MERGE,
            NodeRole.EXIT,
        ]
        for i, role in enumerate(roles):
            node = Node(
                stage_id=f"n{i}",
                name=f"Node {role.value}",
                kind=NodeKind.DETERMINISTIC,
                role=role,
                context="global",
            )
            assert node.role == role

    def test_invalid_node_missing_required_field(self) -> None:
        """Invalid: node missing required field (e.g., stage_id)."""
        with pytest.raises(ValidationError):
            Node(name="Node", kind=NodeKind.AGENT, role=NodeRole.LINEAR, context="global")  # type: ignore

    def test_invalid_node_missing_context(self) -> None:
        """Invalid: node missing required context field."""
        with pytest.raises(ValidationError):
            Node(stage_id="n1", name="Node", kind=NodeKind.AGENT, role=NodeRole.LINEAR)  # type: ignore

    def test_valid_node_default_start_false(self) -> None:
        """Valid: node with default_start=False (the default)."""
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            context="global",
            agent_id="agent1",
        )
        assert node.default_start is False

    def test_invalid_non_start_node_with_default_start_true(self) -> None:
        """Invalid: non-START node with default_start=True should fail validation.

        Only START nodes can have default_start=True (business rule).
        """
        # Schema allows it; DAG validator should catch this
        node = Node(
            stage_id="linear",
            name="Linear",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            default_start=True,
            context="global",
            agent_id="agent1",
        )
        assert node.role == NodeRole.LINEAR
        assert node.default_start is True

    def test_valid_node_with_tools_list(self) -> None:
        """Valid: node with tools list."""
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.LINEAR,
            context="global",
            tools=["tool1", "tool2", "tool3"],
        )
        assert node.tools == ["tool1", "tool2", "tool3"]

    def test_valid_node_with_schemas(self) -> None:
        """Valid: node with inputs_schema_id and outputs_schema_id."""
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            context="global",
            agent_id="agent1",
            inputs_schema_id="schema-in",
            outputs_schema_id="schema-out",
        )
        assert node.inputs_schema_id == "schema-in"
        assert node.outputs_schema_id == "schema-out"

    def test_valid_node_with_continue_on_failure(self) -> None:
        """Valid: node with continue_on_failure=True."""
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            context="global",
            agent_id="agent1",
            continue_on_failure=True,
        )
        assert node.continue_on_failure is True

    def test_valid_merge_node_with_merge_config(self) -> None:
        """Valid: MERGE node with merge configuration."""
        merge_config = {"strategy": "concatenate", "aggregation": "combine_all"}
        node = Node(
            stage_id="merge",
            name="Merge",
            kind=NodeKind.DETERMINISTIC,
            role=NodeRole.MERGE,
            context="global",
            merge=merge_config,
        )
        assert node.merge == merge_config

    def test_valid_node_with_metadata(self) -> None:
        """Valid: node with arbitrary metadata."""
        metadata = {"custom_key": "custom_value", "priority": 5}
        node = Node(
            stage_id="n1",
            name="Node",
            kind=NodeKind.AGENT,
            role=NodeRole.LINEAR,
            context="global",
            agent_id="agent1",
            metadata=metadata,
        )
        assert node.metadata == metadata


# ============================================================================
# Edge Schema Tests
# ============================================================================


class TestEdgeSchema:
    """Tests for Edge schema validation."""

    def test_valid_edge_with_condition(self) -> None:
        """Valid: edge with condition (for decision routing)."""
        edge = Edge(from_node_id="decision", to_node_id="branch1", condition="yes")
        assert edge.from_node_id == "decision"
        assert edge.to_node_id == "branch1"
        assert edge.condition == "yes"

    def test_valid_edge_without_condition(self) -> None:
        """Valid: edge without condition."""
        edge = Edge(from_node_id="node1", to_node_id="node2")
        assert edge.condition is None

    def test_valid_edge_with_edge_id(self) -> None:
        """Valid: edge with optional edge_id."""
        edge = Edge(from_node_id="n1", to_node_id="n2", edge_id="e1")
        assert edge.edge_id == "e1"

    def test_edge_no_edge_type_field(self) -> None:
        """Valid: edge schema has no edge_type field (per Phase 1 spec).

        Per AGENT_ENGINE_SPEC §3.1: routing semantics come from node roles,
        not edge types. Edge should not have an edge_type field.
        """
        # Create edge and verify it has no edge_type attribute
        edge = Edge(from_node_id="n1", to_node_id="n2")
        assert not hasattr(edge, "edge_type")

    def test_invalid_edge_missing_from_node_id(self) -> None:
        """Invalid: edge missing from_node_id."""
        with pytest.raises(ValidationError):
            Edge(to_node_id="n2")  # type: ignore

    def test_invalid_edge_missing_to_node_id(self) -> None:
        """Invalid: edge missing to_node_id."""
        with pytest.raises(ValidationError):
            Edge(from_node_id="n1")  # type: ignore

    def test_valid_edge_with_all_fields(self) -> None:
        """Valid: edge with all optional fields."""
        edge = Edge(
            from_node_id="n1",
            to_node_id="n2",
            condition="route_a",
            edge_id="edge_001",
        )
        assert edge.from_node_id == "n1"
        assert edge.to_node_id == "n2"
        assert edge.condition == "route_a"
        assert edge.edge_id == "edge_001"


# ============================================================================
# Task Schema Tests
# ============================================================================


class TestTaskSchema:
    """Tests for Task schema validation."""

    def test_valid_task_minimal(self) -> None:
        """Valid: minimal task with required fields."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        task = Task(
            task_id="task-1",
            spec=spec,
            task_memory_ref="task_mem",
            project_memory_ref="proj_mem",
            global_memory_ref="global_mem",
        )
        assert task.task_id == "task-1"
        assert task.lifecycle == TaskLifecycle.QUEUED
        assert task.status == UniversalStatus.PENDING

    def test_valid_task_with_lifecycle_states(self) -> None:
        """Valid: task with different lifecycle values."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        lifecycles = [
            TaskLifecycle.QUEUED,
            TaskLifecycle.ACTIVE,
            TaskLifecycle.SUSPENDED,
            TaskLifecycle.CONCLUDED,
            TaskLifecycle.ARCHIVED,
        ]
        for lifecycle in lifecycles:
            task = Task(
                task_id=f"task-{lifecycle.value}",
                spec=spec,
                lifecycle=lifecycle,
                task_memory_ref="task_mem",
                project_memory_ref="proj_mem",
                global_memory_ref="global_mem",
            )
            assert task.lifecycle == lifecycle

    def test_valid_task_with_status_values(self) -> None:
        """Valid: task with different status values."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        statuses = [
            UniversalStatus.PENDING,
            UniversalStatus.IN_PROGRESS,
            UniversalStatus.COMPLETED,
            UniversalStatus.FAILED,
            UniversalStatus.CANCELLED,
            UniversalStatus.BLOCKED,
        ]
        for status in statuses:
            task = Task(
                task_id=f"task-{status.value}",
                spec=spec,
                status=status,
                task_memory_ref="task_mem",
                project_memory_ref="proj_mem",
                global_memory_ref="global_mem",
            )
            assert task.status == status

    def test_valid_task_with_current_output(self) -> None:
        """Valid: task has current_output field."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        task = Task(
            task_id="task-1",
            spec=spec,
            current_output={"result": "some output"},
            task_memory_ref="task_mem",
            project_memory_ref="proj_mem",
            global_memory_ref="global_mem",
        )
        assert task.current_output == {"result": "some output"}

    def test_valid_task_with_lineage_clone(self) -> None:
        """Valid: task with lineage fields for clone relationship."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        task = Task(
            task_id="task-clone",
            spec=spec,
            parent_task_id="task-original",
            lineage_type="clone",
            lineage_metadata={"clone_reason": "retry"},
            task_memory_ref="task_mem",
            project_memory_ref="proj_mem",
            global_memory_ref="global_mem",
        )
        assert task.parent_task_id == "task-original"
        assert task.lineage_type == "clone"
        assert task.lineage_metadata["clone_reason"] == "retry"

    def test_valid_task_with_lineage_subtask(self) -> None:
        """Valid: task with lineage fields for subtask relationship."""
        spec = TaskSpec(task_spec_id="spec-1", request="Subtask")
        task = Task(
            task_id="subtask-1",
            spec=spec,
            parent_task_id="parent-task",
            lineage_type="decomposed",
            lineage_metadata={"decomposition_index": 0, "total_subtasks": 3},
            task_memory_ref="task_mem",
            project_memory_ref="proj_mem",
            global_memory_ref="global_mem",
        )
        assert task.parent_task_id == "parent-task"
        assert task.lineage_type == "decomposed"
        assert task.lineage_metadata["decomposition_index"] == 0

    def test_valid_task_with_memory_references(self) -> None:
        """Valid: task has task, project, and global memory references."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        task = Task(
            task_id="task-1",
            spec=spec,
            task_memory_ref="mem:task:task-1",
            project_memory_ref="mem:project:proj-1",
            global_memory_ref="mem:global:global",
        )
        assert task.task_memory_ref == "mem:task:task-1"
        assert task.project_memory_ref == "mem:project:proj-1"
        assert task.global_memory_ref == "mem:global:global"

    def test_invalid_task_missing_memory_refs(self) -> None:
        """Invalid: task missing required memory references."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        with pytest.raises(ValidationError):
            Task(task_id="task-1", spec=spec, task_memory_ref="task_mem")  # type: ignore

    def test_valid_task_with_current_stage_id(self) -> None:
        """Valid: task with current_stage_id."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        task = Task(
            task_id="task-1",
            spec=spec,
            current_stage_id="stage-2",
            task_memory_ref="task_mem",
            project_memory_ref="proj_mem",
            global_memory_ref="global_mem",
        )
        assert task.current_stage_id == "stage-2"

    def test_valid_task_with_timestamps(self) -> None:
        """Valid: task with created_at and updated_at timestamps."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something")
        task = Task(
            task_id="task-1",
            spec=spec,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T01:00:00Z",
            task_memory_ref="task_mem",
            project_memory_ref="proj_mem",
            global_memory_ref="global_mem",
        )
        assert task.created_at == "2025-01-01T00:00:00Z"
        assert task.updated_at == "2025-01-01T01:00:00Z"

    def test_valid_task_to_dict_and_from_dict(self) -> None:
        """Valid: task can round-trip through dict serialization."""
        spec = TaskSpec(task_spec_id="spec-1", request="Do something", mode=TaskMode.IMPLEMENT)
        original = Task(
            task_id="task-1",
            spec=spec,
            lifecycle=TaskLifecycle.ACTIVE,
            status=UniversalStatus.IN_PROGRESS,
            current_output={"data": "value"},
            task_memory_ref="task_mem",
            project_memory_ref="proj_mem",
            global_memory_ref="global_mem",
        )

        # Convert to dict and back
        task_dict = original.to_dict()
        restored = Task.from_dict(task_dict)

        assert restored.task_id == original.task_id
        assert restored.lifecycle == original.lifecycle
        assert restored.status == original.status
        assert restored.current_output == original.current_output


# ============================================================================
# ContextProfile Schema Tests
# ============================================================================


class TestContextProfileSchema:
    """Tests for ContextProfile schema validation."""

    def test_valid_context_profile_recency(self) -> None:
        """Valid: profile with retrieval_policy='recency'."""
        profile = ContextProfile(
            id="profile-recency",
            max_tokens=2048,
            retrieval_policy="recency",
            sources=[ContextProfileSource(store="task")],
        )
        assert profile.retrieval_policy == "recency"

    def test_valid_context_profile_semantic(self) -> None:
        """Valid: profile with retrieval_policy='semantic'."""
        profile = ContextProfile(
            id="profile-semantic",
            max_tokens=2048,
            retrieval_policy="semantic",
            sources=[ContextProfileSource(store="project")],
        )
        assert profile.retrieval_policy == "semantic"

    def test_valid_context_profile_hybrid(self) -> None:
        """Valid: profile with retrieval_policy='hybrid'."""
        profile = ContextProfile(
            id="profile-hybrid",
            max_tokens=2048,
            retrieval_policy="hybrid",
            sources=[ContextProfileSource(store="global")],
        )
        assert profile.retrieval_policy == "hybrid"

    def test_valid_context_profile_multiple_sources(self) -> None:
        """Valid: profile with multiple sources (task, project, global)."""
        profile = ContextProfile(
            id="profile-multi",
            max_tokens=4096,
            retrieval_policy="hybrid",
            sources=[
                ContextProfileSource(store="task"),
                ContextProfileSource(store="project"),
                ContextProfileSource(store="global"),
            ],
        )
        assert len(profile.sources) == 3
        assert profile.sources[0].store == "task"
        assert profile.sources[1].store == "project"
        assert profile.sources[2].store == "global"

    def test_valid_context_profile_source_with_tags(self) -> None:
        """Valid: profile source with optional tags."""
        profile = ContextProfile(
            id="profile-tagged",
            max_tokens=2048,
            retrieval_policy="recency",
            sources=[
                ContextProfileSource(store="task", tags=["recent", "critical"]),
                ContextProfileSource(store="project", tags=["relevant"]),
            ],
        )
        assert profile.sources[0].tags == ["recent", "critical"]
        assert profile.sources[1].tags == ["relevant"]

    def test_valid_context_profile_with_metadata(self) -> None:
        """Valid: profile with arbitrary metadata."""
        metadata = {"compression": "enabled", "cache_ttl": 3600}
        profile = ContextProfile(
            id="profile-meta",
            max_tokens=2048,
            retrieval_policy="hybrid",
            sources=[ContextProfileSource(store="task")],
            metadata=metadata,
        )
        assert profile.metadata == metadata

    def test_invalid_context_profile_missing_id(self) -> None:
        """Invalid: profile missing id field."""
        with pytest.raises(ValidationError):
            ContextProfile(
                max_tokens=2048,
                retrieval_policy="recency",
                sources=[ContextProfileSource(store="task")],
            )  # type: ignore

    def test_invalid_context_profile_missing_max_tokens(self) -> None:
        """Invalid: profile missing max_tokens field."""
        with pytest.raises(ValidationError):
            ContextProfile(
                id="profile",
                retrieval_policy="recency",
                sources=[ContextProfileSource(store="task")],
            )  # type: ignore

    def test_invalid_context_profile_missing_retrieval_policy(self) -> None:
        """Invalid: profile missing retrieval_policy field."""
        with pytest.raises(ValidationError):
            ContextProfile(
                id="profile",
                max_tokens=2048,
                sources=[ContextProfileSource(store="task")],
            )  # type: ignore

    def test_invalid_context_profile_missing_sources(self) -> None:
        """Invalid: profile missing sources field."""
        with pytest.raises(ValidationError):
            ContextProfile(
                id="profile",
                max_tokens=2048,
                retrieval_policy="recency",
            )  # type: ignore

    def test_valid_context_profile_source_minimal(self) -> None:
        """Valid: source with just store field."""
        source = ContextProfileSource(store="task")
        assert source.store == "task"
        assert source.tags == []

    def test_invalid_context_profile_source_missing_store(self) -> None:
        """Invalid: source missing store field."""
        with pytest.raises(ValidationError):
            ContextProfileSource()  # type: ignore


# ============================================================================
# DAG Validation Tests
# ============================================================================


class TestDAGValidation:
    """Tests for WorkflowGraph DAG validation."""

    def test_valid_minimal_dag(self) -> None:
        """Valid: minimal DAG with one START, one LINEAR, one EXIT."""
        graph = WorkflowGraph(
            workflow_id="wf1",
            nodes=["start", "process", "exit"],
            edges=[
                Edge(from_node_id="start", to_node_id="process"),
                Edge(from_node_id="process", to_node_id="exit"),
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "process": Node(
                stage_id="process",
                name="Process",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        # Should not raise
        validate_workflow_graph(graph, nodes=nodes)

    def test_valid_complex_dag_with_decision_and_merge(self) -> None:
        """Valid: complex DAG with DECISION, BRANCH, MERGE nodes."""
        graph = WorkflowGraph(
            workflow_id="wf2",
            nodes=["start", "decision", "branch_left", "branch_right", "merge", "exit"],
            edges=[
                Edge(from_node_id="start", to_node_id="decision"),
                Edge(from_node_id="decision", to_node_id="branch_left", condition="left"),
                Edge(from_node_id="decision", to_node_id="branch_right", condition="right"),
                Edge(from_node_id="branch_left", to_node_id="merge"),
                Edge(from_node_id="branch_right", to_node_id="merge"),
                Edge(from_node_id="merge", to_node_id="exit"),
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.AGENT,
                role=NodeRole.DECISION,
                context="global",
                agent_id="agent1",
            ),
            "branch_left": Node(
                stage_id="branch_left",
                name="Left Branch",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "branch_right": Node(
                stage_id="branch_right",
                name="Right Branch",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "merge": Node(
                stage_id="merge",
                name="Merge",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.MERGE,
                context="global",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        # Should not raise
        validate_workflow_graph(graph, nodes=nodes)

    def test_invalid_dag_no_start_node(self) -> None:
        """Invalid: DAG with no START node."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["process", "exit"],
            edges=[Edge(from_node_id="process", to_node_id="exit")],
        )
        nodes = {
            "process": Node(
                stage_id="process",
                name="Process",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "START node" in str(exc.value)

    def test_invalid_dag_no_exit_node(self) -> None:
        """Invalid: DAG with no EXIT node."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "process"],
            edges=[Edge(from_node_id="start", to_node_id="process")],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "process": Node(
                stage_id="process",
                name="Process",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "EXIT node" in str(exc.value)

    def test_invalid_dag_no_default_start(self) -> None:
        """Invalid: DAG with START node but default_start=False."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "exit"],
            edges=[Edge(from_node_id="start", to_node_id="exit")],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=False,  # Invalid: START without default_start
                context="global",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "default_start" in str(exc.value)

    def test_invalid_dag_multiple_default_starts(self) -> None:
        """Invalid: DAG with multiple START nodes having default_start=True."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start1", "start2", "exit"],
            edges=[
                Edge(from_node_id="start1", to_node_id="exit"),
                Edge(from_node_id="start2", to_node_id="exit"),
            ],
        )
        nodes = {
            "start1": Node(
                stage_id="start1",
                name="Start1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "start2": Node(
                stage_id="start2",
                name="Start2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,  # Invalid: two defaults
                context="global",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "Multiple nodes have default_start" in str(exc.value)

    def test_invalid_dag_cycle_detected(self) -> None:
        """Invalid: DAG with cycle."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "process", "exit"],
            edges=[
                Edge(from_node_id="start", to_node_id="process"),
                Edge(from_node_id="process", to_node_id="exit"),
                Edge(from_node_id="exit", to_node_id="start"),  # Creates cycle
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "process": Node(
                stage_id="process",
                name="Process",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "Cycle detected" in str(exc.value)

    def test_invalid_dag_unreachable_nodes(self) -> None:
        """Invalid: DAG with unreachable nodes from default start."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "process", "isolated", "exit"],
            edges=[
                Edge(from_node_id="start", to_node_id="process"),
                Edge(from_node_id="process", to_node_id="exit"),
                # isolated node has no incoming edges
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "process": Node(
                stage_id="process",
                name="Process",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "isolated": Node(
                stage_id="isolated",
                name="Isolated",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "Unreachable" in str(exc.value)

    def test_invalid_dag_no_path_to_exit(self) -> None:
        """Invalid: DAG where default start cannot reach any exit."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "process", "exit"],
            edges=[
                Edge(from_node_id="start", to_node_id="process"),
                # No path from start to exit (exit is unreachable)
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "process": Node(
                stage_id="process",
                name="Process",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        # Exit is unreachable, so we get unreachable node error
        assert "Unreachable" in str(exc.value) or "cannot reach any exit" in str(exc.value)

    def test_invalid_merge_node_less_than_two_inbound_edges(self) -> None:
        """Invalid: MERGE node with less than 2 inbound edges."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "split", "left", "right", "merge", "exit"],
            edges=[
                Edge(from_node_id="start", to_node_id="split"),
                Edge(from_node_id="split", to_node_id="left"),
                Edge(from_node_id="split", to_node_id="right"),
                Edge(from_node_id="left", to_node_id="merge"),
                # Missing: right edge to merge - this should trigger the error
                Edge(from_node_id="merge", to_node_id="exit"),
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "split": Node(
                stage_id="split",
                name="Split",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.SPLIT,
                context="global",
            ),
            "left": Node(
                stage_id="left",
                name="Left",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "right": Node(
                stage_id="right",
                name="Right",
                kind=NodeKind.AGENT,
                role=NodeRole.LINEAR,
                context="global",
                agent_id="agent1",
            ),
            "merge": Node(
                stage_id="merge",
                name="Merge",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.MERGE,
                context="global",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        # The error could be about the MERGE node or about the LINEAR node missing edges
        assert "Merge" in str(exc.value) or "LINEAR" in str(exc.value)

    def test_invalid_decision_node_less_than_two_outbound_edges(self) -> None:
        """Invalid: DECISION node with less than 2 outbound edges."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "decision", "next"],
            edges=[
                Edge(from_node_id="start", to_node_id="decision"),
                Edge(from_node_id="decision", to_node_id="next"),
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.AGENT,
                role=NodeRole.DECISION,
                context="global",
                agent_id="agent1",
            ),
            "next": Node(
                stage_id="next",
                name="Next",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        # Check for either "at least two outgoing edges" or "DECISION nodes must have at least 2"
        assert ("at least two outgoing" in str(exc.value).lower() or
                "decision nodes must have at least 2" in str(exc.value).lower())

    def test_invalid_start_node_with_agent_kind_in_dag(self) -> None:
        """Invalid: START node with kind=AGENT (business rule)."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "exit"],
            edges=[Edge(from_node_id="start", to_node_id="exit")],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.AGENT,  # Invalid for START
                role=NodeRole.START,
                default_start=True,
                context="global",
                agent_id="agent1",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        # Validator enforces kind-role constraint: START nodes must be DETERMINISTIC
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "START" in str(exc.value) and "DETERMINISTIC" in str(exc.value)

    def test_invalid_exit_node_with_agent_kind_in_dag(self) -> None:
        """Invalid: EXIT node with kind=AGENT (business rule)."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "exit"],
            edges=[Edge(from_node_id="start", to_node_id="exit")],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "exit": Node(
                stage_id="exit",
                name="Exit",
                kind=NodeKind.AGENT,  # Invalid for EXIT
                role=NodeRole.EXIT,
                context="global",
                agent_id="agent1",
            ),
        }
        # Validator enforces kind-role constraint: EXIT nodes must be DETERMINISTIC
        with pytest.raises(ValueError) as exc:
            validate_workflow_graph(graph, nodes=nodes)
        assert "EXIT" in str(exc.value) and "DETERMINISTIC" in str(exc.value)

    def test_valid_dag_without_node_metadata(self) -> None:
        """Valid: DAG validation without node metadata (falls back to graph structure)."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "process", "exit"],
            edges=[
                Edge(from_node_id="start", to_node_id="process"),
                Edge(from_node_id="process", to_node_id="exit"),
            ],
        )
        # Should not raise - validator falls back to graph structure
        validate_workflow_graph(graph, nodes=None)

    def test_valid_dag_with_multiple_exit_nodes(self) -> None:
        """Valid: DAG with multiple EXIT nodes (all reachable)."""
        graph = WorkflowGraph(
            workflow_id="wf",
            nodes=["start", "decision", "exit1", "exit2"],
            edges=[
                Edge(from_node_id="start", to_node_id="decision"),
                Edge(from_node_id="decision", to_node_id="exit1", condition="path1"),
                Edge(from_node_id="decision", to_node_id="exit2", condition="path2"),
            ],
        )
        nodes = {
            "start": Node(
                stage_id="start",
                name="Start",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.START,
                default_start=True,
                context="global",
            ),
            "decision": Node(
                stage_id="decision",
                name="Decision",
                kind=NodeKind.AGENT,
                role=NodeRole.DECISION,
                context="global",
                agent_id="agent1",
            ),
            "exit1": Node(
                stage_id="exit1",
                name="Exit1",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
            "exit2": Node(
                stage_id="exit2",
                name="Exit2",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="global",
            ),
        }
        # Should not raise
        validate_workflow_graph(graph, nodes=nodes)
