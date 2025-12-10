"""Tests for DAG execution and decision routing in the DAG executor.

Demonstrates:
- DAG structure with transform → decision → branches → merge stages.
- Decision-based routing: different next stages based on decision output.
- Merge stage aggregating prior outputs.
- Task checkpointing and telemetry events.
"""

import pytest
from unittest.mock import MagicMock

from agent_engine.runtime.dag_executor import DAGExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import (
    Edge,
    Stage,
    StageType,
    TaskMode,
    TaskSpec,
    TaskStatus,
    WorkflowGraph,
)


def test_dag_execution_with_decision_routing():
    """Test a small DAG: transform → decision → (left|right) → merge."""
    stages = {
        "transform_1": Stage(
            stage_id="transform_1",
            name="Transform",
            type=StageType.LINEAR,
            entrypoint=True,
        ),
        "decision_1": Stage(
            stage_id="decision_1",
            name="Decision",
            type=StageType.DECISION,
        ),
        "left_branch": Stage(
            stage_id="left_branch",
            name="Left Branch",
            type=StageType.AGENT,
        ),
        "right_branch": Stage(
            stage_id="right_branch",
            name="Right Branch",
            type=StageType.AGENT,
        ),
        "merge_1": Stage(
            stage_id="merge_1",
            name="Merge",
            type=StageType.MERGE,
            terminal=True,
        ),
    }

    edges = [
        Edge(from_stage_id="transform_1", to_stage_id="decision_1"),
        Edge(from_stage_id="decision_1", to_stage_id="left_branch", condition="left"),
        Edge(from_stage_id="decision_1", to_stage_id="right_branch", condition="right"),
        Edge(from_stage_id="left_branch", to_stage_id="merge_1"),
        Edge(from_stage_id="right_branch", to_stage_id="merge_1"),
    ]

    graph = WorkflowGraph(
        workflow_id="test_dag_wf",
        stages=["transform_1", "decision_1", "left_branch", "right_branch", "merge_1"],
        edges=edges,
        start_stage_ids=["transform_1"],
        end_stage_ids=["merge_1"],
    )

    router = Router(workflow=graph, stages=stages)
    task_manager = TaskManager()
    context_assembler = MagicMock()
    telemetry = MagicMock()
    plugins = MagicMock()

    agent_runtime = MagicMock()
    tool_runtime = MagicMock()

    def mock_agent_stage(task, stage, context):
        """Mock agent runtime: return decision or stage output."""
        if stage.stage_id == "decision_1":
            return {"condition": "left"}, None
        elif stage.stage_id == "left_branch":
            return {"branch": "left", "result": "left_result"}, None
        elif stage.stage_id == "right_branch":
            return {"branch": "right", "result": "right_result"}, None
        return None, None

    agent_runtime.run_agent_stage.side_effect = mock_agent_stage
    tool_runtime.run_tool_stage.return_value = (None, None)

    executor = DAGExecutor(
        task_manager=task_manager,
        router=router,
        context_assembler=context_assembler,
        agent_runtime=agent_runtime,
        tool_runtime=tool_runtime,
        telemetry=telemetry,
        plugins=plugins,
    )

    spec = TaskSpec(task_spec_id="test_spec", mode=TaskMode.ANALYSIS_ONLY, request="Test request")
    task = task_manager.create_task(spec)
    context_assembler.build_context.return_value = MagicMock()

    result_task = executor.run(task)

    assert result_task.status == TaskStatus.COMPLETED
    assert result_task.task_id == task.task_id
    executed_stages = [entry.stage_id for entry in result_task.routing_trace]
    assert "transform_1" in executed_stages
    assert "decision_1" in executed_stages
    assert "left_branch" in executed_stages
    assert "merge_1" in executed_stages
    assert "right_branch" not in executed_stages

    assert plugins.emit.called
    assert telemetry.emit.called


def test_router_resolve_edge_deterministic():
    """Test Router.resolve_edge method with deterministic routing policy."""
    stages = {
        "s1": Stage(stage_id="s1", name="Stage 1", type=StageType.AGENT),
        "s2": Stage(stage_id="s2", name="Stage 2", type=StageType.AGENT),
        "s3": Stage(stage_id="s3", name="Stage 3", type=StageType.AGENT),
    }
    edges = [
        Edge(from_stage_id="s1", to_stage_id="s2", condition="go_to_s2"),
        Edge(from_stage_id="s1", to_stage_id="s3", condition="go_to_s3"),
    ]
    graph = WorkflowGraph(
        workflow_id="resolve_edge_wf",
        stages=["s1", "s2", "s3"],
        edges=edges,
        start_stage_ids=["s1"],
        end_stage_ids=["s3"]
    )
    router = Router(workflow=graph, stages=stages)

    # Test 1: Matching condition key "condition"
    decision_output = {"condition": "go_to_s2"}
    next_stage = router.resolve_edge(None, None, decision_output, edges)
    assert next_stage == "s2"

    # Test 2: Matching condition key "route"
    decision_output = {"route": "go_to_s3"}
    next_stage = router.resolve_edge(None, None, decision_output, edges)
    assert next_stage == "s3"

    # Test 3: No matching condition, multiple edges, defaults to first
    decision_output = {"condition": "nonexistent"}
    next_stage = router.resolve_edge(None, None, decision_output, edges)
    assert next_stage == "s2"  # First edge

    # Test 4: Empty decision output, multiple edges, defaults to first
    decision_output = {}
    next_stage = router.resolve_edge(None, None, decision_output, edges)
    assert next_stage == "s2"  # First edge

    # Test 5: Single edge, should return that edge
    single_edge = [edges[0]]
    decision_output = {}
    next_stage = router.resolve_edge(None, None, decision_output, single_edge)
    assert next_stage == "s2"

    # Test 6: Empty edges list should raise ValueError
    with pytest.raises(ValueError):
        router.resolve_edge(None, None, {}, [])
