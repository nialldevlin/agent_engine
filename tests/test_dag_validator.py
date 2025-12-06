"""Tests for the workflow DAG validator."""

from agent_engine.schemas.workflow import WorkflowGraph, Edge, validate_workflow_graph
import pytest


def test_valid_acyclic_graph_passes() -> None:
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1", "stage2"],
        edges=[Edge(from_stage_id="stage1", to_stage_id="stage2")],
    )

    # Should not raise
    validate_workflow_graph(graph)


def test_graph_with_cycle_fails() -> None:
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1", "stage2"],
        edges=[
            Edge(from_stage_id="stage1", to_stage_id="stage2"),
            Edge(from_stage_id="stage2", to_stage_id="stage1"),
        ],
    )

    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph)
    assert "Cycle detected" in str(exc.value)


def test_unreachable_node_fails() -> None:
    # Explicitly set start_stage_ids so that stage3 is not considered a start node
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1", "stage2", "stage3"],
        edges=[Edge(from_stage_id="stage1", to_stage_id="stage2")],
        start_stage_ids=["stage1"],
    )

    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph)
    assert "Unreachable stage" in str(exc.value) or "Unreachable" in str(exc.value)


def test_edge_to_unknown_stage_fails() -> None:
    graph = WorkflowGraph(
        workflow_id="test",
        stages=["stage1"],
        edges=[Edge(from_stage_id="stage1", to_stage_id="stage_unknown")],
    )

    with pytest.raises(ValueError) as exc:
        validate_workflow_graph(graph)
    assert "unknown stage" in str(exc.value)
