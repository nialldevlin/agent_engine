"""AgentRuntime executes agent stages via an LLM client and JSON Engine."""

from __future__ import annotations

from typing import Any, Dict, Tuple

from agent_engine.json_engine import validate
from agent_engine.schemas import EngineError, Node, Task


class AgentRuntime:
    """Lightweight AgentRuntime wiring prompt assembly to an LLM client."""

    def __init__(self, llm_client=None, template_version: str = "v1") -> None:
        self.llm_client = llm_client
        self.template_version = template_version

    def run_agent_stage(self, task: Task, node: Node, context_package) -> Tuple[Any | None, EngineError | None]:
        prompt = self._build_prompt(task, node, context_package)
        llm_output = self.llm_client.generate(prompt) if self.llm_client else prompt

        if node.outputs_schema_id:
            validated, err = validate(node.outputs_schema_id, llm_output)
            if err:
                return None, err
            return validated, None

        return llm_output, None

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
