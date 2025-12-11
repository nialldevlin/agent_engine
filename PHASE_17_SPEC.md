# Phase 17: Multi-Task - MINIMAL

Add multi-task query methods:

1. **runtime/task_manager.py**: Add methods:
   - get_all_tasks()
   - get_tasks_by_status(status)
   - get_task_count()
   - clear_completed_tasks()

2. **engine.py**: Add methods:
   - run_multiple(inputs) - sequential execution
   - get_all_task_ids()
   - get_task_summary(task_id)

3. **docs/MULTI_TASK_ISOLATION.md**: Document isolation guarantees

4. **Tests**: 15+ tests covering multi-task queries, isolation

Minimal: Task tracking/queries, sequential execution only. No scheduling/concurrency.
Files: modify task_manager.py/engine.py, MULTI_TASK_ISOLATION.md, test file.
