"""AgentRuntime executes agent stages via an LLM client and JSON Engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from agent_engine.json_engine import validate
from agent_engine.schemas import EngineError, Node, Task, NodeRole
from agent_engine.runtime.parameter_resolver import ParameterResolver
from agent_engine.runtime.llm_client import LLMClient
import re


class AgentRuntime:
    """Lightweight AgentRuntime wiring prompt assembly to an LLM client."""

    def __init__(
        self,
        llm_client=None,
        template_version: str = "v1",
        workspace_root: Optional[Path] = None,
        parameter_resolver: Optional[ParameterResolver] = None,
    ) -> None:
        self.llm_client = llm_client
        self.template_version = template_version
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.parameter_resolver = parameter_resolver
        # Cache for per-agent LLM clients: key = f"{agent_id}:{model}"
        self.agent_llm_clients: Dict[str, LLMClient] = {}

    def _get_or_create_llm_client(
        self,
        agent_id: str,
        llm_config: Dict[str, Any]
    ) -> Optional[LLMClient]:
        """Get cached LLM client or return default client.

        Key: f"{agent_id}:{llm_config['model']}"
        For now, returns the default self.llm_client since per-agent
        client creation depends on external configuration.

        Args:
            agent_id: ID of the agent.
            llm_config: Resolved LLM configuration dict.

        Returns:
            LLM client instance or None if not available.
        """
        if not self.llm_client:
            return None

        # Build cache key from agent_id and model
        model = llm_config.get("model", "unknown")
        cache_key = f"{agent_id}:{model}"

        # For now, return the default client
        # Future: instantiate per-agent clients based on llm_config
        return self.llm_client

    def clear_task_clients(self, task_id: str) -> None:
        """Clear parameter overrides for a task.

        Called when task completes to reset per-task parameter scope.

        Args:
            task_id: Task ID whose overrides should be cleared.
        """
        if self.parameter_resolver:
            self.parameter_resolver.clear_task_overrides(task_id)

    def run_agent_stage(self, task: Task, node: Node, context_package) -> Tuple[Any | None, EngineError | None, Optional[Dict]]:
        """Execute agent stage with potential ToolPlan emission.

        Returns:
            (output, error, tool_plan) - 3-tuple
        """
        # Lightweight deterministic branching for decision nodes
        if node.role == NodeRole.DECISION:
            payload = getattr(task, "current_output", None)
            action = None
            if isinstance(payload, dict):
                action = payload.get("action")
            if action in ("create", "edit"):
                decision_payload = {"condition": action, "action": action, "request": payload}
                return decision_payload, None, None
            # If no action and no LLM client, default to create
            if self.llm_client is None:
                return {"condition": "create", "action": "create", "request": payload}, None, None

        # For merge nodes like generate_summary, skip LLM and use fallback
        if node.role == NodeRole.MERGE:
            # Merge nodes should use deterministic fallback (read files)
            fallback_output, fallback_tool_plan = self._maybe_build_editor_plan(task, node)
            return fallback_output if fallback_output else task.current_output, None, fallback_tool_plan

        # Build prompt (tool-aware if tools present)
        if node.tools:
            prompt = self._build_tool_aware_prompt(task, node, context_package)
        else:
            prompt = self._build_prompt(task, node, context_package)

        # Deterministic fallback for Mini-Editor style flows (tools present, no LLM)
        fallback_output, fallback_tool_plan = self._maybe_build_editor_plan(task, node)

        # Resolve LLM config from manifest + overrides if parameter_resolver available
        llm_client = self.llm_client
        if self.parameter_resolver and node.agent_id and self.llm_client:
            try:
                # Extract project_id and task_id from task
                project_id = getattr(task, "project_id", None)
                task_id = getattr(task, "task_id", None)

                # Get agent's manifest config (empty dict as fallback)
                manifest_config = getattr(node, "config", {})
                manifest_llm_model = getattr(node, "llm", None)

                # Resolve final LLM config respecting priority: task > project > global
                llm_config = self.parameter_resolver.resolve_llm_config(
                    agent_id=node.agent_id,
                    manifest_config=manifest_config,
                    task_id=task_id,
                    project_id=project_id,
                    manifest_llm_model=manifest_llm_model,
                )

                # Get or create LLM client for this config
                llm_client = self._get_or_create_llm_client(node.agent_id, llm_config)
            except Exception as e:
                # Log error and fall back to default LLM client
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error resolving LLM config for agent {node.agent_id}: {e}")
                llm_client = self.llm_client

        # Call LLM (adapt prompt to generic payload)
        if llm_client:
            if isinstance(prompt, dict):
                content = json.dumps(prompt)
            else:
                content = str(prompt)
            request_payload = {
                "messages": [{"role": "user", "content": content}],
                "prompt": content,
            }
            try:
                llm_output = llm_client.generate(request_payload)
            except Exception as e:
                # Graceful fallback: return prompt payload with error note
                llm_output = {
                    "main_result": prompt,
                    "llm_error": str(e),
                }
        else:
            llm_output = fallback_output if fallback_output is not None else prompt

        # Parse JSON if output is a string (LLM text response)
        if isinstance(llm_output, str):
            try:
                llm_output = json.loads(llm_output)
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, treat as literal string output
                pass

        # Decision nodes must always return a routable condition; apply fallback if missing
        if node.role == NodeRole.DECISION:
            llm_output = self._ensure_decision_output(payload=llm_output, task=task)

        # Parse output to extract tool_plan if present
        tool_plan = None
        main_result = llm_output

        # Handle draft_document and edit_document nodes specially
        if node.stage_id in ("draft_document", "edit_document") and llm_client and node.stage_id != "generate_summary":
            # Extract payload details
            payload = getattr(task, "current_output", None)
            if isinstance(payload, dict):
                # Handle merge node payloads
                if "merge_inputs" in payload:
                    merge_inputs = payload.get("merge_inputs", [])
                    if merge_inputs and len(merge_inputs) > 0:
                        first_input = merge_inputs[0]
                        if isinstance(first_input, dict) and "output" in first_input:
                            payload = first_input["output"]

                action = payload.get("action") or payload.get("condition")
                path = payload.get("path")
                title = payload.get("title") or payload.get("name")
                user_input = payload.get("user_input")

                # If nested in request dict (from decision node), extract from there
                if user_input is None and isinstance(payload.get("request"), dict):
                    request_data = payload.get("request")
                    action = action or request_data.get("action")
                    path = path or request_data.get("path")
                    title = title or request_data.get("title") or request_data.get("name")
                    user_input = request_data.get("user_input")

                # Build natural language prompt for content generation
                if node.stage_id == "draft_document" and action == "create":
                    # Extract the task request for content generation
                    content_request = user_input if isinstance(user_input, str) else str(user_input)

                    # Remove "create a file X" prefix to get what to write about
                    # Match patterns like "Create a file X that/with/about/containing..."
                    match = re.search(r'(?:create|make|write)\s+(?:a\s+)?file\s+\S+\s+(?:that|with|about|containing|explaining|for)\s+(.+)', content_request, re.IGNORECASE)
                    if match:
                        content_topic = match.group(1)
                    else:
                        content_topic = content_request

                    # Build prompt asking LLM to generate content
                    natural_prompt = f"Generate markdown documentation about: {content_topic}\n\nReturn ONLY the markdown content, starting with a heading."

                    # Call LLM again with natural prompt
                    request_payload = {
                        "messages": [{"role": "user", "content": natural_prompt}],
                        "prompt": natural_prompt,
                    }
                    try:
                        generated_content = llm_client.generate(request_payload)
                        # Clean up the generated content
                        if isinstance(generated_content, str):
                            generated_content = generated_content.strip()
                    except Exception:
                        # Fall back to default content on LLM error
                        generated_content = None

                    if generated_content:
                        # Build tool plan with LLM-generated content
                        target_path = path or self._default_document_path(title)
                        tool_id = next((tid for tid in node.tools if "write" in tid), node.tools[0]) if node.tools else "write_file"
                        tool_plan = {
                            "steps": [{
                                "tool_id": tool_id,
                                "inputs": {"path": target_path, "content": generated_content},
                                "reason": "write LLM-generated content",
                                "kind": "write",
                            }]
                        }
                        main_result = {
                            "action": action or "create",
                            "path": target_path,
                            "title": title,
                            "summary_only": False,
                            "content": generated_content,
                        }

        # Original logic for other cases - but not for draft/edit nodes which built their own tool_plan
        if isinstance(llm_output, dict) and node.stage_id not in ("draft_document", "edit_document"):
            if 'tool_plan' in llm_output and 'main_result' in llm_output:
                if tool_plan is None:  # Don't override if already set above
                    tool_plan = llm_output.get('tool_plan')
                    main_result = llm_output.get('main_result')

        # Fallback to deterministic plan if LLM output had none
        if tool_plan is None and fallback_tool_plan:
            tool_plan = fallback_tool_plan
            if fallback_output is not None:
                main_result = fallback_output

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

    def _maybe_build_editor_plan(self, task: Task, node: Node) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Build a deterministic tool_plan for Mini-Editor style nodes.

        Returns (main_result, tool_plan) or (None, None) if not applicable.
        """
        # Only use deterministic fallback when no LLM client is available
        if self.llm_client is not None:
            return None, None

        payload = getattr(task, "current_output", None)

        # Handle merge node payloads - extract from merge_inputs if present
        request_payload = payload
        if isinstance(payload, dict) and "merge_inputs" in payload:
            merge_inputs = payload.get("merge_inputs", [])
            # Use the first merge input's output as the base payload
            if merge_inputs and len(merge_inputs) > 0:
                first_input = merge_inputs[0]
                if isinstance(first_input, dict) and "output" in first_input:
                    request_payload = first_input["output"]
                else:
                    request_payload = first_input
            payload = request_payload

        if not isinstance(payload, dict):
            return None, None
        request_payload = payload.get("request") if isinstance(payload.get("request"), dict) else {}

        action = payload.get("action") or payload.get("condition") or request_payload.get("action")
        path = payload.get("path") or request_payload.get("path")
        title = payload.get("title") or payload.get("name") or request_payload.get("title")
        summary_only = payload.get("summary_only", False) or request_payload.get("summary_only", False)
        user_input = payload.get("user_input") or request_payload.get("user_input") or payload.get("request")

        # Only synthesize for known nodes with filesystem tools
        if not node.tools:
            return None, None

        target_path = path or self._default_document_path(title)
        main_result: Dict[str, Any] = {
            "action": action or "create",
            "path": target_path,
            "title": title,
            "summary_only": summary_only,
        }

        # draft/create
        if node.stage_id == "draft_document" or (action == "create" and node.tools):
            content = payload.get("content") or self._default_content(title, user_input)
            tool_id = next((tid for tid in node.tools if "write" in tid), node.tools[0])
            tool_plan = {
                "steps": [
                    {
                        "tool_id": tool_id,
                        "inputs": {"path": target_path, "content": content},
                        "reason": "write initial document",
                        "kind": "write",
                    }
                ]
            }
            main_result["content"] = content
            return main_result, tool_plan

        # edit branch
        if node.stage_id == "edit_document" or action == "edit":
            content = payload.get("content") or self._default_content(title, user_input or "Apply edits")
            steps = []
            steps.append(
                {
                    "tool_id": node.tools[0],
                    "inputs": {"path": target_path, "max_bytes": 50_000},
                    "reason": "load document before edit",
                    "kind": "read",
                }
            )
            if not summary_only and len(node.tools) > 1:
                steps.append(
                    {
                        "tool_id": node.tools[-1],
                        "inputs": {"path": target_path, "content": content},
                        "reason": "apply edits",
                        "kind": "write",
                    }
                )
            tool_plan = {"steps": steps}
            main_result["content"] = content
            return main_result, tool_plan

        # summary branch
        if node.stage_id == "generate_summary":
            tool_plan = {
                "steps": [
                    {
                        "tool_id": node.tools[0],
                        "inputs": {"path": target_path, "max_bytes": 50_000},
                        "reason": "read document for summary",
                        "kind": "read",
                    }
                ]
            }
            return main_result, tool_plan

        return None, None

    def _default_document_path(self, title: Optional[str]) -> str:
        base = title or "document"

        # If title looks like a filename with extension, use it directly
        if re.match(r'^[\w\-\.]+\.\w+$', base):
            filename = base
        else:
            # Otherwise, slugify and add .md extension
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", base).strip("-").lower() or "document"
            filename = f"{slug}.md"

        # Keep documents under workspace/documents if workspace known
        if self.workspace_root:
            return str(self.workspace_root / "documents" / filename)
        return filename

    def _default_content(self, title: Optional[str], user_input: Optional[str]) -> str:
        heading = title or "Document"

        # Extract actual text from REPL-wrapped payload
        if isinstance(user_input, dict):
            # REPL wraps input as {"input": "...", "attached_files": []}
            body = user_input.get("input", "")
            if not body:
                # Fallback to JSON dump if no "input" key
                try:
                    body = json.dumps(user_input, indent=2)
                except Exception:
                    body = str(user_input)
        elif isinstance(user_input, str):
            body = user_input
        else:
            body = "Please draft the requested content."

        return f"# {heading}\n\n{body}\n"

    def _ensure_decision_output(self, payload: Any, task: Task) -> Dict[str, Any]:
        """Guarantee a decision payload with a 'condition' key for routing."""
        if isinstance(payload, dict):
            # If already has a condition/route, return as-is
            for key in ["condition", "route", "selected_edge", "selected_edge_label"]:
                if payload.get(key) is not None:
                    return payload
            # Fallback: derive action from task.current_output if dict
            current = getattr(task, "current_output", None)
            action = None
            if isinstance(current, dict):
                action = current.get("action") or current.get("condition")
            return {
                "condition": action or "create",
                "action": action or "create",
                "llm_error": payload.get("llm_error"),
                "main_result": payload.get("main_result", payload),
            }

        # Non-dict payloads: wrap with default condition
        return {
            "condition": "create",
            "action": "create",
            "main_result": payload,
        }
