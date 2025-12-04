"""Runnable declarative example for the Agent Engine.

Pipeline structure is defined entirely in configs/basic_llm_agent/*.yaml and
is a simple DAG: user_input -> gather_context -> interpretation -> decomposition
-> planning -> execution -> review -> results.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from agent_engine.config_loader import load_engine_config
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.pipeline_executor import PipelineExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.schemas import ContextItem, ContextRequest, TaskMode, TaskSpec
from agent_engine.telemetry import TelemetryBus
from agent_engine.runtime.memory import TaskMemoryStore

CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs" / "basic_llm_agent"


class ExampleLLMClient:
    """Very small, deterministic LLM stand-in for the example."""

    def generate(self, prompt: dict):
        stage_id = prompt.get("agent_stage")
        request = prompt.get("task_request")
        if stage_id == "user_input":
            return {"notes": request}
        if stage_id == "interpretation":
            return {"summary": f"Understand request: {request}", "intent": "execute simple actions"}
        if stage_id == "decomposition":
            return {"steps": ["clarify goals", "list files", "prepare edits"], "request": request}
        if stage_id == "planning":
            return {"plan": f"Plan steps for: {request}", "tools": prompt.get("tools")}
        if stage_id == "review":
            return {"status": "approved", "notes": "Plan reviewed", "request": request}
        if stage_id == "results":
            return {"status": "done", "request": request}
        return {"echo": request, "stage": stage_id}


def gather_context_handler(call_input):
    cwd = Path(".")
    files = sorted([p.name for p in cwd.iterdir() if p.is_file()])[:10]
    return {"workspace_files": files, "request": call_input.get("request")}


def execution_handler(call_input):
    # Lightweight deterministic executor for common shell-like tasks.
    request = (call_input.get("request") or "").strip()
    cwd = Path(".")
    if request.lower().startswith(("ls", "list")):
        entries = sorted(p.name for p in cwd.iterdir())[:50]
        return {"executed": True, "kind": "list", "entries": entries}
    if request.lower().startswith("read "):
        target = request.split(" ", 1)[1].strip()
        path = cwd / target
        if path.exists() and path.is_file():
            return {"executed": True, "kind": "read", "path": target, "content": path.read_text()[:4000]}
        return {"executed": False, "error": f"File not found: {target}"}
    if request.lower().startswith("search "):
        needle = request.split(" ", 1)[1].strip()
        matches = []
        for p in cwd.rglob("*"):
            if p.is_file():
                try:
                    text = p.read_text()
                except Exception:
                    continue
                if needle in text:
                    matches.append(str(p))
            if len(matches) >= 20:
                break
        return {"executed": True, "kind": "search", "query": needle, "matches": matches}
    # For writes/edits, we respond with a stub to avoid unintentional mutations.
    return {
        "executed": False,
        "kind": "noop",
        "message": f"Execution stub: request '{request}' not actioned (writes are disabled in example).",
    }


def build_example_components():
    manifests = {
        "agents": CONFIG_DIR / "agents.yaml",
        "tools": CONFIG_DIR / "tools.yaml",
        "stages": CONFIG_DIR / "stages.yaml",
        "workflow": CONFIG_DIR / "workflow.yaml",
        "pipelines": CONFIG_DIR / "pipelines.yaml",
        "memory": CONFIG_DIR / "memory.yaml",
    }
    engine_config, err = load_engine_config(manifests)
    if err:
        raise SystemExit(f"Failed to load config: {err.message}")

    task_manager = TaskManager()
    router = Router(workflow=engine_config.workflow, pipelines=engine_config.pipelines, stages=engine_config.stages)  # type: ignore[arg-type]
    context_assembler = ContextAssembler(memory_config=engine_config.memory)
    agent_runtime = AgentRuntime(llm_client=ExampleLLMClient())
    tool_runtime = ToolRuntime(tools=engine_config.tools, tool_handlers={"gather_context": gather_context_handler, "execution": execution_handler})
    telemetry = TelemetryBus()
    executor = PipelineExecutor(task_manager, router, context_assembler, agent_runtime, tool_runtime, telemetry=telemetry)
    return engine_config, task_manager, router, context_assembler, executor, telemetry


def run_example(user_request: str):
    engine_config, task_manager, router, context_assembler, executor, telemetry = build_example_components()

    spec = TaskSpec(task_spec_id="example-task", request=user_request, mode=TaskMode.IMPLEMENT)
    pipeline = router.choose_pipeline(spec)
    task = task_manager.create_task(spec, pipeline_id=pipeline.pipeline_id)

    # Seed context with the raw request
    task_store = context_assembler.task_stores.get(task.task_id)
    if not task_store:
        task_store = TaskMemoryStore(task_id=task.task_id)
        context_assembler.task_stores[task.task_id] = task_store
    task_store.backend.add(
        ContextItem(
            context_item_id="req",
            kind="user_request",
            source="cli",
            payload={"request": user_request},
            tags=["request"],
            token_cost=1,
        )
    )

    ctx_req = ContextRequest(context_request_id="cli", budget_tokens=512, domains=[], history_types=[], mode=spec.mode.value)
    _ = context_assembler.build_context(task, ctx_req)

    final_task = executor.run(task, pipeline_id=pipeline.pipeline_id)
    print(f"Task status: {final_task.status.value}")
    for stage_id, rec in final_task.stage_results.items():
        print(f"- {stage_id}: output={rec.output} error={getattr(rec.error, 'message', None)}")
    print(f"Events emitted: {len(telemetry.events)}")


def main():
    parser = argparse.ArgumentParser(description="Run the basic LLM agent example pipeline.")
    parser.add_argument("request", help="User request to execute")
    args = parser.parse_args()
    run_example(args.request)


if __name__ == "__main__":
    main()
