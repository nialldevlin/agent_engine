"""ToolRuntime executes deterministic tools or LLM-backed handlers with safety checks."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_engine.json_engine import validate
from agent_engine.schemas import EngineError, EngineErrorCode, EngineErrorSource, Node, Severity, Task, ToolCallRecord, ToolDefinition, ToolKind
from agent_engine.security import check_tool_call


class ToolRuntime:
    """Dispatch tool calls to registered handlers or an LLM client."""

    def __init__(
        self,
        tools: Dict[str, ToolDefinition],
        tool_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] | None = None,
        llm_client=None,
    ) -> None:
        self.tools = tools
        self.tool_handlers = tool_handlers or {}
        self.llm_client = llm_client

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

        decision = check_tool_call(tool_def)
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
        }
        handler = self.tool_handlers.get(stage.tool_id)
        if tool_def.kind == ToolKind.DETERMINISTIC and handler:
            output = handler(call_input)
        elif tool_def.kind == ToolKind.LLM_TOOL and self.llm_client:
            output = self.llm_client.generate(call_input)
        else:
            output = {"tool": stage.tool_id, "echo": call_input}

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

            # Check permissions
            decision = check_tool_call(tool_def)
            if not decision.allowed:
                error = EngineError(
                    error_id="tool_permission_denied",
                    code=EngineErrorCode.SECURITY,
                    message=f"Tool '{tool_id}' permission denied: {decision.reason}",
                    source=EngineErrorSource.TOOL_RUNTIME,
                    severity=Severity.ERROR
                )
                return tool_calls, error

            # Execute tool
            started_at = self._now_iso()
            output = None
            tool_error = None

            try:
                handler = self.tool_handlers.get(tool_id)
                if tool_def.kind == ToolKind.DETERMINISTIC and handler:
                    output = handler(inputs)
                elif tool_def.kind == ToolKind.LLM_TOOL and self.llm_client:
                    output = self.llm_client.generate(inputs)
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

            except Exception as e:
                tool_error = EngineError(
                    error_id="tool_execution_failed",
                    code=EngineErrorCode.TOOL,
                    message=f"Tool execution failed: {e}",
                    source=EngineErrorSource.TOOL_RUNTIME,
                    severity=Severity.ERROR
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

            # If tool failed due to misuse, stop execution
            if tool_error and tool_error.code == EngineErrorCode.SECURITY:
                return tool_calls, tool_error

        return tool_calls, None

    def _now_iso(self) -> str:
        """Generate ISO-8601 timestamp."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("UTC")).isoformat()
