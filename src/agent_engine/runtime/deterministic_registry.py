"""Registry for deterministic node operations."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

from agent_engine.schemas import EngineError, Node, Task


# Type alias for deterministic operation functions
DeterministicOperation = Callable[
    [Task, Node, Any],  # task, node, context_package
    Tuple[Any, Optional[EngineError]]  # (output, error)
]


class DeterministicRegistry:
    """Map node IDs to deterministic operation callbacks.

    Per PHASE_4_IMPLEMENTATION_PLAN §3.5, this registry allows projects to define
    custom deterministic logic for START, LINEAR, DECISION, and other deterministic nodes.

    Default operations are provided for common cases:
    - START: Identity transform (return input as-is)
    - LINEAR: Identity transform (return current_output as-is)
    - DECISION: Extract 'decision' key from current_output
    - EXIT: Identity transform (read-only)
    """

    def __init__(self):
        self.operations: Dict[str, DeterministicOperation] = {}
        self.default_start: Optional[DeterministicOperation] = None
        self.default_linear: Optional[DeterministicOperation] = None
        self.default_decision: Optional[DeterministicOperation] = None
        self.default_exit: Optional[DeterministicOperation] = None

        # Register built-in defaults
        self._register_builtin_defaults()

    def register(self, node_id: str, operation: DeterministicOperation) -> None:
        """Register a deterministic operation for a specific node.

        Args:
            node_id: Node stage_id to register operation for
            operation: Callable with signature (task, node, context) -> (output, error)
        """
        self.operations[node_id] = operation

    def get(self, node_id: str) -> Optional[DeterministicOperation]:
        """Retrieve registered operation for a node.

        Args:
            node_id: Node stage_id to look up

        Returns:
            Operation callable if registered, None otherwise
        """
        return self.operations.get(node_id)

    def register_default_start(self, operation: DeterministicOperation) -> None:
        """Register default START node operation."""
        self.default_start = operation

    def register_default_linear(self, operation: DeterministicOperation) -> None:
        """Register default LINEAR node operation."""
        self.default_linear = operation

    def register_default_decision(self, operation: DeterministicOperation) -> None:
        """Register default DECISION node operation."""
        self.default_decision = operation

    def register_default_exit(self, operation: DeterministicOperation) -> None:
        """Register default EXIT node operation."""
        self.default_exit = operation

    def get_default_for_role(self, role) -> Optional[DeterministicOperation]:
        """Get default operation for a node role.

        Args:
            role: NodeRole enum value

        Returns:
            Default operation for that role, or None
        """
        from agent_engine.schemas import NodeRole

        if role == NodeRole.START:
            return self.default_start
        elif role == NodeRole.LINEAR:
            return self.default_linear
        elif role == NodeRole.DECISION:
            return self.default_decision
        elif role == NodeRole.EXIT:
            return self.default_exit
        else:
            return None

    def _register_builtin_defaults(self) -> None:
        """Register built-in default operations."""

        # Default START: Return task input as-is (identity)
        def default_start_op(task: Task, node: Node, context_package) -> Tuple[Any, Optional[EngineError]]:
            # Extract input from task spec
            input_payload = getattr(task.spec, 'request', None)
            if input_payload is None:
                input_payload = task.current_output
            return input_payload, None

        # Default LINEAR: Return current output as-is (identity)
        def default_linear_op(task: Task, node: Node, context_package) -> Tuple[Any, Optional[EngineError]]:
            return task.current_output, None

        # Default DECISION: Extract decision key from current output
        def default_decision_op(task: Task, node: Node, context_package) -> Tuple[Any, Optional[EngineError]]:
            output = task.current_output
            if isinstance(output, dict) and 'decision' in output:
                return output, None
            # Wrap non-dict outputs
            return {'decision': str(output)}, None

        # Default EXIT: Return current output as-is (read-only)
        def default_exit_op(task: Task, node: Node, context_package) -> Tuple[Any, Optional[EngineError]]:
            return task.current_output, None

        self.default_start = default_start_op
        self.default_linear = default_linear_op
        self.default_decision = default_decision_op
        self.default_exit = default_exit_op
