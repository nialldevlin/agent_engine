"""Tests for the workflow DAG validator."""

import pytest

from agent_engine.schemas import Edge, EdgeType, Stage, StageType, WorkflowGraph
from agent_engine.schemas.workflow import validate_workflow_graph


def test_valid_acyclic_graph_passes() -> None:
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1", "stage2"],
        edges=[Edge(from_stage_id="stage1", to_stage_id="stage2")],
    )

    # Should not raise
    stages = {
        "stage1": Stage(stage_id="stage1", name="Stage 1", type=StageType.AGENT),
        "stage2": Stage(stage_id="stage2", name="Stage 2", type=StageType.AGENT),
    }
    validate_workflow_graph(graph, stages=stages)


def test_graph_with_cycle_fails() -> None:
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1", "stage2"],
        edges=[
            Edge(from_stage_id="stage1", to_stage_id="stage2"),
            Edge(from_stage_id="stage2", to_stage_id="stage1"),
        ],
    )

    stages = {
        "stage1": Stage(stage_id="stage1", name="Stage 1", type=StageType.AGENT),
        "stage2": Stage(stage_id="stage2", name="Stage 2", type=StageType.AGENT),
    }

    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph, stages=stages)
    assert "Cycle detected" in str(exc.value)


def test_unreachable_node_fails() -> None:
    # Explicitly set start_stage_ids so that stage3 is not considered a start node
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1", "stage2", "stage3"],
        edges=[Edge(from_stage_id="stage1", to_stage_id="stage2")],
        start_stage_ids=["stage1"],
    )

    stages = {
        "stage1": Stage(stage_id="stage1", name="Stage 1", type=StageType.AGENT),
        "stage2": Stage(stage_id="stage2", name="Stage 2", type=StageType.AGENT),
        "stage3": Stage(stage_id="stage3", name="Stage 3", type=StageType.AGENT),
    }

    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph, stages=stages)
    assert "Unreachable stage" in str(exc.value) or "Unreachable" in str(exc.value)


def test_edge_to_unknown_stage_fails() -> None:
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1"],
        edges=[Edge(from_stage_id="stage1", to_stage_id="stage_unknown")],
    )

    stages = {"stage1": Stage(stage_id="stage1", name="Stage 1", type=StageType.AGENT)}

    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph, stages=stages)
    assert "unknown stage" in str(exc.value)


def test_conditional_edge_requires_decision_stage() -> None:
    graph = WorkflowGraph(
        workflow_id="wf",
        stages=["s1", "s2"],
        edges=[Edge(from_stage_id="s1", to_stage_id="s2", edge_type=EdgeType.CONDITIONAL)],
    )
    stages = {
        "s1": Stage(stage_id="s1", name="Start", type=StageType.AGENT),
        "s2": Stage(stage_id="s2", name="Next", type=StageType.AGENT),
    }
    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph, stages=stages)
    assert "Conditional edge" in str(exc.value)


def test_merge_stage_requires_multiple_inbound_edges() -> None:
    graph = WorkflowGraph(
        workflow_id="wf",
        stages=["left", "right", "merge"],
        edges=[
            Edge(from_stage_id="left", to_stage_id="merge"),
        ],
    )
    stages = {
        "left": Stage(stage_id="left", name="Left", type=StageType.AGENT),
        "right": Stage(stage_id="right", name="Right", type=StageType.AGENT),
        "merge": Stage(stage_id="merge", name="Merge", type=StageType.MERGE),
    }
    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph, stages=stages)
    assert "Merge stage" in str(exc.value)


def test_decision_stage_requires_multiple_outbound_edges() -> None:
    graph = WorkflowGraph(
        workflow_id="wf",
        stages=["decision", "next"],
        edges=[Edge(from_stage_id="decision", to_stage_id="next", edge_type=EdgeType.CONDITIONAL)],
    )
    stages = {
        "decision": Stage(stage_id="decision", name="Decision", type=StageType.DECISION),
        "next": Stage(stage_id="next", name="Next", type=StageType.AGENT),
    }
    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph, stages=stages)
    assert "at least two outgoing edges" in str(exc.value)
