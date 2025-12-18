"""Internal schemas for Router execution and merge coordination.

Per AGENT_ENGINE_SPEC §3.1-3.3 and AGENT_ENGINE_OVERVIEW §3.2,
these schemas support the Router's responsibility for DAG traversal,
task coordination, and merge scheduling.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import Field

from .base import SchemaBase


class WorkItemKind(str, Enum):
    """Type of work item in the router's worklist.

    Per AGENT_ENGINE_SPEC §3, work items represent the different
    operations the router must perform:
    - EXECUTE: Execute a node on a task
    - MERGE_WAIT: Wait for upstream tasks to complete
    - ROUTE_DECISION: Determine next node from decision output
    - CLONE_SPAWN: Create clones from branch node
    - SUBTASK_SPAWN: Create subtasks from split node
    """
    EXECUTE = "execute"
    MERGE_WAIT = "merge_wait"
    ROUTE_DECISION = "route_decision"
    CLONE_SPAWN = "clone_spawn"
    SUBTASK_SPAWN = "subtask_spawn"


class MergeInputItem(SchemaBase):
    """A single upstream output collected by a merge node.

    Per AGENT_ENGINE_SPEC §3.3 (Merge), merge nodes receive
    structured list of upstream outputs including:
    - The output payload
    - The producing node ID
    - Associated metadata (status, timestamp, etc.)

    Attributes:
        task_id: ID of the upstream task that produced this output
        node_id: ID of the node that produced this output
        output: The output payload from the upstream node
        node_status: Status of the upstream node (success/failure/partial)
        stage_result_index: Position in that node's stage_results (for history lookup)
        timestamp: ISO-8601 timestamp when output was produced
        lineage_metadata: Any lineage info from parent/clone/subtask
    """
    task_id: str = Field(..., description="Upstream task ID")
    node_id: str = Field(..., description="Node ID that produced this output")
    output: Optional[Any] = Field(default=None, description="Output payload from upstream node")
    node_status: str = Field(default="completed", description="Status of upstream node")
    stage_result_index: Optional[int] = Field(default=None, description="Position in stage_results")
    timestamp: Optional[str] = Field(default=None, description="ISO-8601 timestamp")
    lineage_metadata: Dict[str, Any] = Field(default_factory=dict, description="Lineage context")


class WorkItem(SchemaBase):
    """A work item in the router's worklist.

    Per AGENT_ENGINE_SPEC §3.1, the router maintains a worklist of
    operations to perform. Each work item describes one operation.

    Work items represent different routing operations:
    - EXECUTE: Execute a node with the given task
    - MERGE_WAIT: Wait for upstream tasks
    - ROUTE_DECISION: Extract decision from output
    - CLONE_SPAWN: Create clones from branch
    - SUBTASK_SPAWN: Create subtasks from split

    Attributes:
        kind: Type of work (execute, merge_wait, spawn_clones, etc.)
        task_id: Task this work item operates on
        node_id: Node this work item targets
        priority: Execution priority (lower number = higher priority)
        metadata: Additional context for this work item
        depends_on_work_items: IDs of work items this depends on
    """
    kind: WorkItemKind = Field(..., description="Type of work item")
    task_id: str = Field(..., description="Task this work operates on")
    node_id: str = Field(..., description="Target node for this work")
    priority: int = Field(default=0, description="Execution priority (lower = higher)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    depends_on_work_items: List[str] = Field(
        default_factory=list,
        description="IDs of work items this depends on"
    )


class MergeWaitState(SchemaBase):
    """State tracking for a merge node waiting for upstream tasks.

    Per AGENT_ENGINE_SPEC §3.3 (Merge), merge nodes must wait for
    all incoming branches or subtasks to complete before proceeding.
    This schema tracks the coordination state.

    When a task reaches a merge node, it must wait for all tasks
    on all inbound edges to complete. This state tracks:
    - Which inbound edges have completed
    - The collected upstream outputs
    - When we're ready to proceed

    Attributes:
        merge_node_id: ID of the merge node waiting
        task_id: Task waiting at this merge
        inbound_edge_count: Total number of inbound edges
        completed_tasks: Set of upstream task IDs that have completed
        collected_outputs: List of MergeInputItem from completed upstreams
        all_complete: Whether all upstreams are done (ready to proceed)
        ready_at: ISO-8601 timestamp when merge became ready
    """
    merge_node_id: str = Field(..., description="ID of the merge node")
    task_id: str = Field(..., description="Task waiting at merge")
    inbound_edge_count: int = Field(..., description="Total inbound edges")
    completed_tasks: List[str] = Field(
        default_factory=list,
        description="IDs of upstream tasks that completed"
    )
    collected_outputs: List[MergeInputItem] = Field(
        default_factory=list,
        description="Outputs collected from upstream tasks"
    )
    all_complete: bool = Field(default=False, description="All upstreams done?")
    ready_at: Optional[str] = Field(default=None, description="ISO-8601 timestamp")
