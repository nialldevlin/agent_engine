from agent_engine.schemas import TaskMode, TaskStatus

from tests.helpers.basic_llm_agent import build_engine


def test_basic_llm_agent_example_e2e() -> None:
    engine = build_engine()
    final = engine.run_one("list files", mode=TaskMode.IMPLEMENT)

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
