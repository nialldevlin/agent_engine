"""Pipeline executor loops through stages using agent/tool runtimes."""

from __future__ import annotations

from typing import Optional, Tuple

from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.schemas import ContextItem, EngineError, Stage, StageType, Task, TaskStatus
from agent_engine.telemetry import TelemetryBus


class PipelineExecutor:
    def __init__(
        self,
        task_manager: TaskManager,
        router: Router,
        context_assembler: ContextAssembler,
        agent_runtime,
        tool_runtime,
        telemetry: TelemetryBus | None = None,
        plugins=None,
    ) -> None:
        self.task_manager = task_manager
        self.router = router
        self.context_assembler = context_assembler
        self.agent_runtime = agent_runtime
        self.tool_runtime = tool_runtime
        self.telemetry = telemetry
        self.plugins = plugins

    def run(self, task: Task, pipeline_id: str) -> Task:
        pipeline = self.router.pipelines[pipeline_id]
        self._emit_plugin("before_task", task_id=task.task_id)
        self._emit_event("task", {"state": "start"})
        self.task_manager.set_status(task, TaskStatus.RUNNING)

        current_stage_id: Optional[str] = None
        retries: dict[str, int] = {}
        pending_decision: Optional[dict] = None
        while True:
            next_stage_id = self.router.next_stage(current_stage_id, pipeline, decision=pending_decision)
            pending_decision = None
            if next_stage_id is None:
                self.task_manager.set_status(task, TaskStatus.COMPLETED)
                break
            stage = self._resolve_stage(next_stage_id)
            self.task_manager.set_current_stage(task, stage.stage_id)
            ctx = self.context_assembler.build_context(task, request=self._default_context_request(task))
            started_at = self._timestamp()
            self._emit_plugin("before_stage", task_id=task.task_id, stage_id=stage.stage_id)
            self._emit_event("stage", {"state": "start", "stage_id": stage.stage_id})
            output, error = self._run_stage(task, stage, ctx)
            self._emit_plugin("after_stage", task_id=task.task_id, stage_id=stage.stage_id, error=error)
            self._emit_event("stage", {"state": "end", "stage_id": stage.stage_id, "error": bool(error)})

            # Record results and routing
            self.task_manager.record_stage_result(task, stage.stage_id, output=output, error=error, started_at=started_at)
            self.task_manager.append_routing(task, stage.stage_id, decision=None, agent_id=stage.agent_id)
            if output is not None and hasattr(self.context_assembler, "store"):
                try:
                    item = ContextItem(
                        context_item_id=f"{stage.stage_id}-{len(self.context_assembler.store.items)}",
                        kind="stage_output",
                        source=stage.stage_id,
                        payload=output,
                        tags=[stage.type.value],
                        token_cost=0,
                    )
                    self.context_assembler.store.add(item)
                except Exception:
                    pass

            # On-error handling
            if error:
                retries.setdefault(stage.stage_id, 0)
                policy = stage.on_error.get("policy")
                max_retries = stage.on_error.get("max_retries") or 0
                fallback_stage_id = stage.on_error.get("fallback_stage_id")

                if policy == "retry" and retries[stage.stage_id] < max_retries:
                    retries[stage.stage_id] += 1
                    continue
                if policy == "fallback_stage" and fallback_stage_id:
                    current_stage_id = fallback_stage_id
                    continue
                if policy == "skip":
                    current_stage_id = stage.stage_id
                    # proceed to next stage even though error occurred
                else:
                    # fallback end nodes if configured
                    if pipeline.fallback_end_stage_ids:
                        self.task_manager.set_status(task, TaskStatus.FAILED)
                        break
                    self.task_manager.set_status(task, TaskStatus.FAILED)
                    break

            if stage.type == StageType.DECISION:
                if isinstance(output, dict):
                    pending_decision = output
                else:
                    pending_decision = {"condition": output}

            if stage.terminal:
                self.task_manager.set_status(task, TaskStatus.COMPLETED if error is None else TaskStatus.FAILED)
                break
            current_stage_id = stage.stage_id if not error else current_stage_id

        return task

    def _run_stage(self, task: Task, stage: Stage, context_package):
        if stage.type == StageType.AGENT:
            self._emit_plugin("before_agent", task_id=task.task_id, stage_id=stage.stage_id)
            output, error = self.agent_runtime.run_agent_stage(task, stage, context_package)
            self._emit_plugin("after_agent", task_id=task.task_id, stage_id=stage.stage_id, error=error)
            return output, error
        if stage.type == StageType.TOOL:
            self._emit_plugin("before_tool", task_id=task.task_id, stage_id=stage.stage_id)
            output, error = self.tool_runtime.run_tool_stage(task, stage, context_package)
            self._emit_plugin("after_tool", task_id=task.task_id, stage_id=stage.stage_id, error=error)
            return output, error
        # For merge/decision/transform, no-op placeholder
        return None, None

    def _resolve_stage(self, stage_id: str) -> Stage:
        for stage in self.router.workflow.stages:
            if isinstance(stage, str):
                # If workflow uses IDs only, skip resolution; actual Stage lookup should be external
                break
        # The router stores IDs; here we expect stages to be stored elsewhere.
        # To keep executor functional, build a minimal Stage placeholder if not present.
        # In practice, stages are passed via EngineConfig.
        return self.router.workflow_stage_lookup(stage_id)

    def _default_context_request(self, task: Task):
        from agent_engine.schemas import ContextRequest

        return ContextRequest(
            context_request_id=f"ctx-req-{task.task_id}",
            budget_tokens=0,
            domains=[],
            history_types=[],
            mode=task.spec.mode.value,
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
