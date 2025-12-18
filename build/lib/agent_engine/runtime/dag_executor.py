"""DAG executor loops through stages using agent/tool runtimes."""

from __future__ import annotations

from typing import Optional, Tuple

from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import ContextItem, EngineError, Node, NodeKind, NodeRole, Task, UniversalStatus
from agent_engine.telemetry import TelemetryBus


class DAGExecutor:
    def __init__(
        self,
        task_manager: TaskManager,
        router: Router,
        context_assembler: ContextAssembler,
        agent_runtime,
        tool_runtime,
        telemetry: TelemetryBus | None = None,
        plugins=None,
        json_engine=None,
        deterministic_registry=None,
    ) -> None:
        self.task_manager = task_manager
        self.router = router
        self.context_assembler = context_assembler
        self.agent_runtime = agent_runtime
        self.tool_runtime = tool_runtime
        self.telemetry = telemetry
        self.plugins = plugins

        # Add NodeExecutor integration
        from agent_engine.runtime.node_executor import NodeExecutor
        from agent_engine.runtime.deterministic_registry import DeterministicRegistry

        self.json_engine = json_engine
        self.deterministic_registry = deterministic_registry or DeterministicRegistry()
        self.node_executor = NodeExecutor(
            agent_runtime=agent_runtime,
            tool_runtime=tool_runtime,
            context_assembler=context_assembler,
            json_engine=json_engine or self._create_stub_json_engine(),
            deterministic_registry=self.deterministic_registry
        )

    def _create_stub_json_engine(self):
        """Create stub JSON engine for validation."""
        class StubJsonEngine:
            def validate(self, schema_id, payload):
                # Pass-through validation
                return payload, None
        return StubJsonEngine()

    def run(self, task: Task) -> Task:
        """Execute a task through the DAG workflow."""
        self._emit_plugin("before_task", task_id=task.task_id)
        self._emit_event("task", {"state": "start"})
        self.task_manager.set_status(task, UniversalStatus.IN_PROGRESS)

        current_stage_id: Optional[str] = None
        retries: dict[str, int] = {}
        pending_decision: Optional[dict] = None
        while True:
            next_stage_id = self.router.next_stage(current_stage_id, decision=pending_decision)
            pending_decision = None
            if next_stage_id is None:
                self.task_manager.set_status(task, UniversalStatus.COMPLETED)
                break
            node = self._resolve_stage(next_stage_id)
            self.task_manager.set_current_stage(task, node.stage_id)
            ctx = self.context_assembler.build_context(task, request=self._default_context_request(task))
            started_at = self._timestamp()
            self._emit_plugin("before_stage", task_id=task.task_id, stage_id=node.stage_id)
            self._emit_event("stage", {"state": "start", "stage_id": node.stage_id})
            self._emit_event("stage_started", {"stage_id": node.stage_id, "stage_type": node.kind.value, "task_id": task.task_id})
            output, error = self._run_stage(task, node, ctx)
            self._emit_plugin("after_stage", task_id=task.task_id, stage_id=node.stage_id, error=error)
            self._emit_event("stage", {"state": "end", "stage_id": node.stage_id, "error": bool(error)})
            self._emit_event("stage_finished", {"stage_id": node.stage_id, "stage_type": node.kind.value, "task_id": task.task_id, "error": bool(error)})

            # Record results and routing
            # Note: record_stage_result is now handled by _run_stage through NodeExecutor
            # self.task_manager.record_stage_result(task, node.stage_id, output=output, error=error, started_at=started_at)
            self.task_manager.append_routing(task, node.stage_id, decision=None, agent_id=node.agent_id)

            # Save checkpoint after stage execution
            checkpoint_error = self.task_manager.save_checkpoint(task.task_id)
            if checkpoint_error:
                self._emit_event("checkpoint_error", {"stage_id": node.stage_id, "task_id": task.task_id, "error": checkpoint_error.message})
            if output is not None and hasattr(self.context_assembler, "store"):
                try:
                    item = ContextItem(
                        context_item_id=f"{node.stage_id}-{len(self.context_assembler.store.items)}",
                        kind="stage_output",
                        source=node.stage_id,
                        payload=output,
                        tags=[node.kind.value],
                        token_cost=0,
                    )
                    self.context_assembler.store.add(item)
                except Exception:
                    pass

            # On-error handling
            if error:
                retries.setdefault(node.stage_id, 0)
                # For now, handle continue_on_failure as a simple flag
                if node.continue_on_failure:
                    current_stage_id = node.stage_id
                    # proceed to next stage even though error occurred
                else:
                    self.task_manager.set_status(task, UniversalStatus.FAILED)
                    break

            if node.role == NodeRole.DECISION:
                if isinstance(output, dict):
                    pending_decision = output
                else:
                    pending_decision = {"condition": output}

            if node.role == NodeRole.EXIT:
                self.task_manager.set_status(task, UniversalStatus.COMPLETED if error is None else UniversalStatus.FAILED)
                break
            current_stage_id = node.stage_id if not error else current_stage_id

        return task

    def _run_stage(self, task: Task, node: Node, ctx):
        """Execute a single node by delegating to NodeExecutor."""
        # Execute node through NodeExecutor
        record, next_output = self.node_executor.execute_node(task, node)

        # Store complete record in task history
        task.stage_results[node.stage_id] = record

        # Update task current output if execution succeeded
        if next_output is not None:
            task.current_output = next_output

        # Return output and error for compatibility
        return record.output, record.error

    def _resolve_stage(self, stage_id: str) -> Node:
        # If the Router was initialized with a stages mapping, use it
        try:
            return self.router.stages[stage_id]
        except Exception:
            # Fallback: attempt to ask router to resolve (some routers may provide helper)
            if hasattr(self.router, "workflow_stage_lookup"):
                return self.router.workflow_stage_lookup(stage_id)
            raise

    def _default_context_request(self, task: Task):
        from agent_engine.schemas import ContextRequest

        return ContextRequest(
            context_request_id=f"ctx-req-{task.task_id}",
            budget_tokens=0,
            domains=[],
            history_types=[],
            mode=task.spec.mode.value if getattr(task, "spec", None) and getattr(task.spec, "mode", None) else None,
            agent_profile=None,
        )

    def _emit_plugin(self, hook: str, **kwargs) -> None:
        if self.plugins:
            try:
                self.plugins.emit(hook, **kwargs)
            except Exception:
                # Defensive: executor should not crash from plugin errors
                pass

    def _emit_event(self, event_type: str, payload) -> None:
        if self.telemetry:
            from agent_engine.schemas import Event, EventType

            evt = Event(
                event_id=f"{event_type}-{len(self.telemetry.events)}",
                task_id=payload.get("task_id") if isinstance(payload, dict) else None,
                stage_id=payload.get("stage_id") if isinstance(payload, dict) else None,
                type=EventType[event_type.upper()] if event_type.upper() in EventType.__members__ else EventType.TELEMETRY,
                timestamp=None,
                payload=payload if isinstance(payload, dict) else {"payload": payload},
            )
            self.telemetry.emit(evt)

    def _timestamp(self) -> str:
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"
