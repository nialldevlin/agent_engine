"""NodeExecutor orchestrates single-node execution following canonical stage lifecycle."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from agent_engine.schemas import (
    EngineError,
    EngineErrorCode,
    EngineErrorSource,
    Node,
    NodeKind,
    NodeRole,
    Severity,
    StageExecutionRecord,
    Task,
    UniversalStatus,
)


def _now_iso() -> str:
    """Generate ISO-8601 timestamp."""
    return datetime.now(ZoneInfo("UTC")).isoformat()


class NodeExecutor:
    """Orchestrate single-node execution following canonical stage lifecycle.

    Per AGENT_ENGINE_SPEC §3.2, every node execution follows:
    1. Assemble context (using context profile)
    2. Execute deterministic logic or invoke LLM agent
    3. Validate output using node's output schema
    4. Update task current output
    5. Write complete structured history entry
    6. Determine routing according to node role

    This class handles steps 1-5. Step 6 (routing) is handled by the Router.
    """

    def __init__(
        self,
        agent_runtime,
        tool_runtime,
        context_assembler,
        json_engine,
        deterministic_registry
    ):
        self.agent_runtime = agent_runtime
        self.tool_runtime = tool_runtime
        self.context_assembler = context_assembler
        self.json_engine = json_engine
        self.deterministic_registry = deterministic_registry

    def execute_node(
        self,
        task: Task,
        node: Node
    ) -> Tuple[StageExecutionRecord, Optional[Any]]:
        """Execute a single node following canonical lifecycle.

        Args:
            task: Task being executed
            node: Node to execute

        Returns:
            (StageExecutionRecord, next_output)
            - StageExecutionRecord: Complete history record for this execution
            - next_output: Output to become task.current_output (or None on failure)
        """
        started_at = _now_iso()

        # Step 1: Validate input (if schema present)
        input_payload = task.current_output
        if node.inputs_schema_id:
            validated_input, validation_error = self._validate_input(node, input_payload)
            if validation_error:
                record = self._create_error_record(
                    node=node,
                    input_payload=input_payload,
                    error=validation_error,
                    started_at=started_at,
                    context_profile_id=None,
                    context_metadata={}
                )
                return record, None
            input_payload = validated_input

        # Step 2: Assemble context
        try:
            context_package = self.context_assembler.build_context(
                task,
                self._default_context_request(task)
            )
            context_profile_id = node.context if node.context not in ["global", "none"] else node.context
            context_metadata = self._get_context_metadata(context_package)
        except Exception as e:
            error = EngineError(
                error_id="context_assembly_failed",
                code=EngineErrorCode.UNKNOWN,
                message=f"Context assembly failed: {e}",
                source=EngineErrorSource.RUNTIME,
                severity=Severity.ERROR
            )
            record = self._create_error_record(
                node=node,
                input_payload=input_payload,
                error=error,
                started_at=started_at,
                context_profile_id=node.context,
                context_metadata={}
            )
            return record, None

        # Step 3: Execute node (agent or deterministic)
        if node.kind == NodeKind.AGENT:
            output, error, tool_plan = self._execute_agent_node(task, node, context_package)
        else:  # DETERMINISTIC
            output, error = self._execute_deterministic_node(task, node, context_package)
            tool_plan = None

        # If execution failed, return error record
        if error:
            record = self._create_error_record(
                node=node,
                input_payload=input_payload,
                error=error,
                started_at=started_at,
                context_profile_id=context_profile_id,
                context_metadata=context_metadata,
                tool_plan=tool_plan
            )
            return record, None

        # Step 4: Validate output (if schema present)
        if node.outputs_schema_id:
            validated_output, validation_error = self._validate_output(node, output)
            if validation_error:
                record = self._create_error_record(
                    node=node,
                    input_payload=input_payload,
                    error=validation_error,
                    started_at=started_at,
                    context_profile_id=context_profile_id,
                    context_metadata=context_metadata,
                    output=output,
                    tool_plan=tool_plan
                )
                return record, None
            output = validated_output

        # Step 5: Create complete StageExecutionRecord
        record = StageExecutionRecord(
            node_id=node.stage_id,
            node_role=node.role,
            node_kind=node.kind,
            input=input_payload,
            output=output,
            error=None,
            node_status=UniversalStatus.COMPLETED,
            tool_plan=tool_plan,
            tool_calls=[],  # Tool calls will be added by tool runtime
            context_profile_id=context_profile_id,
            context_metadata=context_metadata,
            started_at=started_at,
            completed_at=_now_iso()
        )

        return record, output

    def _validate_input(
        self,
        node: Node,
        input_payload: Any
    ) -> Tuple[Any, Optional[EngineError]]:
        """Validate input against node's input schema."""
        if not hasattr(self.json_engine, 'validate'):
            # No validation available, pass through
            return input_payload, None

        try:
            validated, error = self.json_engine.validate(node.inputs_schema_id, input_payload)
            if error:
                return None, error
            return validated, None
        except Exception as e:
            error = EngineError(
                error_id="input_validation_failed",
                code=EngineErrorCode.VALIDATION,
                message=f"Input validation failed: {e}",
                source=EngineErrorSource.RUNTIME,
                severity=Severity.ERROR,
                stage_id=node.stage_id
            )
            return None, error

    def _validate_output(
        self,
        node: Node,
        output_payload: Any
    ) -> Tuple[Any, Optional[EngineError]]:
        """Validate output against node's output schema."""
        if not hasattr(self.json_engine, 'validate'):
            # No validation available, pass through
            return output_payload, None

        try:
            validated, error = self.json_engine.validate(node.outputs_schema_id, output_payload)
            if error:
                return None, error
            return validated, None
        except Exception as e:
            error = EngineError(
                error_id="output_validation_failed",
                code=EngineErrorCode.VALIDATION,
                message=f"Output validation failed: {e}",
                source=EngineErrorSource.RUNTIME,
                severity=Severity.ERROR,
                stage_id=node.stage_id
            )
            return None, error

    def _execute_agent_node(
        self,
        task: Task,
        node: Node,
        context_package
    ) -> Tuple[Any, Optional[EngineError], Optional[Dict]]:
        """Execute agent node with potential ToolPlan emission.

        Returns:
            (output, error, tool_plan)
        """
        try:
            # Call agent runtime
            result = self.agent_runtime.run_agent_stage(task, node, context_package)

            # Handle different return formats (2-tuple or 3-tuple)
            if isinstance(result, tuple) and len(result) == 3:
                output, error, tool_plan = result
            else:
                output, error = result
                tool_plan = None

            if error:
                return None, error, None

            # If agent returned both main_result and tool_plan, extract them
            if isinstance(output, dict):
                if 'tool_plan' in output and 'main_result' in output:
                    tool_plan = output.get('tool_plan')
                    output = output.get('main_result')

                    # Execute tool plan if present
                    if tool_plan and node.tools:
                        tool_calls, tool_error = self.tool_runtime.execute_tool_plan(
                            tool_plan, task, node, context_package
                        )
                        if tool_error:
                            return None, tool_error, tool_plan

            return output, None, tool_plan

        except Exception as e:
            error = EngineError(
                error_id="agent_execution_failed",
                code=EngineErrorCode.AGENT,
                message=f"Agent execution failed: {e}",
                source=EngineErrorSource.AGENT_RUNTIME,
                severity=Severity.ERROR,
                stage_id=node.stage_id
            )
            return None, error, None

    def _execute_deterministic_node(
        self,
        task: Task,
        node: Node,
        context_package
    ) -> Tuple[Any, Optional[EngineError]]:
        """Execute deterministic node via registry or defaults."""
        # Look up registered operation
        operation = self.deterministic_registry.get(node.stage_id)

        if operation:
            # Execute registered operation
            try:
                return operation(task, node, context_package)
            except Exception as e:
                error = EngineError(
                    error_id="deterministic_execution_failed",
                    code=EngineErrorCode.UNKNOWN,
                    message=f"Deterministic operation failed: {e}",
                    source=EngineErrorSource.RUNTIME,
                    severity=Severity.ERROR,
                    stage_id=node.stage_id
                )
                return None, error

        # Fall back to role-based defaults
        default_op = self.deterministic_registry.get_default_for_role(node.role)
        if default_op:
            try:
                return default_op(task, node, context_package)
            except Exception as e:
                error = EngineError(
                    error_id="default_operation_failed",
                    code=EngineErrorCode.UNKNOWN,
                    message=f"Default operation failed: {e}",
                    source=EngineErrorSource.RUNTIME,
                    severity=Severity.ERROR,
                    stage_id=node.stage_id
                )
                return None, error

        # No operation found - return identity transform
        return task.current_output, None

    def _create_error_record(
        self,
        node: Node,
        input_payload: Any,
        error: EngineError,
        started_at: str,
        context_profile_id: Optional[str],
        context_metadata: Dict[str, Any],
        output: Any = None,
        tool_plan: Optional[Dict] = None
    ) -> StageExecutionRecord:
        """Create StageExecutionRecord for failed execution."""
        return StageExecutionRecord(
            node_id=node.stage_id,
            node_role=node.role,
            node_kind=node.kind,
            input=input_payload,
            output=output,
            error=error,
            node_status=UniversalStatus.FAILED,
            tool_plan=tool_plan,
            tool_calls=[],
            context_profile_id=context_profile_id,
            context_metadata=context_metadata,
            started_at=started_at,
            completed_at=_now_iso()
        )

    def _default_context_request(self, task: Task):
        """Build default context request for compatibility."""
        from agent_engine.schemas import ContextRequest

        return ContextRequest(
            context_request_id=f"ctx-req-{task.task_id}",
            budget_tokens=0,
            domains=[],
            history_types=[],
            mode=task.spec.mode.value if hasattr(task.spec, 'mode') and task.spec.mode else None,
            agent_profile=None,
        )

    def _get_context_metadata(self, context_package) -> Dict[str, Any]:
        """Extract context metadata for history recording."""
        try:
            if hasattr(self.context_assembler, 'get_context_metadata'):
                metadata = self.context_assembler.get_context_metadata(context_package)
                # Ensure it's a dict (in case of mocks or other implementations)
                if isinstance(metadata, dict):
                    return metadata
        except Exception:
            pass

        # Fallback: basic metadata
        metadata = {
            'items_count': len(context_package.items) if hasattr(context_package, 'items') else 0
        }
        return metadata
