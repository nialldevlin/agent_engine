from agent_engine.plugins import LoggingPlugin, PluginManager
from agent_engine.patterns import run_committee, run_supervisor


def test_plugin_manager_emits_hooks_non_strict() -> None:
    sink = []
    plugin = LoggingPlugin(sink)
    manager = PluginManager(strict=False)
    manager.register(plugin)
    manager.emit("on_before_task", task_id="t1")
    manager.emit("on_after_task", task_id="t1")
    assert sink == ["before_task:t1", "after_task:t1"]


def test_committee_and_supervisor_patterns() -> None:
    committee_result = run_committee(
        work_items=[1, 2, 3],
        worker_fn=lambda x: x * 2,
        merge_fn=lambda outputs: sum(outputs),
    )
    assert committee_result == 12

    supervisor_result = run_supervisor(
        tasks=[1, 2],
        worker_fn=lambda x: x + 1,
        supervisor_fn=lambda outputs: {"total": sum(outputs), "count": len(outputs)},
    )
    assert supervisor_result == {"total": 5, "count": 2}
