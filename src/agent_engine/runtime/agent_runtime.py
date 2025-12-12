"""AgentRuntime executes agent stages via an LLM client and JSON Engine."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from agent_engine.json_engine import validate
from agent_engine.schemas import EngineError, Node, Task, NodeRole


class AgentRuntime:
    """Lightweight AgentRuntime wiring prompt assembly to an LLM client."""

    def __init__(self, llm_client=None, template_version: str = "v1") -> None:
        self.llm_client = llm_client
        self.template_version = template_version

    def run_agent_stage(self, task: Task, node: Node, context_package) -> Tuple[Any | None, EngineError | None, Optional[Dict]]:
        """Execute agent stage with potential ToolPlan emission.

        Returns:
            (output, error, tool_plan) - 3-tuple
        """
        # Lightweight deterministic branching when no LLM client is configured
        if self.llm_client is None:
            payload = getattr(task, "current_output", None)
            if node.role == "decision" or getattr(node, "role", None) == NodeRole.DECISION:
                action = None
                if isinstance(payload, dict):
                    action = payload.get("action")
                if action in ("create", "edit"):
                    return {"condition": action}, None, None
                # Default to first branch
                return {"condition": "create"}, None, None

        # Build prompt (tool-aware if tools present)
        if node.tools:
            prompt = self._build_tool_aware_prompt(task, node, context_package)
        else:
            prompt = self._build_prompt(task, node, context_package)

        # Call LLM (adapt prompt to generic payload)
        if self.llm_client:
            if isinstance(prompt, dict):
                content = json.dumps(prompt)
            else:
                content = str(prompt)
            request_payload = {
                "messages": [{"role": "user", "content": content}],
                "prompt": content,
            }
            llm_output = self.llm_client.generate(request_payload)
        else:
            llm_output = prompt

        # Parse JSON if output is a string (LLM text response)
        if isinstance(llm_output, str):
            try:
                llm_output = json.loads(llm_output)
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, treat as literal string output
                pass

        # Parse output to extract tool_plan if present
        tool_plan = None
        main_result = llm_output

        if isinstance(llm_output, dict):
            if 'tool_plan' in llm_output and 'main_result' in llm_output:
                tool_plan = llm_output.get('tool_plan')
                main_result = llm_output.get('main_result')

        # Validate main result against output schema
        if node.outputs_schema_id:
            validated, err = validate(node.outputs_schema_id, main_result)
            if err:
                return None, err, None
            return validated, None, tool_plan

        return main_result, None, tool_plan

    def _build_prompt(self, task: Task, node: Node, context_package) -> Dict[str, Any]:
        spec = getattr(task, "spec", task)
        return {
            "template_version": self.template_version,
            "agent_stage": node.stage_id,
            "task_mode": getattr(spec, "mode", None).value if getattr(spec, "mode", None) else None,
            "task_request": getattr(spec, "request", None),
            "context": [item.payload for item in context_package.items],
            "tools": node.tools or [],
            "schema_id": node.outputs_schema_id,
        }

    def _build_tool_aware_prompt(self, task: Task, node: Node, context_package) -> Dict[str, Any]:
        """Build prompt that instructs agent to emit ToolPlan when tools are available."""
        spec = getattr(task, "spec", task)

        # Get tool definitions
        tool_definitions = []
        for tool_id in node.tools:
            tool_definitions.append({
                'tool_id': tool_id,
                'description': f'Tool {tool_id} available for use'
            })

        return {
            "template_version": self.template_version,
            "agent_stage": node.stage_id,
            "task_mode": getattr(spec, "mode", None).value if getattr(spec, "mode", None) else None,
            "task_request": getattr(spec, "request", None),
            "context": [item.payload for item in context_package.items] if hasattr(context_package, 'items') else [],
            "tools": tool_definitions,
            "schema_id": node.outputs_schema_id,
            "instructions": "When tools are available, emit JSON with both 'main_result' and 'tool_plan' keys. ToolPlan format: {'steps': [{'tool_id': '...', 'inputs': {...}, 'reason': '...', 'kind': '...'}]}"
        }
