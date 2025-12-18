"""ToolRuntime executes deterministic tools or LLM-backed handlers with safety checks."""

from __future__ import annotations

import signal
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_engine.json_engine import validate
from agent_engine.runtime.parameter_resolver import ParameterResolver
from agent_engine.schemas import EngineError, EngineErrorCode, EngineErrorSource, Node, Severity, Task, ToolCallRecord, ToolDefinition, ToolKind, ArtifactType, ToolCapability
from agent_engine.security import check_tool_call


class ToolRuntime:
    """Dispatch tool calls to registered handlers or an LLM client."""

    def __init__(
        self,
        tools: Dict[str, ToolDefinition],
        tool_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] | None = None,
        llm_client=None,
        telemetry=None,
        artifact_store=None,
        policy_evaluator=None,
        workspace_root=None,
        allow_network: bool = False,
        allow_workspace_mutation: bool = True,
        parameter_resolver: Optional[ParameterResolver] = None,
    ) -> None:
        self.tools = tools
        self.tool_handlers = tool_handlers or {}
        self.llm_client = llm_client
        self.telemetry = telemetry
        self.artifact_store = artifact_store
        self.policy_evaluator = policy_evaluator
        self.workspace_root = workspace_root
        self.parameter_resolver = parameter_resolver
        # Security gates can be overridden at runtime; defaults allow workspace mutation for app tools
        self.allow_network = allow_network
        self.allow_workspace_mutation = allow_workspace_mutation

    def run_tool_stage(self, task: Task, node: Node, context_package) -> Tuple[Any | None, EngineError | None]:
        if not node.tools:
            return None, None
        # Use the first tool in the tools list
        tool_id = node.tools[0] if node.tools else None
        if not tool_id:
            return None, None
        tool_def = self.tools.get(tool_id)
        if tool_def is None:
            return None, None

        decision = check_tool_call(
            tool_def,
            allow_network=self.allow_network or getattr(tool_def, "allow_network", False),
            allow_workspace_mutation=self.allow_workspace_mutation
            or (hasattr(tool_def, "capabilities") and ToolCapability.WORKSPACE_MUTATION in tool_def.capabilities),
        )
        if not decision.allowed:
            from agent_engine.schemas import EngineErrorCode, EngineErrorSource, Severity

            return (
                None,
                EngineError(
                    error_id="tool_permission",
                    code=EngineErrorCode.SECURITY,
                    message=decision.reason,
                    source=EngineErrorSource.TOOL_RUNTIME,
                    severity=Severity.ERROR,
                ),
            )

        spec_obj = getattr(task, "spec", task)
        mode = getattr(spec_obj, "mode", None)
        call_input = {
            "task_id": getattr(task, "task_id", getattr(spec_obj, "task_spec_id", "unknown")),
            "request": getattr(spec_obj, "request", None),
            "mode": mode.value if mode else None,
            "context_items": [item.payload for item in context_package.items],
            "workspace_root": str(self.workspace_root) if self.workspace_root else None,
        }
        handler = self.tool_handlers.get(tool_id)
        if tool_def.kind == ToolKind.DETERMINISTIC and handler:
            output = handler(call_input)
        elif tool_def.kind == ToolKind.LLM_TOOL and self.llm_client:
            output = self.llm_client.generate(call_input)
        else:
            output = {"tool": tool_id, "echo": call_input}

        if tool_def.outputs_schema_id:
            validated, err = validate(tool_def.outputs_schema_id, output)
            if err:
                return None, err
            return validated, None

        return output, None

    def execute_tool_plan(
        self,
        tool_plan: Dict[str, Any],
        task: Task,
        node: Node,
        context_package
    ) -> Tuple[List, Optional[EngineError]]:
        """Execute ToolPlan steps deterministically.

        Args:
            tool_plan: ToolPlan dict with 'steps' list
            task: Current task
            node: Node executing the plan
            context_package: Assembled context

        Returns:
            (tool_calls_list, error)
            - tool_calls_list: List of ToolCallRecord objects
            - error: EngineError if any tool failed due to misuse, None otherwise
        """
        from uuid import uuid4

        tool_calls = []

        # Extract steps from tool_plan
        steps = tool_plan.get('steps', [])
        if not steps:
            return [], None

        # Execute each step
        for step in steps:
            tool_id = step.get('tool_id')
            inputs = step.get('inputs', {})
            reason = step.get('reason', '')
            kind = step.get('kind', 'analyze')

            if not tool_id:
                continue

            # Look up tool definition
            tool_def = self.tools.get(tool_id)
            if not tool_def:
                error = EngineError(
                    error_id="tool_not_found",
                    code=EngineErrorCode.TOOL,
                    message=f"Tool '{tool_id}' not found in registry",
                    source=EngineErrorSource.TOOL_RUNTIME,
                    severity=Severity.ERROR
                )
                return tool_calls, error

            # Resolve tool config if parameter resolver is available
            tool_config = {}
            if self.parameter_resolver:
                manifest_config = getattr(tool_def, 'config', {}) or {}
                tool_config = self.parameter_resolver.resolve_tool_config(
                    tool_id=tool_id,
                    manifest_config=manifest_config,
                    task_id=task.task_id,
                    project_id=getattr(task, 'project_id', None)
                )

            # Check if tool is enabled (enabled=false means skip)
            if not tool_config.get("enabled", True):
                continue  # Skip disabled tool

            # Check permissions
            decision = check_tool_call(
                tool_def,
                allow_network=self.allow_network or getattr(tool_def, "allow_network", False),
                allow_workspace_mutation=self.allow_workspace_mutation
                or (hasattr(tool_def, "capabilities") and ToolCapability.WORKSPACE_MUTATION in tool_def.capabilities),
            )
            if not decision.allowed:
                error = EngineError(
                    error_id="tool_permission_denied",
                    code=EngineErrorCode.SECURITY,
                    message=f"Tool '{tool_id}' permission denied: {decision.reason}",
                    source=EngineErrorSource.TOOL_RUNTIME,
                    severity=Severity.ERROR
                )
                return tool_calls, error

            # Check policy evaluator (Phase 14)
            if self.policy_evaluator:
                allowed, reason = self.policy_evaluator.check_tool_allowed(tool_id, task.task_id)
                if not allowed:
                    error = EngineError(
                        error_id="tool_policy_denied",
                        code=EngineErrorCode.SECURITY,
                        message=f"Tool '{tool_id}' denied by policy: {reason}",
                        source=EngineErrorSource.TOOL_RUNTIME,
                        severity=Severity.ERROR
                    )
                    return tool_calls, error

            # Emit tool invoked event
            if self.telemetry:
                self.telemetry.tool_invoked(
                    task_id=task.task_id,
                    node_id=node.stage_id,
                    tool_id=tool_id,
                    inputs=inputs
                )

            # Execute tool
            started_at = self._now_iso()
            output = None
            tool_error = None

            # Get timeout override or use default
            timeout = tool_config.get("timeout", getattr(tool_def, 'timeout', None))

            try:
                handler = self.tool_handlers.get(tool_id)
                if tool_def.kind == ToolKind.DETERMINISTIC and handler:
                    output = self._execute_with_timeout(handler, inputs, timeout, tool_id)
                elif tool_def.kind == ToolKind.LLM_TOOL and self.llm_client:
                    output = self._execute_with_timeout(
                        self.llm_client.generate, inputs, timeout, tool_id
                    )
                else:
                    # Echo fallback
                    output = {"tool": tool_id, "echo": inputs}

                # Validate tool output if schema present
                if tool_def.outputs_schema_id:
                    validated, err = validate(tool_def.outputs_schema_id, output)
                    if err:
                        tool_error = err
                        output = None
                    else:
                        output = validated

            except TimeoutError as e:
                tool_error = EngineError(
                    error_id="tool_execution_timeout",
                    code=EngineErrorCode.TOOL,
                    message=f"Tool execution timeout: {e}",
                    source=EngineErrorSource.TOOL_RUNTIME,
                    severity=Severity.ERROR
                )
            except Exception as e:
                tool_error = EngineError(
                    error_id="tool_execution_failed",
                    code=EngineErrorCode.TOOL,
                    message=f"Tool execution failed: {e}",
                    source=EngineErrorSource.TOOL_RUNTIME,
                    severity=Severity.ERROR
                )

            # Emit tool completed or failed event
            if self.telemetry:
                if tool_error:
                    self.telemetry.tool_failed(
                        task_id=task.task_id,
                        node_id=node.stage_id,
                        tool_id=tool_id,
                        error=tool_error
                    )
                else:
                    self.telemetry.tool_completed(
                        task_id=task.task_id,
                        node_id=node.stage_id,
                        tool_id=tool_id,
                        output=output,
                        status="success"
                    )

            # Create ToolCallRecord
            call_record = ToolCallRecord(
                call_id=f"call-{uuid4().hex[:8]}",
                tool_id=tool_id,
                stage_id=node.stage_id,
                inputs=inputs,
                output=output,
                error=tool_error,
                started_at=started_at,
                completed_at=self._now_iso(),
                metadata={'reason': reason, 'kind': kind}
            )
            tool_calls.append(call_record)

            # Store artifact if artifact store is available
            if self.artifact_store:
                self.artifact_store.store_artifact(
                    task_id=task.task_id,
                    artifact_type=ArtifactType.TOOL_RESULT,
                    payload={
                        "tool_name": tool_id,
                        "arguments": inputs,
                        "result": output
                    },
                    node_id=node.stage_id,
                    schema_ref=None,  # Tools don't have schema refs yet
                    additional_metadata={
                        "tool_call_id": call_record.call_id,
                        "status": "success" if tool_error is None else "failure"
                    }
                )

            # If tool failed due to misuse, stop execution
            if tool_error and tool_error.code == EngineErrorCode.SECURITY:
                return tool_calls, tool_error

        return tool_calls, None

    def _execute_with_timeout(
        self,
        func: Callable[[Dict[str, Any]], Any],
        inputs: Dict[str, Any],
        timeout: Optional[float],
        tool_id: str
    ) -> Any:
        """Execute a tool handler with optional timeout.

        Args:
            func: The callable to execute (handler or llm_client.generate).
            inputs: The input parameters for the function.
            timeout: Optional timeout in seconds. If None, executes without timeout.
            tool_id: Tool ID for error messages.

        Returns:
            The result of func(inputs).

        Raises:
            TimeoutError: If execution exceeds the timeout.
            Any exception raised by func.
        """
        if timeout is None:
            # No timeout, execute directly
            return func(inputs)

        # Use threading to implement timeout
        result = [None]
        exception = [None]

        def worker():
            try:
                result[0] = func(inputs)
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # Thread is still running after timeout
            raise TimeoutError(f"Tool '{tool_id}' execution exceeded timeout of {timeout} seconds")

        if exception[0]:
            raise exception[0]

        return result[0]

    def _now_iso(self) -> str:
        """Generate ISO-8601 timestamp."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("UTC")).isoformat()
