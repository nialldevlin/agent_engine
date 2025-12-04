import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from examples.basic_llm_agent.cli import build_example_components

from agent_engine.schemas import ContextItem, ContextRequest, TaskMode, TaskSpec, TaskStatus
from agent_engine.runtime.memory import TaskMemoryStore


def test_basic_llm_agent_example_e2e() -> None:
    engine_config, task_manager, router, context_assembler, executor, telemetry = build_example_components()

    spec = TaskSpec(task_spec_id="example-e2e", request="list files", mode=TaskMode.IMPLEMENT)
    pipeline = router.choose_pipeline(spec)
    task = task_manager.create_task(spec, pipeline_id=pipeline.pipeline_id)

    task_store = context_assembler.task_stores.get(task.task_id)
    if not task_store:
        task_store = TaskMemoryStore(task_id=task.task_id)
        context_assembler.task_stores[task.task_id] = task_store
    task_store.backend.add(
        ContextItem(
            context_item_id="seed",
            kind="user_request",
            source="test",
            payload={"request": spec.request},
            tags=["request"],
            token_cost=1,
        )
    )
    ctx_req = ContextRequest(
        context_request_id="test",
        budget_tokens=256,
        domains=[],
        history_types=[],
        mode=spec.mode.value,
    )
    context_assembler.build_context(task, ctx_req)

    final = executor.run(task, pipeline_id=pipeline.pipeline_id)

    assert final.status == TaskStatus.COMPLETED
    assert "review" in final.stage_results
    assert not any(rec.error for rec in final.stage_results.values())

    gather_output = final.stage_results["gather_context"].output
    execution_output = final.stage_results["execution"].output
    review_output = final.stage_results["review"].output

    assert gather_output.workspace_files
    assert execution_output.executed is True
    assert execution_output.kind == "list"
    assert review_output.get("status") == "approved"
