"""ToolRuntime executes deterministic tools or LLM peasants with safety checks."""

from __future__ import annotations

from typing import Any, Callable, Dict, Tuple

from agent_engine.json_engine import validate
from agent_engine.schemas import EngineError, Stage, Task, ToolDefinition, ToolKind
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

    def run_tool_stage(self, task: Task, stage: Stage, context_package) -> Tuple[Any | None, EngineError | None]:
        if stage.tool_id is None:
            return None, None
        tool_def = self.tools.get(stage.tool_id)
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
        elif tool_def.kind == ToolKind.LLM_PEASANT and self.llm_client:
            output = self.llm_client.generate(call_input)
        else:
            output = {"tool": stage.tool_id, "echo": call_input}

        if tool_def.outputs_schema_id:
            validated, err = validate(tool_def.outputs_schema_id, output)
            if err:
                return None, err
            return validated, None

        return output, None
